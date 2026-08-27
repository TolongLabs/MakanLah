"""The spike. Answers one question with a number.

Can ~50 KL restaurant posts be pulled into the source_post / venue / mention
schema in docs/TRD.md with name, location, dish and sentiment?

Every stage is resumable: raw notes cache to data/raw/, and the SQLite corpus is
keyed on (platform, platform_post_id), so a re-run costs no requests it already
made. A failed unit is counted and skipped, never fatal to the batch.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env
import extract
import geocode
import rednote
import schema

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
CORPUS = ROOT / 'data' / 'corpus'

KEYWORDS = [
    '吉隆坡美食',
    '吉隆坡餐厅推荐',
    'KL food',
    'Kuala Lumpur restaurant',
    '吉隆坡必吃',
    'KL cafe recommendation',
    '吉隆坡肉骨茶',
    'makan sedap Kuala Lumpur',
    '吉隆坡早餐',
    'KL hidden gem food',
    '八打灵美食',
    'nasi lemak KL',
]

CJK = re.compile(r'[一-鿿]')
MS = re.compile(r'\b(nasi|makan|sedap|kedai|restoran|jalan|dan|yang|di|ke|murah|enak)\b', re.I)
EN = re.compile(r'\b(the|and|food|restaurant|best|good|really|place|try)\b', re.I)


def detect_langs(text):
    """Plural by design. A single-language column would erase the code-switching
    that is the point of this corpus."""
    langs = []
    if CJK.search(text or ''):
        langs.append('zh')
    if MS.search(text or ''):
        langs.append('ms')
    if EN.search(text or ''):
        langs.append('en')
    return langs or ['und']


def post_text(note):
    return '\n'.join(x for x in [note.get('title'), note.get('desc')] if x)


async def gather(limit):
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / 'rednote_notes.jsonl'
    have = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            try:
                d = json.loads(line)
                have[d['note_id']] = d
            except json.JSONDecodeError:
                continue
    print(f'cache: {len(have)} notes already captured')
    if len(have) >= limit:
        return list(have.values())[:limit]

    fh = cache.open('a')

    def on_note(d):
        if d['note_id'] not in have:
            have[d['note_id']] = d
            fh.write(json.dumps(d, ensure_ascii=False) + '\n')
            fh.flush()

    await rednote.collect(KEYWORDS, limit - len(have), on_note=on_note)
    fh.close()
    return list(have.values())[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--no-geocode', action='store_true')
    a = ap.parse_args()

    env.load()
    print(f'extraction lane: {extract.lane_name()}')
    notes = asyncio.run(gather(a.limit))
    print(f'notes in hand: {len(notes)}')

    CORPUS.mkdir(parents=True, exist_ok=True)
    con = schema.connect(str(CORPUS / 'spike.db'))

    stats = dict(
        posts=0,
        extract_ok=0,
        extract_fail=0,
        venues=0,
        mentions=0,
        no_venue=0,
        excerpt_verbatim=0,
        excerpt_repaired=0,
        excerpt_dropped=0,
    )

    for i, n in enumerate(notes, 1):
        text = post_text(n)
        if not text.strip():
            continue
        pid = schema.upsert_post(
            con,
            platform='rednote',
            platform_post_id=n['note_id'],
            url=f'https://www.rednote.com/explore/{n["note_id"]}',
            author_handle=n.get('author'),
            posted_at=n.get('date'),
            langs=detect_langs(text),
            raw_text=text,
            media_urls=[],
            raw_payload={k: v for k, v in n.items() if k != 'url'},
        )
        stats['posts'] += 1

        try:
            venues, model = extract.extract(text)
            stats['extract_ok'] += 1
        except Exception as e:
            stats['extract_fail'] += 1
            print(f'  [{i}/{len(notes)}] extract failed {n["note_id"]}: {str(e)[:120]}')
            con.commit()
            continue

        if not venues:
            stats['no_venue'] += 1

        for v in venues:
            name = (v.get('name') or '').strip()
            if not name:
                continue
            vid = schema.upsert_venue(con, name=name, aliases=v.get('aliases') or [], area=v.get('area'))
            if not vid:
                continue
            ex, repaired = extract.repair_excerpt(v.get('excerpt'), name, v.get('aliases'), text)
            if ex is None:
                stats['excerpt_dropped'] += 1
            elif repaired:
                stats['excerpt_repaired'] += 1
            else:
                stats['excerpt_verbatim'] += 1
            schema.upsert_mention(
                con,
                post_id=pid,
                venue_id=vid,
                dishes=v.get('dishes'),
                sentiment=v.get('sentiment'),
                price_band=v.get('price_band'),
                excerpt=ex,
                extractor_model=model,
                confidence=v.get('confidence'),
            )
        con.commit()
        print(f'  [{i}/{len(notes)}] {n["note_id"]} -> {len(venues)} venue(s)')

    stats['venues'] = con.execute('select count(*) c from venue').fetchone()['c']
    stats['mentions'] = con.execute('select count(*) c from mention').fetchone()['c']

    if not a.no_geocode:
        todo = con.execute('select id, name, aliases, area from venue where lat is null').fetchall()
        print(f'geocoding {len(todo)} venues (1 req/sec, Nominatim)')
        hit = 0
        for r in todo:
            names = [r['name'], *json.loads(r['aliases'])]
            got = None
            for nm in names:
                got = geocode.geocode(nm, area=r['area'])
                if got:
                    break
            if got:
                lat, lng, disp, conf = got
                con.execute(
                    'update venue set lat=?, lng=?, address=?, geocoder=?, geocode_confidence=? where id=?',
                    (lat, lng, disp, 'nominatim', conf, r['id']),
                )
                hit += 1
        con.commit()
        print(f'geocoded {hit}/{len(todo)}')

    report(con, stats)


def report(con, stats):
    def q(sql):
        return con.execute(sql).fetchone()['c']

    total_v = q('select count(*) c from venue')
    with_loc = q('select count(*) c from venue where lat is not null')
    m_dish = q("select count(*) c from mention where dishes != '[]'")
    m_sent = q('select count(*) c from mention where sentiment is not null')
    m_exc = q('select count(*) c from mention where excerpt is not null')
    m_total = q('select count(*) c from mention')
    orphan = q("""select count(*) c from venue v where not exists
                  (select 1 from mention m where m.venue_id = v.id)""")
    uncited = q("""select count(*) c from mention m where not exists
                   (select 1 from source_post p where p.id = m.post_id)""")
    langs = con.execute('select langs, count(*) c from source_post group by langs').fetchall()

    def pct(n, d):
        return f'{100 * n / d:.0f}%' if d else 'n/a'

    print(
        f"""
================ SPIKE RESULT ================
posts captured        {stats['posts']}
  extraction ok       {stats['extract_ok']}   failed {stats['extract_fail']}
  named no venue      {stats['no_venue']}

venues                {total_v}
  with coordinates    {with_loc}  ({pct(with_loc, total_v)})
  orphaned            {orphan}

mentions              {m_total}
  with a dish         {m_dish}  ({pct(m_dish, m_total)})
  with sentiment      {m_sent}  ({pct(m_sent, m_total)})
  with an excerpt     {m_exc}  ({pct(m_exc, m_total)})

excerpt provenance    verbatim {stats['excerpt_verbatim']}  """
        f"""repaired {stats['excerpt_repaired']}  dropped {stats['excerpt_dropped']}

INVARIANT every mention joins a source_post: {'PASS' if uncited == 0 else f'FAIL ({uncited})'}

languages per post:"""
    )
    for r in langs:
        print(f'  {r["langs"]:24} {r["c"]}')
    print('==============================================')


if __name__ == '__main__':
    main()

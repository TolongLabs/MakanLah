"""discover -> fetch -> store raw -> extract -> resolve venue -> geocode -> embed

Each stage is resumable and idempotent, keyed on (platform, platform_post_id).
A stage that fails records the failure and continues the batch; an ingestion
failure is a normal outcome, not an exception (docs/AUTONOMY.md).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import geocode as geo
from makanlah import config, db, models
from makanlah.text import NOT_A_VENUE, detect_langs, normalize

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'


def load_raw(path):
    notes = []
    if not path.exists():
        return notes
    for line in path.read_text().splitlines():
        try:
            notes.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return notes


def ingest_notes(notes, platform='rednote'):
    """Records the run so `degraded` can be answered honestly. A run that dies
    mid-batch leaves ok = null, which reads as 'did not finish' rather than as a
    pass -- an absent verifier must never look like success."""
    stats = dict(
        skipped_extracted=0,
        posts=0,
        extracted=0,
        extract_failed=0,
        mentions=0,
        skipped_venue=0,
        excerpt_model=0,
        excerpt_repaired=0,
        excerpt_dropped=0,
    )
    with db.connect(direct=True) as con:
        run_id = db.start_run(con, platform)
        for n in notes:
            text = '\n'.join(x for x in [n.get('title'), n.get('desc')] if x).strip()
            if not text:
                continue
            post_id = db.upsert_post(
                con,
                platform=platform,
                platform_post_id=n['note_id'],
                url=f'https://www.rednote.com/explore/{n["note_id"]}',
                author_handle=n.get('author'),
                posted_at_raw=n.get('date'),
                langs=detect_langs(text),
                raw_text=text,
                media_urls=[],
                raw_payload={k: v for k, v in n.items() if k != 'token'},
            )
            con.commit()
            stats['posts'] += 1

            if db.already_extracted(con, post_id, config.settings().extract_model):
                stats['skipped_extracted'] += 1
                continue

            try:
                venues, model = models.extract(text)
                stats['extracted'] += 1
            except Exception as e:
                stats['extract_failed'] += 1
                print(f'  extract failed {n["note_id"]}: {str(e)[:100]}', flush=True)
                continue

            for v in venues:
                name = (v.get('name') or '').strip()
                norm = normalize(name)
                if not norm or norm in NOT_A_VENUE:
                    stats['skipped_venue'] += 1
                    continue
                venue_id = db.upsert_venue(
                    con,
                    name=name,
                    name_normalized=norm,
                    aliases=[a for a in (v.get('aliases') or []) if a],
                    area=v.get('area'),
                )
                excerpt, origin = models.repair_excerpt(v.get('excerpt'), name, v.get('aliases'), text)
                stats[f'excerpt_{origin}'] += 1
                if db.upsert_mention(
                    con,
                    post_id=post_id,
                    venue_id=venue_id,
                    dishes=v.get('dishes') or [],
                    sentiment=v.get('sentiment'),
                    price_band=v.get('price_band'),
                    excerpt=excerpt,
                    excerpt_origin=origin,
                    extractor_model=model,
                    confidence=v.get('confidence'),
                ):
                    stats['mentions'] += 1
            con.commit()
            db.mark_extracted(con, post_id, model)
            con.commit()
            print(f'  [{stats["posts"]}] {n["note_id"]} -> {len(venues)} venue(s)', flush=True)
        db.finish_run(
            con,
            run_id,
            ok=stats['extract_failed'] < max(1, stats['posts']),
            posts_seen=len(notes),
            posts_kept=stats['posts'],
            error=f'{stats["extract_failed"]} extraction failures' if stats['extract_failed'] else None,
        )
    return stats


def geocode_pending(limit=None):
    hit = miss = 0
    with db.connect(direct=True) as con:
        rows = con.execute(
            'select id, name, aliases, area from venue where lat is null' + (f' limit {int(limit)}' if limit else '')
        ).fetchall()
        print(f'geocoding {len(rows)} venues (1 req/sec)', flush=True)
        for r in rows:
            got = None
            for nm in [r['name'], *(r['aliases'] or [])]:
                got = geo.geocode(nm, area=r['area'])
                if got:
                    break
            if got:
                lat, lng, disp, conf = got
                db.set_coords(con, r['id'], lat, lng, disp, 'nominatim', conf)
                con.commit()
                hit += 1
            else:
                miss += 1
    return hit, miss


def embed_pending():
    s = config.settings()
    done = 0
    with db.connect(direct=True) as con:
        rows = db.venue_documents(con, only_missing_for=s.embed_model)
        print(f'embedding {len(rows)} venues with {s.embed_model}', flush=True)
        for i in range(0, len(rows), models.EMBED_BATCH):
            chunk = rows[i : i + models.EMBED_BATCH]
            try:
                vecs = models.embed([c['document'] for c in chunk])
            except Exception as e:
                print(f'  embed batch failed: {str(e)[:100]}', flush=True)
                continue
            for c, v in zip(chunk, vecs, strict=True):
                db.upsert_embedding(con, c['id'], s.embed_model, v)
                done += 1
            con.commit()
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default=str(RAW / 'rednote_notes.jsonl'))
    ap.add_argument('--skip-geocode', action='store_true')
    ap.add_argument('--skip-embed', action='store_true')
    a = ap.parse_args()

    notes = load_raw(Path(a.raw))
    print(f'raw notes: {len(notes)}', flush=True)
    stats = ingest_notes(notes)
    print(json.dumps(stats, indent=2))

    if not a.skip_geocode:
        hit, miss = geocode_pending()
        print(f'geocoded {hit}, unresolved {miss}')
    if not a.skip_embed:
        print(f'embedded {embed_pending()} venues')


if __name__ == '__main__':
    main()

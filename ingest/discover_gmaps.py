"""Google Maps as a source of venues, not only as an annotation on them.

`enrich_gmaps` iterates `venue where exists (mention)`. Maps supplies 84% of the
evidence in this corpus and could not introduce a single restaurant: every venue
entered through ~20 RedNote keywords, so a place that is popular on Maps but that
Chinese-language RedNote writers have not posted about was invisible by
construction (#157). That is the ceiling a Malaysian tester hit in one sitting.

It is also the non-negotiable in AGENTS.md going unmet where it matters most:
RedNote is load-bearing for *discovery* even though it carries a minority of the
evidence.

A discovered venue carries coordinates and a place_id and NO evidence. That is
deliberate and it is safe: `filter_candidates` and `venues_with_citations` both
inner-join `mention`, so a venue with no post behind it cannot be recommended.
It becomes recommendable only once `enrich_gmaps` captures real review text for
it. Discovery widens the funnel; it never invents a recommendation.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import cdp, gmaps
from makanlah import db
from makanlah.text import normalize

# Where people in the Klang Valley actually eat, not where the influencers post.
# Trend-driven capture already covers the city centre; the gap the tester named is
# the neighbourhood, so the ordinary suburbs carry as much weight here as KLCC.
AREAS = [
    'Bangsar',
    'Cheras',
    'Kepong',
    'Setapak',
    'Old Klang Road',
    'Petaling Jaya',
    'SS2',
    'SS15',
    'Damansara',
    'Mont Kiara',
    'Bukit Bintang',
    'Chow Kit',
    'Sentul',
    'Wangsa Maju',
    'Ampang',
    'Puchong',
    'Seri Kembangan',
    'Subang Jaya',
    'Shah Alam',
    'Klang',
    'Sri Petaling',
    'Bukit Jalil',
    'Taman Desa',
    'Segambut',
    'Titiwangsa',
    'Pandan Indah',
    'Kajang',
    'Serdang',
]

# Deliberately mixed-language and mixed-register: a grid that is all English
# returns an English-signposted corpus, which is the same bias RedNote gave us in
# the other direction. Generic terms ('restaurant', 'kopitiam') reach the shops
# that no dish keyword names.
DISHES = [
    'nasi lemak',
    'bak kut teh',
    'char kway teow',
    'banana leaf rice',
    'roti canai',
    'dim sum',
    'chicken rice',
    'laksa',
    'satay',
    'wantan mee',
    'curry mee',
    'nasi kandar',
    'rojak',
    'cendol',
    'seafood',
    'steamboat',
    'kopitiam',
    'mamak',
    'cafe',
    'restaurant',
    'economy rice',
    'yong tau foo',
    'claypot',
    'noodles',
    'dessert',
    'breakfast',
    'supper',
]


def plan_queries(areas=None, dishes=None, city='Kuala Lumpur'):
    """The area x dish grid, in a fixed order so `--offset` means something.

    Sorted rather than nested-loop order because #128: every un-offset run
    re-captures the same top N, and a grid that reorders between runs makes an
    offset resume land somewhere else entirely.
    """
    areas = AREAS if areas is None else areas
    dishes = DISHES if dishes is None else dishes
    return sorted(f'{d} {a} {city}'.strip() for a in areas for d in dishes)


def area_of(query, areas=None):
    """Which known area this query was built for.

    Recovered by matching against the list rather than by splitting on spaces:
    'Old Klang Road' splits to 'Road', which would then be written as the
    neighbourhood of every venue found there. Longest match first, so 'SS15'
    is not read as 'SS1'.
    """
    areas = AREAS if areas is None else areas
    for a in sorted(areas, key=len, reverse=True):
        if a in query:
            return a
    return None


def corpus_index(con):
    """The two keys a discovered place can already be known by."""
    rows = con.execute('select id, name, place_id from venue').fetchall()
    by_place_id, by_norm = {}, {}
    for r in rows:
        if r['place_id']:
            by_place_id[r['place_id']] = r['id']
        key = normalize(r['name'])
        if key:
            by_norm.setdefault(key, r['id'])
    return {'by_place_id': by_place_id, 'by_norm': by_norm}


def resolve_against_corpus(rec, existing):
    """(venue_id | None, action). place_id decides before the name does.

    #59: the evidence-based merge on place_id is the right rule and must not be
    loosened, because a wrong merge is not recoverable. A name match is weaker --
    it is how 华阳冰室 and 华阳 Oriental Kopi became two rows for one kopitiam --
    so a name hit adopts the place_id rather than being trusted on its own.
    """
    pid = rec.get('place_id')
    if pid and pid in existing['by_place_id']:
        return existing['by_place_id'][pid], 'known'
    key = normalize(rec.get('name') or '')
    if key and key in existing['by_norm']:
        return existing['by_norm'][key], 'adopt_place_id'
    return None, 'new'


def apply_discovered(con, records, area, existing, stats):
    """Persist one query's worth of places. No mention rows: see the module note."""
    for rec in records:
        venue_id, action = resolve_against_corpus(rec, existing)
        if action == 'known':
            stats['known'] += 1
            continue
        if action == 'adopt_place_id':
            con.execute(
                """update venue set place_id = coalesce(place_id, %s),
                          lat = coalesce(lat, %s), lng = coalesce(lng, %s),
                          geocoder = coalesce(geocoder, 'google_maps'),
                          geocode_confidence = coalesce(geocode_confidence, 0.9)
                   where id = %s""",
                (rec['place_id'], rec['lat'], rec['lng'], venue_id),
            )
            existing['by_place_id'][rec['place_id']] = venue_id
            stats['adopted'] += 1
            continue
        new_id = db.upsert_venue(con, name=rec['name'], name_normalized=normalize(rec['name']), aliases=[], area=area)
        con.execute(
            """update venue set lat=%s, lng=%s, place_id=%s, geocoder='google_maps',
                      geocode_confidence=0.9 where id=%s""",
            (rec['lat'], rec['lng'], rec['place_id'], new_id),
        )
        existing['by_place_id'][rec['place_id']] = new_id
        key = normalize(rec['name'])
        if key:
            existing['by_norm'].setdefault(key, new_id)
        stats['new'] += 1


async def run(con, queries, per_query=60, tab_every=5, pause=2.5):
    stats = dict(new=0, known=0, adopted=0, queries=0, failed=0, seen=0)
    existing = corpus_index(con)
    run_id = db.start_run(con, 'google_maps')
    for i in range(0, len(queries), tab_every):
        batch = queries[i : i + tab_every]
        try:
            async with cdp.Session() as page:
                for q in batch:
                    area = area_of(q)
                    try:
                        found = await asyncio.wait_for(gmaps.discover(page, q, limit=per_query), timeout=180)
                    except TimeoutError:
                        stats['failed'] += 1
                        print(f'  timeout {q!r}', flush=True)
                        continue
                    except Exception as e:
                        stats['failed'] += 1
                        print(f'  failed {q!r}: {str(e)[:70]}', flush=True)
                        continue
                    before = stats['new']
                    stats['seen'] += len(found)
                    apply_discovered(con, found, area, existing, stats)
                    con.commit()
                    stats['queries'] += 1
                    print(
                        f'  [{stats["queries"]}/{len(queries)}] {q[:44]!r} {len(found)} found '
                        f'{stats["new"] - before} new (total new {stats["new"]})',
                        flush=True,
                    )
                    await asyncio.sleep(pause)
        except Exception as e:
            stats['failed'] += len(batch)
            print(f'  tab batch failed: {str(e)[:90]}', flush=True)
    db.finish_run(
        con,
        run_id,
        ok=stats['new'] > 0,
        posts_seen=stats['seen'],
        posts_kept=stats['new'],
        error=f'{stats["failed"]} queries failed' if stats['failed'] else None,
    )
    return stats


def main():
    ap = argparse.ArgumentParser(description='Discover KL venues from Google Maps (#157)')
    ap.add_argument('--limit', type=int, default=None, help='how many grid queries to run')
    ap.add_argument('--offset', type=int, default=0, help='resume point in the grid (#128)')
    ap.add_argument('--per-query', type=int, default=60)
    ap.add_argument('--query', action='append', help='run these instead of the grid')
    ap.add_argument('--dry-run', action='store_true', help='print the grid and exit')
    args = ap.parse_args()

    queries = args.query or plan_queries()
    if not args.query:
        queries = queries[args.offset : args.offset + args.limit if args.limit else None]
    if args.dry_run:
        print(f'{len(queries)} queries')
        for q in queries[:20]:
            print(' ', q)
        return
    if not cdp.alive():
        print('no CDP on 9222 -- run scripts/chrome-session.sh start', file=sys.stderr)
        raise SystemExit(1)

    # Direct, not pooled: this is a long ingestion batch, which is exactly the
    # case pgbouncer's transaction mode does not support.
    with db.connect(direct=True) as con:
        stats = asyncio.run(run(con, queries, per_query=args.per_query))
    print(
        f'\n{stats["queries"]} queries, {stats["seen"]} places seen, '
        f'{stats["new"]} new venues, {stats["adopted"]} adopted a place_id, '
        f'{stats["known"]} already known, {stats["failed"]} failed'
    )


if __name__ == '__main__':
    main()

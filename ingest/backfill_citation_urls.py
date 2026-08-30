"""Add the place id to Google Maps citation URLs already written (#163).

`review_url` built a bare text search, so every Maps citation chip was a fuzzy
lookup for the venue's name. Measured 0 of 20 carrying `query_place_id` while
`venue.maps_url` carried it all along.

For most venues that degrades gracefully. For `Undisclosed Location` -- a real
place whose name the extraction lost -- the chip searched Maps for the literal
words and resolved to nothing, which breaks the one thing the product promises.
"""

import argparse
import sys

from makanlah import db


def backfill(dry_run=False):
    counts = {'examined': 0, 'updated': 0, 'no_place_id': 0, 'already': 0}
    with db.connect(direct=True) as con:
        rows = con.execute(
            """select p.id, p.url, v.place_id, v.name
               from source_post p
               join mention m on m.post_id = p.id
               join venue v on v.id = m.venue_id
               where p.platform = 'google_maps'
               group by p.id, p.url, v.place_id, v.name"""
        ).fetchall()
        pending = []
        for r in rows:
            counts['examined'] += 1
            if 'query_place_id=' in (r['url'] or ''):
                counts['already'] += 1
                continue
            if not r['place_id']:
                counts['no_place_id'] += 1
                continue
            pending.append((f'{r["url"]}&query_place_id={r["place_id"]}', r['id']))
        if pending and not dry_run:
            con.cursor().executemany('update source_post set url = %s where id = %s', pending)
            con.commit()
        counts['updated'] = len(pending)
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    c = backfill(dry_run=args.dry_run)
    head = 'would update' if args.dry_run else 'updated'
    print(
        f'examined {c["examined"]}, {head} {c["updated"]}, already had one {c["already"]}, no place_id {c["no_place_id"]}'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())

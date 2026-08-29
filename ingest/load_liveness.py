"""Load externally measured post liveness into source_post.dead_at.

The prober in ingest/liveness.py cannot classify RedNote over plain HTTP:
measured against five independently classified posts it agreed 0 of 5, because
the note renders client-side and the served HTML is byte-identical for a live
post and a dead one. A real browser can tell, so the measurement is taken by the
UAT harness and loaded here rather than duplicating a browser stack.

**Only `live` and `dead` are written.** `unknown` means the probe learned
nothing -- a timeout, a 429, a login wall that never resolved -- and writing it
would delete real evidence from the product on the strength of one bad network
minute. It is counted and reported, never applied.

`live` clears a previous mark rather than being ignored: a post can come back,
and a stale dead_at hides evidence forever.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from makanlah import db

WRITABLE = {'live', 'dead'}


def read_rows(path: Path):
    text = path.read_text()
    if path.suffix == '.json':
        data = json.loads(text)
        return data['rows'] if isinstance(data, dict) and 'rows' in data else data
    return list(csv.DictReader(text.splitlines()))


def summarise(rows):
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get('verdict', 'missing')] = counts.get(r.get('verdict', 'missing'), 0) + 1
    return counts


def apply(con, rows, dry_run=False):
    applied = {'dead': 0, 'live': 0}
    skipped = 0
    with con.cursor() as cur:
        for r in rows:
            verdict = (r.get('verdict') or '').strip()
            url = (r.get('post_url') or '').strip()
            if verdict not in WRITABLE or not url:
                skipped += 1
                continue
            if dry_run:
                applied[verdict] += 1
                continue
            value = r.get('checked_at') if verdict == 'dead' else None
            cur.execute(
                'update source_post set dead_at = %s where url = %s',
                (value, url),
            )
            applied[verdict] += cur.rowcount
        if not dry_run:
            con.commit()
    return applied, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description='Load measured post liveness into source_post.dead_at')
    ap.add_argument('path', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    rows = read_rows(args.path)
    print(f'{len(rows)} rows: {summarise(rows)}')

    with db.connect(direct=True) as con:
        with con.cursor() as cur:
            cur.execute('select count(*) c, count(dead_at) d from source_post')
            before = dict(cur.fetchone())
        print(f'before: {before["d"]} of {before["c"]} posts marked dead')

        applied, skipped = apply(con, rows, dry_run=args.dry_run)

        with con.cursor() as cur:
            cur.execute('select count(*) c, count(dead_at) d from source_post')
            after = dict(cur.fetchone())
    print(f'applied: {applied}, skipped (not live/dead): {skipped}')
    print(
        f'after : {after["d"]} of {after["c"]} posts marked dead'
        + ('  [DRY RUN, nothing written]' if args.dry_run else '')
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())

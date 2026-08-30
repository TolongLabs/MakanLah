"""Re-tag Google Maps posts whose language column was never filled (#133).

`enrich_gmaps.py` hardcoded `langs=['und']`, so 1,388 of 1,507 posts carried no
language tag and every one of them was a Maps review. Language-aware retrieval
reads this column, which made the whole Maps half of the corpus invisible to it.

The ingest path is fixed in the same change; this repairs what it already wrote.
Replaces rather than appends: a row tagged 'und' must come out tagged 'zh', not
'und,zh', or the tag it exists to remove survives the repair.
"""

import argparse
import sys

from makanlah import db
from makanlah.text import detect_langs

# Rows a reader would call untagged. A row with a real tag is never touched.
UNTAGGED = "(langs is null or langs = '{}' or langs = array['und'])"


def backfill(limit=None, dry_run=False, batch=200, retag_all=False):
    counts = {'examined': 0, 'updated': 0, 'unchanged': 0, 'no_text': 0}
    tally = {}
    with db.connect(direct=True) as con:
        # --all re-runs the detector over every post, not just the untagged ones.
        # Widening a detector leaves correctly-tagged rows carrying the OLD answer,
        # and detect_langs is plural, so a re-tag can only add a language to a row.
        where = 'true' if retag_all else f"platform = 'google_maps' and {UNTAGGED}"
        sql = f'select id, raw_text, langs from source_post where {where} order by id'
        rows = con.execute(sql + (' limit %s' if limit else ''), (limit,) if limit else ()).fetchall()

        pending = []
        for r in rows:
            counts['examined'] += 1
            text = (r['raw_text'] or '').strip()
            if not text:
                counts['no_text'] += 1
                continue
            langs = detect_langs(text)
            if langs == list(r['langs'] or []) or (not retag_all and langs == ['und']):
                counts['unchanged'] += 1
                continue
            tally[','.join(langs)] = tally.get(','.join(langs), 0) + 1
            pending.append((langs, r['id']))

            # Batched so a failure costs one batch, not the whole run. 1,388 rows in
            # one transaction is also long enough to matter on a pooled connection.
            if not dry_run and len(pending) >= batch:
                con.cursor().executemany('update source_post set langs = %s where id = %s', pending)
                con.commit()
                counts['updated'] += len(pending)
                pending = []

        if pending:
            if dry_run:
                counts['updated'] += len(pending)
            else:
                con.cursor().executemany('update source_post set langs = %s where id = %s', pending)
                con.commit()
                counts['updated'] += len(pending)

    return counts, tally


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--limit', type=int, help='stop after this many candidate rows')
    ap.add_argument('--dry-run', action='store_true', help='report what would change, write nothing')
    ap.add_argument(
        '--all',
        dest='retag_all',
        action='store_true',
        help='re-tag every post, not only the untagged ones. Use after widening a detector',
    )
    args = ap.parse_args()

    counts, tally = backfill(limit=args.limit, dry_run=args.dry_run, retag_all=args.retag_all)
    head = 'would update' if args.dry_run else 'updated'
    print(
        f'examined {counts["examined"]}, {head} {counts["updated"]}, '
        f'already correct {counts["unchanged"]}, empty text {counts["no_text"]}'
    )
    for combo, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f'  {combo}: {n}')
    return 0 if counts['examined'] else 1


if __name__ == '__main__':
    sys.exit(main())

"""Fill `price_band` from post text the corpus already holds (#158).

The tester's second complaint was price, and it was not a scraping shortfall: 49
of 1,653 mentions carried a band while the posts behind them named figures in
three languages that extraction had not been asked for. Re-reading cached text
costs no scrape and no model call.

The band is only ever written where the writer named a figure. A mention whose
post says nothing about cost keeps its null -- inferring a band from cuisine or
area is the halal-guess defect (#126) in a different column.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db
from makanlah.prices import price_band_from_text

# An explicit range is a writer stating what a visit costs. A bare figure in prose
# is usually one dish, one drink, or a number that is not money at all -- measured
# at 58 of 315 hits on this corpus, and wrong in the direction that matters: the
# post reading "on the pricey side (a mangorange drink costs around RM12)" parsed
# to the cheapest band.
RM_RANGE = re.compile(r'(?:RM|rm)\s?[\d,]+\s?[-–—~]\s?(?:RM|rm)?\s?[\d,]+')
PER_PERSON = re.compile(r'人均|每人|一个人|per\s*(?:person|pax|head)|seorang|a\s*head|\beach\b', re.I)


def figure_describes_the_meal(text):
    """Whether a figure in this post is a claim about what eating there costs.

    The parser answers 'is there a figure'; this answers 'is it the meal'. Keeping
    them apart matters because the parser is right as specified -- it is the
    inference from any figure to a venue's price band that is unsound.
    """
    t = text or ''
    if not isinstance(t, str):
        return False
    return bool(RM_RANGE.search(t) or PER_PERSON.search(t))


def candidates(con, limit=None):
    """Mentions with no band, and the post text behind them."""
    sql = """select m.id, p.raw_text
             from mention m join source_post p on p.id = m.post_id
             where m.price_band is null and p.raw_text is not null and p.raw_text <> ''
             order by m.id"""
    if limit:
        sql += f' limit {int(limit)}'
    return [dict(r) for r in con.execute(sql).fetchall()]


def run(con, limit=None, dry_run=False):
    rows = candidates(con, limit)
    stats = {'seen': len(rows), 'filled': 0, 'bands': {1: 0, 2: 0, 3: 0, 4: 0}}
    stats['skipped_unqualified'] = 0
    for r in rows:
        band = price_band_from_text(r['raw_text'])
        if band is None:
            continue
        # A figure is not a price unless the post says it is what a visit costs.
        if not figure_describes_the_meal(r['raw_text']):
            stats['skipped_unqualified'] += 1
            continue
        stats['filled'] += 1
        stats['bands'][band] += 1
        if not dry_run:
            con.execute('update mention set price_band = %s where id = %s', (band, r['id']))
    if not dry_run:
        con.commit()
    return stats


def main():
    ap = argparse.ArgumentParser(description='Backfill mention.price_band from cached post text (#158)')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--dry-run', action='store_true', help='report what would be filled, write nothing')
    a = ap.parse_args()
    with db.connect(direct=True) as con:
        stats = run(con, a.limit, a.dry_run)
    verb = 'would fill' if a.dry_run else 'filled'
    print(f'{stats["seen"]} unpriced mentions read, {verb} {stats["filled"]}')
    print(f'  bands: {stats["bands"]}')
    print(f'  skipped, figure not stated as a meal cost: {stats["skipped_unqualified"]}')


if __name__ == '__main__':
    main()

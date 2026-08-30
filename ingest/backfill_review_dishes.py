"""Tag Maps reviews with the dishes they name, and the price they state (#157, #158).

`enrich_gmaps` writes every Maps mention with `dishes=[]` and `price_band=None`.
Maps carries 84% of this corpus's evidence, so the lexical dish lane could not see
most of it: `roti canai` returned nothing across the whole city while two RedNote
venues carried the tag and dozens of enriched Indian restaurants had reviews that
named it in plain English.

The vocabulary is the corpus's own dish strings, so this is a snowball rather than
a new source of truth -- RedNote's extractions teach the reader what to look for in
Maps text, and nothing is invented that no post ever said.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.backfill_prices import figure_describes_the_meal
from makanlah import db
from makanlah.dishes import dishes_in_text
from makanlah.prices import price_band_from_text


def candidates(con, limit=None):
    """Maps mentions carrying no dishes, with the review text behind them."""
    sql = """select m.id, m.excerpt, m.price_band
             from mention m join source_post p on p.id = m.post_id
             where p.platform = 'google_maps' and cardinality(m.dishes) = 0
               and m.excerpt is not null and m.excerpt <> ''
             order by m.id"""
    if limit:
        sql += f' limit {int(limit)}'
    return [dict(r) for r in con.execute(sql).fetchall()]


def run(con, limit=None, dry_run=False):
    vocab = [d for d in db.dish_vocabulary(con) if d]
    rows = candidates(con, limit)
    stats = {'seen': len(rows), 'tagged': 0, 'dishes_written': 0, 'priced': 0}
    for r in rows:
        found = dishes_in_text(r['excerpt'], vocab)
        band = None
        if r['price_band'] is None and figure_describes_the_meal(r['excerpt']):
            band = price_band_from_text(r['excerpt'])
        if not found and band is None:
            continue
        if found:
            stats['tagged'] += 1
            stats['dishes_written'] += len(found)
        if band is not None:
            stats['priced'] += 1
        if not dry_run:
            con.execute(
                'update mention set dishes = %s, price_band = coalesce(price_band, %s) where id = %s',
                (found, band, r['id']),
            )
    if not dry_run:
        con.commit()
    return stats


def main():
    ap = argparse.ArgumentParser(description='Tag Maps reviews with dishes and price (#157/#158)')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    with db.connect(direct=True) as con:
        stats = run(con, a.limit, a.dry_run)
    verb = 'would tag' if a.dry_run else 'tagged'
    print(f'{stats["seen"]} untagged Maps mentions read')
    print(f'  {verb} {stats["tagged"]} with {stats["dishes_written"]} dish tag(s)')
    print(f'  {"would price" if a.dry_run else "priced"} {stats["priced"]}')


if __name__ == '__main__':
    main()

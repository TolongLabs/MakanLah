"""Merge venue rows that Google Maps confirms are the same place.

docs/TRD.md keeps ambiguity as separate rows because "merging later is safe, a
wrong merge is not". This is the "later": a shared `place_id` is not a guess, it
is Google stating the two names resolve to one establishment. That is the only
evidence accepted here.

Name similarity is deliberately NOT accepted. "Village Park" and "Village Park
Nasi Lemak" look mergeable and might be two businesses at one address; the
ranking layer collapses those for a single response, which is reversible,
whereas this is not.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db


def duplicate_groups(con):
    rows = con.execute("""
        select place_id, array_agg(id order by created_at) ids, array_agg(name order by created_at) names
        from venue
        where place_id is not null
        group by place_id
        having count(*) > 1
    """).fetchall()
    return rows


def merge_group(con, keep_id, drop_ids, names):
    """Fold every mention, alias and embedding onto the surviving row."""
    # Aliases: every name the place was written under stays discoverable.
    con.execute(
        """update venue set aliases = (
               select array_agg(distinct a) from unnest(aliases || %s::text[]) a
               where a is not null and a <> name
           ) where id = %s""",
        (names, keep_id),
    )
    # A mention already pointing at the survivor for the same post would violate
    # the (post_id, venue_id) unique key, so drop those rather than re-point them.
    con.execute(
        """delete from mention m
           where m.venue_id = any(%s)
             and exists (select 1 from mention k
                         where k.venue_id = %s and k.post_id = m.post_id)""",
        (drop_ids, keep_id),
    )
    con.execute('update mention set venue_id = %s where venue_id = any(%s)', (keep_id, drop_ids))
    # Embeddings are recomputed from the merged document, so stale ones must go.
    con.execute('delete from venue_embedding where venue_id = any(%s)', (drop_ids + [keep_id],))
    con.execute('delete from venue where id = any(%s)', (drop_ids,))


def run(dry_run=False):
    merged = groups = 0
    with db.connect(direct=True) as con:
        for g in duplicate_groups(con):
            ids, names = list(g['ids']), list(g['names'])
            keep, drop = ids[0], ids[1:]
            groups += 1
            merged += len(drop)
            print(f'  {names[0]!r} <- {names[1:]}  ({g["place_id"][:24]}…)', flush=True)
            if not dry_run:
                merge_group(con, keep, drop, names)
                con.commit()
    return groups, merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    groups, merged = run(a.dry_run)
    verb = 'would merge' if a.dry_run else 'merged'
    print(f'{verb} {merged} duplicate row(s) across {groups} place(s)')
    if not a.dry_run and merged:
        print('re-run `python ingest/pipeline.py --skip-geocode` to rebuild embeddings')


if __name__ == '__main__':
    main()

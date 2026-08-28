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
from makanlah.text import NOT_A_VENUE, normalize


def renormalize(con):
    """Recompute name_normalized, and drop rows the rules now reject.

    normalize() is the schema's dedup key, so changing it leaves every existing
    row keyed on the old rules. Adding 茶餐室 to the generics did nothing for the
    华阳 / 华阳冰室 rows already stored.
    """
    rows = con.execute('select id, name, name_normalized from venue').fetchall()
    renamed = dropped = 0
    for r in rows:
        norm = normalize(r['name'])
        if not norm or norm in NOT_A_VENUE:
            # A pronoun or a district that the extractor let through. Its
            # mentions cascade: they described a venue that does not exist.
            con.execute('delete from venue where id = %s', (r['id'],))
            dropped += 1
            print(f'  dropped {r["name"]!r} (not a venue)', flush=True)
            continue
        if norm != r['name_normalized']:
            con.execute('update venue set name_normalized = %s where id = %s', (norm, r['id']))
            renamed += 1
    con.commit()
    return renamed, dropped


def name_groups(con):
    """Venues sharing an exact normalized name.

    This is the schema's own join key, not the loose containment matching
    docs/TRD.md rules out: 'Village Park' and 'Village Park Nasi Lemak' do NOT
    collide here, because their normalized names differ.
    """
    return con.execute("""
        select name_normalized as key, array_agg(id order by created_at) ids,
               array_agg(name order by created_at) names
        from venue group by name_normalized having count(*) > 1
    """).fetchall()


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
    # Keep exactly ONE mention per post across the whole group, then re-point it.
    #
    # Checking only against the survivor is not enough: when three venues merge,
    # two of the DROPPED rows can each hold a mention of the same post, and
    # re-pointing both violates (post_id, venue_id). Measured on a real 3-way
    # merge, which failed mid-run. The survivor's own row wins where one exists,
    # otherwise the best-evidenced duplicate does.
    group = [keep_id, *drop_ids]
    con.execute(
        """delete from mention m
           where m.venue_id = any(%s)
             and m.id <> (
               select k.id from mention k
               where k.venue_id = any(%s) and k.post_id = m.post_id
               order by (k.venue_id = %s) desc,
                        k.confidence desc nulls last,
                        k.excerpt is not null desc,
                        k.id
               limit 1
             )""",
        (group, group, keep_id),
    )
    con.execute('update mention set venue_id = %s where venue_id = any(%s)', (keep_id, drop_ids))
    # Embeddings are recomputed from the merged document, so stale ones must go.
    con.execute('delete from venue_embedding where venue_id = any(%s)', (drop_ids + [keep_id],))
    con.execute('delete from venue where id = any(%s)', (drop_ids,))


def preview_name_groups(con):
    """What --by-name would merge, computed in memory.

    A dry run must not write, but name_groups() reads the STORED key, which is
    the old one until renormalize() has run. Previewing against the stored key
    reports nothing and then the real run merges rows, which is the shape of a
    dry run nobody should trust.
    """
    rows = con.execute('select id, name, created_at from venue order by created_at').fetchall()
    groups, rejected = {}, []
    for r in rows:
        norm = normalize(r['name'])
        if not norm or norm in NOT_A_VENUE:
            rejected.append(r['name'])
            continue
        groups.setdefault(norm, {'key': norm, 'ids': [], 'names': []})
        groups[norm]['ids'].append(r['id'])
        groups[norm]['names'].append(r['name'])
    for n in rejected:
        print(f'  would drop {n!r} (not a venue)', flush=True)
    return [g for g in groups.values() if len(g['ids']) > 1]


def _groups_for(con, dry_run, by_name):
    """Pick the grouping strategy without computing the one we did not ask for.

    preview_name_groups prints what it would drop, so calling it in place_id mode
    would print warnings about a merge that is not happening.
    """
    if not by_name:
        return duplicate_groups(con)
    return preview_name_groups(con) if dry_run else name_groups(con)


def run(dry_run=False, by_name=False):
    merged = groups = 0
    with db.connect(direct=True) as con:
        if by_name and not dry_run:
            renamed, dropped = renormalize(con)
            print(f'  re-normalized {renamed}, dropped {dropped}', flush=True)

        rows = _groups_for(con, dry_run, by_name)
        for g in rows:
            ids, names = list(g['ids']), list(g['names'])
            keep, drop = ids[0], ids[1:]
            groups += 1
            merged += len(drop)
            label = g['key'] if by_name else g['place_id'][:24] + '…'
            print(f'  {names[0]!r} <- {names[1:]}  ({label})', flush=True)
            if not dry_run:
                merge_group(con, keep, drop, names)
                con.commit()
    return groups, merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument(
        '--by-name',
        action='store_true',
        help="re-normalize, then merge on the schema's exact name key rather than place_id",
    )
    a = ap.parse_args()
    groups, merged = run(a.dry_run, a.by_name)
    verb = 'would merge' if a.dry_run else 'merged'
    print(f'{verb} {merged} duplicate row(s) across {groups} place(s)')
    if not a.dry_run and merged:
        print('re-run `python ingest/pipeline.py --skip-geocode` to rebuild embeddings')


if __name__ == '__main__':
    main()

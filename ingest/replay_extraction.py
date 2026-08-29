"""Re-extract posts whose excerpts say nothing, using the current prompt.

Reads the raw cache already in `source_post`. **It never touches a platform**, so
it costs model quota and nothing else -- which is the property `raw_payload` was
kept for (docs/TRD.md).

Why a replay is needed at all: the extraction prompt asked for "a VERBATIM span
copied from the post" and never said the span had to argue anything, so on a
RedNote listicle -- a pin line, then the opinion -- it took the pin line (#25).
The prompt now asks for the opinion, and `repair_excerpt` no longer falls back to
a window at the venue name, which used to put the address straight back.

**A mention whose new excerpt says nothing is not written.** That is the owner's
policy, and PRODUCT.md's: a ranked entry with no real post behind it is a
hallucination with a rating, and an excerpt that only locates the place is the
same claim wearing a citation. A venue left with no mentions appears in the
`uncited_venue` view and is unrankable, which is the correct outcome rather than
a failure.

Each post is replayed in its own transaction and the old mentions are deleted
only after the new extraction has succeeded, so a mid-run failure leaves that
post exactly as it was.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import config, db, models  # noqa: E402
from makanlah.excerpts import argues  # noqa: E402
from makanlah.text import NOT_A_VENUE, normalize  # noqa: E402


def candidates(con):
    """Posts carrying at least one mention that says nothing."""
    rows = con.execute("""
        select p.id as post_id, p.raw_text, v.name, v.aliases, m.excerpt
        from mention m
        join source_post p on p.id = m.post_id
        join venue v on v.id = m.venue_id
        where p.platform = 'rednote' and p.raw_text is not null
    """).fetchall()
    bad = {r['post_id'] for r in rows if not argues(r['excerpt'] or '', [r['name'], *(r['aliases'] or [])])}
    texts = {r['post_id']: r['raw_text'] for r in rows}
    return [(pid, texts[pid]) for pid in bad]


def replay_one(con, post_id, text, stats):
    """Returns the number of mentions written, or None if nothing was changed."""
    try:
        venues, model = models.extract(text)
    except Exception as e:
        stats['extract_failed'] += 1
        print(f'  extract failed {post_id}: {str(e)[:90]}', flush=True)
        return None

    kept = []
    for v in venues:
        name = (v.get('name') or '').strip()
        norm = normalize(name)
        if not norm or norm in NOT_A_VENUE:
            continue
        aliases = [a for a in (v.get('aliases') or []) if a]
        excerpt, origin = models.repair_excerpt(v.get('excerpt'), name, aliases, text)
        if not excerpt or not argues(excerpt, [name, *aliases]):
            stats['dropped_no_testimony'] += 1
            continue
        kept.append((name, norm, aliases, v, excerpt, origin))

    # Only now is anything destroyed.
    con.execute('delete from mention where post_id = %s', (post_id,))
    written = 0
    for name, norm, aliases, v, excerpt, origin in kept:
        venue_id = db.upsert_venue(con, name=name, name_normalized=norm, aliases=aliases, area=v.get('area'))
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
            written += 1
        stats[f'excerpt_{origin}'] += 1
    db.mark_extracted(con, post_id, model)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='write; otherwise report only')
    ap.add_argument('--limit', type=int, default=None, help='replay at most this many posts')
    args = ap.parse_args()

    stats = Counter()
    with db.connect(direct=True) as con:
        todo = candidates(con)
        if args.limit:
            todo = todo[: args.limit]
        before = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where p.platform = 'rednote'
        """).fetchone()['n']
        print(f'{len(todo)} posts carry a mention that says nothing; {before} rednote mentions now')
        print(f'extraction lane: {config.settings().extract_model}')

        if not args.apply:
            print('dry run; pass --apply to write')
            return 0

        for i, (post_id, text) in enumerate(todo, 1):
            written = replay_one(con, post_id, text, stats)
            if written is None:
                con.rollback()
                continue
            con.commit()
            stats['posts'] += 1
            stats['mentions'] += written
            print(f'  [{i}/{len(todo)}] {post_id} -> {written} mention(s)', flush=True)

        after = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where p.platform = 'rednote'
        """).fetchone()['n']
        uncited = con.execute('select count(*) n from uncited_venue').fetchone()['n']
        orphan = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where position(m.excerpt in p.raw_text) = 0
        """).fetchone()['n']

    print(f'\nposts replayed {stats["posts"]}, extraction failures {stats["extract_failed"]}')
    print(f'mentions written {stats["mentions"]}, dropped for saying nothing {stats["dropped_no_testimony"]}')
    print(f'rednote mentions {before} -> {after}')
    print(f'uncited venues now {uncited}   non-verbatim excerpts {orphan}')
    return 1 if orphan else 0


if __name__ == '__main__':
    raise SystemExit(main())

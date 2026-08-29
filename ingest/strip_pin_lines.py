"""Drop the pin line from a RedNote excerpt when testimony is sitting under it.

RedNote posts are listicles: a location line, then the opinion.

    📍店名：香港楼
    👉 必点咖喱鸭丝粥！浓郁顺滑真的香迷糊了

The extractor takes the first line. It satisfies every invariant -- verbatim
substring of raw_text, real post, real URL -- because the invariant asks whether
the text was written, never whether it argues anything (#25). Measured: RedNote
excerpts average 55.9 characters against Google Maps' 196.8, and 103 of 317 are
address-shaped, against 5 of 1388.

**Only `mention.excerpt` is rewritten, never `source_post.raw_text`.** The pin
line really is in the post, and raw_text is the verbatim record. The trigger
requiring excerpt to be a substring of raw_text still holds for free: removing a
prefix of a contiguous substring leaves a suffix, which is contiguous in the same
place. That is why this needs none of the ordering care
`strip_truncation.py` needed.

**This repairs 32 of the 103.** The other 71 are excerpts where the pin line is
the whole thing and there is no testimony to fall back to; those need
re-extraction from the raw cache, and are left untouched rather than blanked.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db  # noqa: E402
from makanlah.excerpts import MIN_REMAINDER, strip_pins, weight  # noqa: E402, F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='write; otherwise report only')
    args = ap.parse_args()

    with db.connect(direct=True) as con:
        rows = con.execute("""
            select m.id, m.excerpt from mention m join source_post p on p.id = m.post_id
            where p.platform = 'rednote' and m.excerpt is not null
        """).fetchall()

        edits = [(r['id'], s) for r in rows if (s := strip_pins(r['excerpt'])) is not None]
        print(f'{len(rows)} rednote excerpts, {len(edits)} carry testimony under a pin line')

        if not args.apply:
            for _, s in edits[:5]:
                print(f'  would become: {s[:70]!r}')
            print('dry run; pass --apply to write')
            return 0

        for mid, new in edits:
            con.execute('update mention set excerpt = %s where id = %s', (new, mid))
        con.commit()
        print(f'rewrote {len(edits)} excerpts')

        # Verified with checks this script does not own. The orphan count is the
        # database's own invariant, and the length/address counts use a different
        # expression from PIN_LINE -- measuring a fix with the fix's own
        # definition is how strip_truncation.py's first pass reported zero while
        # 295 excerpts were still marked.
        orphan = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where position(m.excerpt in p.raw_text) = 0
        """).fetchone()['n']
        stats = con.execute("""
            select count(*) n, avg(length(m.excerpt)) len,
                   sum(case when m.excerpt ~ '^[[:space:]]*📍' then 1 else 0 end) pinned
            from mention m join source_post p on p.id = m.post_id where p.platform = 'rednote'
        """).fetchone()
        print(f'non-verbatim excerpts: {orphan}')
        print(f'rednote now: {stats["n"]} excerpts, mean {stats["len"]:.1f} chars, {stats["pinned"]} still pin-led')
        return 1 if orphan else 0


if __name__ == '__main__':
    raise SystemExit(main())

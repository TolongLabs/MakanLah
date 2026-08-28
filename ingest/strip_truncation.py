"""Remove Google Maps' own "… More" control from captured text.

The scraper now expands reviews before reading (ingest/gmaps.py), so new
captures are clean. This repairs what was already stored: 1036 of 1388 Google
Maps excerpts ended in the marker, which reached users inside a citation
presented as the writer's verbatim words.

Order matters. `mention.excerpt` must be a substring of `source_post.raw_text`,
enforced by a trigger, so raw_text is stripped FIRST and excerpts second -- the
stripped excerpt is still a substring of the stripped post.

This does NOT recover the truncated text; that is lost until those places are
re-captured. It removes the chrome, not the cause.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db  # noqa: E402

PATTERN = r'(…|\.\.\.)[[:space:]]*More[[:space:]]*$'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='write; otherwise report only')
    args = ap.parse_args()

    with db.connect(direct=True) as con:
        posts = con.execute('select count(*) n from source_post where raw_text ~ %s', (PATTERN,)).fetchone()['n']
        mentions = con.execute('select count(*) n from mention where excerpt ~ %s', (PATTERN,)).fetchone()['n']
        print(f'{posts} posts and {mentions} excerpts carry the marker')

        if not args.apply:
            print('dry run; pass --apply to write')
            return 0

        p = con.execute(
            "update source_post set raw_text = regexp_replace(raw_text, %s, '') where raw_text ~ %s", (PATTERN, PATTERN)
        ).rowcount
        m = con.execute(
            "update mention set excerpt = regexp_replace(excerpt, %s, '') where excerpt ~ %s", (PATTERN, PATTERN)
        ).rowcount
        con.commit()
        print(f'stripped {p} posts and {m} excerpts')

        left = con.execute('select count(*) n from mention where excerpt ~ %s', (PATTERN,)).fetchone()['n']
        orphan = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where position(m.excerpt in p.raw_text) = 0
        """).fetchone()['n']
        print(f'remaining marked excerpts: {left}   non-verbatim excerpts: {orphan}')
        return 1 if (left or orphan) else 0


if __name__ == '__main__':
    raise SystemExit(main())

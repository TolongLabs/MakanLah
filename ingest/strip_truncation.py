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

# Google Maps emits its control three ways: after an ellipsis, after a full
# stop, and after a bare word with no punctuation at all ("Pricing ok More").
# The first pass only handled the ellipsis form and left 295 excerpts marked --
# and reported success, because it counted with the same pattern it stripped
# with. Measuring a fix with the fix's own definition proves nothing.
#
# Two guards make the wider pattern safe, both verified against the corpus:
#   - CASE SENSITIVE. One excerpt genuinely ends in lower-case "more"; zero end
#     in capital "More" as a real word (a real one would carry punctuation, and
#     no excerpt matches "More" followed by punctuation).
#   - PLATFORM SCOPED. All 295 are google_maps. RedNote text is never touched.
PATTERN = r'([[:space:]]*(…|\.\.\.)[[:space:]]*|[[:space:]]+)More[[:space:]]*$'
PLATFORM = 'google_maps'


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
            """update source_post set raw_text = regexp_replace(raw_text, %s, '')
               where platform = %s and raw_text ~ %s""",
            (PATTERN, PLATFORM, PATTERN),
        ).rowcount
        m = con.execute(
            """update mention set excerpt = regexp_replace(excerpt, %s, '')
               where excerpt ~ %s
                 and exists (select 1 from source_post p where p.id = mention.post_id and p.platform = %s)""",
            (PATTERN, PATTERN, PLATFORM),
        ).rowcount
        con.commit()
        print(f'stripped {p} posts and {m} excerpts')

        # Deliberately a DIFFERENT pattern from the one used to strip. Verifying a
        # fix with the fix's own definition is how the first pass reported zero
        # while 295 excerpts still ended in the marker.
        left = con.execute("select count(*) n from mention where excerpt ~ '[[:space:]]More[[:space:]]*$'").fetchone()[
            'n'
        ]
        orphan = con.execute("""
            select count(*) n from mention m join source_post p on p.id = m.post_id
            where position(m.excerpt in p.raw_text) = 0
        """).fetchone()['n']
        print(f'remaining marked excerpts: {left}   non-verbatim excerpts: {orphan}')
        return 1 if (left or orphan) else 0


if __name__ == '__main__':
    raise SystemExit(main())

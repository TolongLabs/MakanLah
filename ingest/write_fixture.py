"""Write the redacted fixture set to docs/source/.

docs/source/ is committed and append-only, so everything identifying or
credential-bearing is stripped before it is written:

  - `xsec_token` is a live request credential, and never appears here
  - author handles identify real people, and become a stable salted hash
  - image URLs carry per-request signatures, and are dropped entirely

Post ids and post URLs stay. They are public, and without them the capture
cannot serve as the fixture set docs/TRD.md requires the tests to run against.

The assertions at the end are not checks, they are the point: a token or a real
handle reaching a committed file is a credential leak.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'source'
SALT = 'makanlah-spike-capture'
KEYISH = re.compile(r'\bsk-[A-Za-z0-9_-]{16,}')


def anon(handle):
    if not handle:
        return None
    return 'author_' + hashlib.sha256((SALT + handle).encode()).hexdigest()[:10]


def build(limit, platform='rednote'):
    with db.connect() as con:
        posts = con.execute(
            """select * from source_post where platform = %s
               order by captured_at limit %s""",
            (platform, limit),
        ).fetchall()
        out = []
        for p in posts:
            ms = con.execute(
                """select m.*, v.name, v.name_normalized, v.aliases, v.area, v.lat, v.lng, v.address
                   from mention m join venue v on v.id = m.venue_id
                   where m.post_id = %s order by m.confidence desc nulls last""",
                (p['id'],),
            ).fetchall()
            out.append(
                {
                    'platform': p['platform'],
                    'platform_post_id': p['platform_post_id'],
                    'url': p['url'],
                    'author_handle': anon(p['author_handle']),
                    'posted_at': p['posted_at_raw'],
                    'langs': list(p['langs']),
                    'raw_text': p['raw_text'],
                    'mentions': [
                        {
                            'venue_name': m['name'],
                            'venue_name_normalized': m['name_normalized'],
                            'aliases': list(m['aliases'] or []),
                            'area': m['area'],
                            'lat': m['lat'],
                            'lng': m['lng'],
                            'address': m['address'],
                            'dishes': list(m['dishes'] or []),
                            'sentiment': m['sentiment'],
                            'price_band': m['price_band'],
                            'excerpt': m['excerpt'],
                            'excerpt_is_substring': bool(
                                m['excerpt'] and p['raw_text'] and m['excerpt'] in p['raw_text']
                            ),
                            'extractor_model': m['extractor_model'],
                            'confidence': m['confidence'],
                        }
                        for m in ms
                    ],
                }
            )
    return posts, out


def write(path, limit=14, platform='rednote'):
    OUT.mkdir(parents=True, exist_ok=True)
    posts, fixtures = build(limit, platform)
    path.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n')

    blob = path.read_text()
    assert 'xsec_token' not in blob, 'a request token reached the capture'
    assert not KEYISH.search(blob), 'an api-key-shaped string reached the capture'
    for p in posts:
        if p['author_handle']:
            assert p['author_handle'] not in blob, 'a raw author handle reached the capture'
    return len(fixtures), sum(len(f['mentions']) for f in fixtures)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default='2026-08-27', help='the capture date in the filename')
    ap.add_argument('--limit', type=int, default=14)
    ap.add_argument('--platform', default='rednote')
    a = ap.parse_args()
    path = OUT / f'{a.date}-{a.platform}-kl-spike.json'
    n, m = write(path, a.limit, a.platform)
    print(f'wrote {path.relative_to(ROOT)}: {n} posts, {m} mentions, redacted')


if __name__ == '__main__':
    main()

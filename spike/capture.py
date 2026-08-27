"""Write the redacted spike capture to docs/source/.

docs/source/ is committed and append-only, so everything identifying or
credential-bearing is stripped before it is written:

  - xsec_token is a live request credential -> removed
  - author handles identify real people -> replaced with a stable salted hash
  - image URLs carry per-request signatures -> dropped entirely

Post ids and post URLs stay. They are public, and without them the capture
cannot serve as the fixture set the tests in docs/TRD.md require.
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import schema

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'source'
SALT = 'makanlah-spike-capture'


def anon(handle):
    if not handle:
        return None
    return 'author_' + hashlib.sha256((SALT + handle).encode()).hexdigest()[:10]


def write(db_path, limit=12):
    con = schema.connect(str(db_path))
    posts = con.execute('select * from source_post order by captured_at limit ?', (limit,)).fetchall()

    stamp = date.today().isoformat()
    OUT.mkdir(parents=True, exist_ok=True)

    fixtures = []
    for p in posts:
        ms = con.execute(
            """select m.*, v.name, v.name_normalized, v.aliases, v.area,
                                   v.lat, v.lng, v.address
                            from mention m join venue v on v.id = m.venue_id
                            where m.post_id = ?""",
            (p['id'],),
        ).fetchall()
        fixtures.append(
            {
                'platform': p['platform'],
                'platform_post_id': p['platform_post_id'],
                'url': p['url'],
                'author_handle': anon(p['author_handle']),
                'posted_at': p['posted_at'],
                'langs': json.loads(p['langs']),
                'raw_text': p['raw_text'],
                'mentions': [
                    {
                        'venue_name': m['name'],
                        'venue_name_normalized': m['name_normalized'],
                        'aliases': json.loads(m['aliases']),
                        'area': m['area'],
                        'lat': m['lat'],
                        'lng': m['lng'],
                        'address': m['address'],
                        'dishes': json.loads(m['dishes']),
                        'sentiment': m['sentiment'],
                        'price_band': m['price_band'],
                        'excerpt': m['excerpt'],
                        'excerpt_is_substring': bool(m['excerpt'] and p['raw_text'] and m['excerpt'] in p['raw_text']),
                        'extractor_model': m['extractor_model'],
                        'confidence': m['confidence'],
                    }
                    for m in ms
                ],
            }
        )

    path = OUT / f'{stamp}-rednote-kl-spike.json'
    path.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n')

    # A token or a raw handle reaching a committed file is a credential leak, so
    # this is an assertion rather than a check.
    blob = path.read_text()
    assert 'xsec_token' not in blob, 'a request token reached the capture'
    for p in posts:
        if p['author_handle']:
            assert p['author_handle'] not in blob, 'a raw author handle reached the capture'
    return path, len(fixtures), sum(len(f['mentions']) for f in fixtures)


if __name__ == '__main__':
    db = ROOT / 'data' / 'corpus' / 'spike.db'
    path, n, m = write(db, limit=int(sys.argv[1]) if len(sys.argv) > 1 else 12)
    print(f'wrote {path.relative_to(ROOT)}: {n} posts, {m} mentions, redacted')

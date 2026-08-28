"""Capture RedNote posts to the raw cache.

Separate from pipeline.py on purpose: fetching is slow, rate-limited and can
fail halfway, while extraction is fast and replayable. Keeping raw captures on
disk means a schema or prompt change costs nothing to re-run, where re-scraping
costs a rate limit and possibly a session (docs/TRD.md, "store raw before
extraction, always").
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import cdp, rednote

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data' / 'raw' / 'rednote_notes.jsonl'

# Spread across cuisine, area and language. A keyword list that is all Chinese
# returns an all-Chinese corpus and the language coverage looks better than it is.
KEYWORDS = [
    '吉隆坡美食',
    '吉隆坡餐厅推荐',
    'KL food',
    'Kuala Lumpur restaurant',
    '吉隆坡必吃',
    'KL cafe recommendation',
    '吉隆坡肉骨茶',
    'makan sedap Kuala Lumpur',
    '吉隆坡早餐',
    'KL hidden gem food',
    '八打灵美食',
    'nasi lemak KL',
    '吉隆坡火锅',
    '吉隆坡日料',
    'KL brunch',
    '吉隆坡马来餐',
    '吉隆坡印度餐',
    'KL supper',
    '吉隆坡甜品',
    'Bangsar food',
    'Mont Kiara restaurant',
    'SS15 food',
    '吉隆坡海鲜',
    'KL banana leaf rice',
    '吉隆坡烧烤',
    'Cheras food',
    'restoran halal Kuala Lumpur',
    '吉隆坡茶餐室',
]


def load_cache():
    have = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            try:
                d = json.loads(line)
                have[d['note_id']] = d
            except json.JSONDecodeError:
                continue
    return have


async def capture(target):
    if not cdp.alive():
        raise SystemExit('CDP is not up. Run: scripts/chrome-session.sh start')
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    have = load_cache()
    print(f'cache holds {len(have)} notes, target {target}', flush=True)
    want = target - len(have)
    if want <= 0:
        print('target already met')
        return len(have)

    fh = CACHE.open('a')

    def on_note(d):
        if d['note_id'] not in have:
            have[d['note_id']] = d
            fh.write(json.dumps(d, ensure_ascii=False) + '\n')
            fh.flush()

    try:
        await rednote.collect(KEYWORDS, want, on_note=on_note, skip=set(have))
    finally:
        fh.close()
    return len(have)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', type=int, default=200, help='total notes wanted in the cache')
    a = ap.parse_args()
    total = asyncio.run(capture(a.target))
    print(f'cache now holds {total} notes')


if __name__ == '__main__':
    main()

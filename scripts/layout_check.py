"""Assert the corroboration pair actually splits, in a real browser.

Why this is not a vitest test. jsdom has no layout engine, so `specimen.test.ts`
can assert everything the exhibit *says* -- no duplicate post, two platforms behind
it, a real post under every excerpt -- and nothing about whether it *splits*. The
one property that took four measured ratios to buy is the one property those tests
structurally cannot see.

Why it is worth a browser at all. A container query falling back is invisible: the
layout stays valid, renders fine, and passes every assertion written against the
DOM. That is exactly how #20 shipped a corroboration layout that never rendered
once, through four green CI runs and a dozen screenshots. The evidence pair is the
product's central claim, so the claim gets a check that can actually fail.

The headroom is why this exists rather than a comment. At the `--page` cap the
specimen's content box clears the 34rem bar by about three pixels. Three. A small
change to the specimen padding, the page cap, the hero gutter or the border drops
the pair silently back to one column, and nothing else in the repo would notice.

Run it against any server:

    cd web && bun run build && bunx vite preview --port 4188 &
    WEB_BASE=http://127.0.0.1:4188 uv run python scripts/layout_check.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import websockets

PORT = int(os.environ.get('CDP_PORT', '9380'))
BASE = os.environ.get('WEB_BASE', 'http://127.0.0.1:4188')
BAR_REM = 34

# (width, height, expected track count or None to report without asserting, note)
# The plate moved out of the hero and into the posts section, which changed the
# geometry these widths describe. The old 1024 case was a documented hole -- the hero
# split there but the page had not reached its cap, so the pair stacked and the note
# said "by design". The section is full width until 76rem, so that hole is gone and
# 1024 is now an assertion rather than a report.
CASES = [
    (390, 844, 1, 'phone: one column on purpose, 34rem cannot fit two'),
    (834, 1112, 2, 'tablet: the section is one column so the plate is full width'),
    (1024, 900, 2, 'laptop: still one column, still full width. This used to stack'),
    (1280, 900, 2, 'page cap reached and the section splits; the plate holds 42rem'),
    (1440, 900, 2, 'nothing changes above the cap'),
]

PROBE = """JSON.stringify((() => {
  const de = document.documentElement
  const spec = document.querySelector('.specimen')
  const pair = document.querySelector('.evidence-pair')
  if (!spec || !pair) return { loaded: false }
  const cs = getComputedStyle(spec)
  const content = spec.getBoundingClientRect().width
    - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
    - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth)
  const chips = [...document.querySelectorAll('.evidence-pair .chip')].map(c => c.textContent.trim())
  return {
    loaded: true,
    tracks: getComputedStyle(pair).gridTemplateColumns.split(' ').filter(Boolean).length,
    content: Math.round(content * 100) / 100,
    bar: BAR * parseFloat(getComputedStyle(de).fontSize),
    docWidth: de.scrollWidth,
    viewWidth: de.clientWidth,
    platforms: [...new Set(chips)],
    excerpts: [...document.querySelectorAll('.evidence-pair .excerpt')].length
  }
})())""".replace('BAR', str(BAR_REM))


async def probe_all(cmd) -> int:
    failures = 0
    for width, height, want, note in CASES:
        await cmd(
            'Emulation.setDeviceMetricsOverride',
            {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': width < 500},
        )
        await cmd('Page.navigate', {'url': f'{BASE}/'})
        await asyncio.sleep(2.2)
        result = await cmd('Runtime.evaluate', {'expression': PROBE, 'returnByValue': True})
        data = json.loads(result['result']['value'])

        # The precondition, asserted rather than assumed. A check that cannot tell
        # "measured clean" from "measured nothing" is the failure it exists to catch:
        # an earlier version of this harness reported clean against a stale module,
        # and then against an entirely different git worktree.
        if not data.get('loaded'):
            print(f'::error::{width}px: no .specimen or .evidence-pair on the page. Nothing was measured.')
            failures += 1
            continue
        if data['excerpts'] < 2 or len(data['platforms']) < 2:
            print(
                f'::error::{width}px: the pair has {data["excerpts"]} excerpts across '
                f'{len(data["platforms"])} platforms. The exhibit is not corroborated, so its layout proves nothing.'
            )
            failures += 1
            continue

        margin = round(data['content'] - data['bar'], 2)
        verdict = 'ok'
        if want is not None and data['tracks'] != want:
            verdict = 'FAIL'
            failures += 1
        print(
            f'{verdict:4} {width:>5}px  tracks={data["tracks"]}'
            f'{"" if want is None else f" (want {want})"}  '
            f'specimen-content={data["content"]}  bar={data["bar"]:.0f}  margin={margin:+.2f}px'
        )
        print(f'         {note}')

        if want == 2 and data['tracks'] == 2 and margin < 8:
            print(
                f'::warning::{width}px: the pair clears the {BAR_REM}rem bar by {margin:.2f}px. '
                'A small change to the specimen padding, the page cap, the hero gutter or the border '
                'drops it back to one column. That fallback is silent -- this check is the only thing that sees it.'
            )
        if data['docWidth'] > data['viewWidth'] + 1:
            print(f'::error::{width}px: document is {data["docWidth"]} wide in a {data["viewWidth"]} viewport.')
            failures += 1
    return failures


async def main() -> int:
    try:
        urllib.request.urlopen(f'{BASE}/', timeout=10).read(64)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f'::error::nothing is serving {BASE} ({error}). Build and preview the client first.')
        return 2

    chrome = subprocess.Popen(
        [
            os.environ.get('CHROME', 'google-chrome'),
            '--headless=new',
            f'--remote-debugging-port={PORT}',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--use-gl=angle',
            '--use-angle=swiftshader',
            f'--user-data-dir={os.environ.get("RUNNER_TEMP", "/tmp")}/layout-check-profile',
            'about:blank',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=2).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            print('::error::headless Chrome did not come up')
            return 2

        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list'))
        ws_url = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            seq = [0]

            async def cmd(method, params=None):
                seq[0] += 1
                await ws.send(json.dumps({'id': seq[0], 'method': method, 'params': params or {}}))
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), 60))
                    if msg.get('id') == seq[0]:
                        if 'error' in msg:
                            raise RuntimeError(f'{method}: {msg["error"]}')
                        return msg.get('result', {})

            await cmd('Page.enable')
            await cmd('Runtime.enable')
            failures = await probe_all(cmd)
    finally:
        chrome.kill()

    print()
    print('the evidence pair splits where it should' if not failures else f'{failures} layout assertions failed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

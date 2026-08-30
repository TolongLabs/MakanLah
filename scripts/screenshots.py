#!/usr/bin/env -S uv run --quiet --with websockets --with pillow python
"""Render every route at desktop, tablet and mobile, in both themes, to
docs/screenshots/<device>/. The directory is gitignored: it is regenerated on demand.

`--readme` instead writes a small curated set to docs/img/, which IS committed. The
full sweep is gitignored because a binary set that churns on every visual change does
not belong in review; three images the public README embeds are a different thing, and
a README pointing at files nobody can see is worse than no README image. Curated shots
are viewport-only rather than full-page, and re-encoded to WebP -- a 2x full-page PNG
of /discover is 4.9 MB, which is not something to put at the top of a landing page.

The mascot is a WebGL canvas and headless software rasterising paints it faint or not
at all, so treat the mascot region of these images as unverified. It is verified
separately: see the Live2D checks in the a11y sweep, which measure the canvas pixels.

Needs the dev server and the API up:
    cd web && bunx vite --port 5199 &
    scripts/dev-api.sh &
    scripts/screenshots.py
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websockets

PORT = 9370
BASE = os.environ.get('WEB_BASE', 'http://localhost:5199')
ROOT = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip()
OUT = os.path.join(ROOT, 'docs', 'screenshots')
PROFILE = '/tmp/makanlah-shots-profile'

# Three real breakpoint regimes rather than three arbitrary numbers. Desktop clears
# every min-width in the stylesheet; tablet sits above the 40rem option grid and below
# the 60rem discover rail, so the hero stacks and the rail is not a rail; mobile is
# below all of them. 360 is the narrowest width the design is tested at and 390 is what
# people actually hold, so mobile is shot at 390 and the a11y sweep covers 360.
DEVICES = [
    ('desktop', 1440, 900),
    ('tablet', 834, 1112),
    ('mobile', 390, 844),
]

VENUE_ID = os.environ.get('VENUE_ID', 'b9433fbc-7da1-49c6-94dc-16f51bc445f0')

ROUTES = [
    ('landing', '/', False),
    ('taste', '/taste', False),
    ('taste-step-4', '/taste', True),
    ('sign-in', '/sign-in', False),
    ('sign-up', '/sign-up', False),
    ('discover', '/discover', False),
    ('venue', f'/r/{VENUE_ID}', False),
    ('not-found', '/nowhere', False),
]

# What a stranger should see first: the evidence, at the two widths people read it on,
# in both themes because the palette is half the design. Not the wizard and not the
# landing hero -- the README already leads with og.png, and the claim it has to support
# is that a pick carries the post it came from.
README_SHOTS = [
    ('discover-desktop-light', '/discover', 1440, 900, 'light'),
    ('discover-desktop-dark', '/discover', 1440, 900, 'dark'),
    ('discover-phone-light', '/discover', 390, 844, 'light'),
]

# The sweep's craving is deliberately fuzzy, which is right for testing the "closest in
# meaning" fallback and wrong for a README: it leads with the product failing to match.
# `nasi lemak` returns eight exact matches, and it is the neutral choice for a public
# front page in a majority-Muslim country -- the chips still offer `pork` and the corpus
# still carries it, but which dish leads the README is an editorial call, not a claim.
README_PREFS = json.dumps({'craving': ['nasi lemak'], 'company': 'family', 'range_m': 0, 'mood': 'comfort'})

PREFS = json.dumps({'craving': ['nasi lemak sedap'], 'company': 'family', 'range_m': 0, 'mood': 'comfort'})

# Walk the wizard to its last step so the ticks, the counter and the budget row are
# all in shot. Clicks the first option on each of the first three steps.
ADVANCE = """
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let step = 0; step < 3; step++) {
    const panel = [...document.querySelectorAll('.step-panel')].find(p => !p.hidden);
    if (!panel) break;
    const opt = panel.querySelector('.option input');
    if (opt) { opt.click(); await sleep(120); }
    const next = [...document.querySelectorAll('.bottom-island button')]
      .find(b => b.textContent.trim() === 'Continue');
    if (!next || next.disabled) break;
    next.click();
    await sleep(320);
  }
  return document.querySelector('.island-counter')?.textContent ?? '';
})()
"""


async def main() -> int:
    chrome = subprocess.Popen(
        [
            'google-chrome',
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            # The mascot is a WebGL canvas. Without a software rasteriser, headless
            # paints it blank, and a screenshot set that quietly omits the mascot
            # misrepresents the build to whoever is eyeballing it.
            '--use-gl=swiftshader',
            '--enable-unsafe-swiftshader',
            '--hide-scrollbars',
            '--force-device-scale-factor=2',
            f'--remote-debugging-port={PORT}',
            f'--user-data-dir={PROFILE}',
            'about:blank',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=2).read()
            break
        except Exception:
            time.sleep(0.25)
    else:
        print('chrome did not start', file=sys.stderr)
        chrome.kill()
        return 1

    tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list'))
    ws_url = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
    written = 0

    async with websockets.connect(ws_url, max_size=300 * 1024 * 1024) as ws:
        seq = [0]

        async def cmd(method, params=None):
            seq[0] += 1
            await ws.send(json.dumps({'id': seq[0], 'method': method, 'params': params or {}}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 90))
                if msg.get('id') == seq[0]:
                    if 'error' in msg:
                        raise RuntimeError(f'{method}: {msg["error"]}')
                    return msg.get('result', {})

        await cmd('Page.enable')
        await cmd('Runtime.enable')
        # Seed on-origin once so /discover does not bounce to /taste.
        await cmd('Page.navigate', {'url': f'{BASE}/'})
        await asyncio.sleep(2)
        await cmd('Runtime.evaluate', {'expression': f'localStorage.setItem("makanlah.prefs", {json.dumps(PREFS)}); 1'})

        if '--readme' in sys.argv:
            import io

            from PIL import Image

            await cmd(
                'Runtime.evaluate',
                {'expression': f'localStorage.setItem("makanlah.prefs", {json.dumps(README_PREFS)}); 1'},
            )

            img_dir = os.path.join(ROOT, 'docs', 'img')
            os.makedirs(img_dir, exist_ok=True)
            for name, path, width, height, theme in README_SHOTS:
                await cmd(
                    'Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]}
                )
                await cmd(
                    'Emulation.setDeviceMetricsOverride',
                    {'width': width, 'height': height, 'deviceScaleFactor': 2, 'mobile': width < 700},
                )
                await cmd('Page.navigate', {'url': BASE + path})
                await asyncio.sleep(12 if path == '/discover' else 5)
                # Viewport only. A README image is a screenful; captureBeyondViewport
                # returns the whole scrolled page, which is where the 4.9 MB came from.
                shot = await cmd('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
                dest = os.path.join(img_dir, f'{name}.webp')
                Image.open(io.BytesIO(base64.b64decode(shot['data']))).save(dest, 'WEBP', quality=82, method=6)
                written += 1
                print(f'{name:<24} {width}x{height} {theme:<5} {os.path.getsize(dest) // 1024:>5} KB')
            chrome.terminate()
            print(f'\n{written} curated screenshots in {img_dir}')
            return 0

        for device, width, height in DEVICES:
            os.makedirs(os.path.join(OUT, device), exist_ok=True)
            for theme in ('light', 'dark'):
                await cmd(
                    'Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]}
                )
                await cmd(
                    'Emulation.setDeviceMetricsOverride',
                    {'width': width, 'height': height, 'deviceScaleFactor': 2, 'mobile': width < 700},
                )
                for name, path, advance in ROUTES:
                    await cmd('Page.navigate', {'url': BASE + path})
                    # The re-rank is a live model call, so /discover genuinely waits.
                    await asyncio.sleep(12 if path == '/discover' else 5)
                    if advance:
                        await cmd(
                            'Runtime.evaluate', {'expression': ADVANCE, 'awaitPromise': True, 'returnByValue': True}
                        )
                        await asyncio.sleep(1)
                    shot = await cmd('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
                    dest = os.path.join(OUT, device, f'{name}-{theme}.png')
                    with open(dest, 'wb') as fh:
                        fh.write(base64.b64decode(shot['data']))
                    written += 1
                    print(f'{device:<8} {theme:<5} {name:<13} {os.path.getsize(dest) // 1024:>5} KB')

    chrome.terminate()
    print(f'\n{written} screenshots in {OUT}')
    return 0


sys.exit(asyncio.run(main()))

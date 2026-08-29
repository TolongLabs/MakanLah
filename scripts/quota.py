#!/usr/bin/env -S uv run --quiet --with websockets python
"""Read free-quota state for the lanes this project actually uses.

Reads the ModelStudio console through the CDP Chrome that `chrome-session.sh`
brings up, because the console's own API needs a session token that is not the
DashScope key. Start it first, and stay signed in:

    scripts/chrome-session.sh start      # then sign in to Alibaba Cloud once

**This scrapes a dashboard, so it will break when the console is redesigned.**
That is an accepted cost: the alternative is a number nobody checks until a card
is charged. When it breaks, the failure is loud and the fix is a selector.

Why it matters, measured 2026-08-29: `qwen3.8-flash` -- the lane behind every
/recommend -- reads `Not Supported`, meaning no free quota at all, while the
extraction lane still had 954,215 tokens. Nothing in the repo said so (#34).
"""

import asyncio
import json
import sys
import urllib.request

import websockets

CONSOLE = 'https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=costing-balance'

# The lanes makanlah/config.py can resolve to, and which console tab each lives
# behind. The console splits LLM / Vision / Multimodal / Audio / Embedding, and a
# search only ever matches inside the active tab -- so an embedding model looked
# up under LLM reports "not listed", which reads exactly like "no quota".
LANES = (
    ('qwen3.8-flash', 'LLM'),
    ('qwen3.7-flash-2026-07-15', 'LLM'),
    ('qwen-plus-2025-07-28', 'LLM'),
    ('text-embedding-v3', 'Embedding'),
)

READ_ROWS = r"""
(() => {
  const rows = [...document.querySelectorAll('tr')]
    .map(r => r.innerText.replace(/\t/g, '').split('\n').map(s => s.trim()).filter(Boolean))
    .filter(c => c.length >= 2);
  return JSON.stringify(rows);
})()
"""


def _tab():
    try:
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=5))
    except OSError:
        sys.exit('no CDP on 9222 -- run: scripts/chrome-session.sh start')
    for t in tabs:
        if 'alibabacloud' in t.get('url', ''):
            return t
    sys.exit(f'no console tab open -- open {CONSOLE} in that window')


async def _tab_select(ws, mid, name):
    expr = f"""
      (() => {{
        const t = [...document.querySelectorAll('div,span,button,a')]
          .filter(e => e.children.length === 0 && e.textContent.trim() === {name!r});
        if (!t.length) return 'no-tab';
        t[0].click();
        return 'ok';
      }})()"""
    await ws.send(
        json.dumps({'id': mid, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}})
    )
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == mid:
            return m['result']['result'].get('value')


async def _search(ws, mid, term):
    """Type into the console's own filter, then read the table back."""
    expr = f"""
      (() => {{
        const i = document.querySelector('input[placeholder*="Search model" i]');
        if (!i) return 'no-search-box';
        const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        set.call(i, {term!r}); i.dispatchEvent(new Event('input', {{bubbles: true}}));
        i.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', bubbles: true}}));
        return 'ok';
      }})()"""
    await ws.send(
        json.dumps({'id': mid, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}})
    )
    while True:
        m = json.loads(await ws.recv())
        if m.get('id') == mid:
            return m['result']['result'].get('value')


async def main():
    tab = _tab()
    async with websockets.connect(tab['webSocketDebuggerUrl'], max_size=20_000_000) as ws:
        mid = 0
        active = None
        for lane, tab in LANES:
            if tab != active:
                mid += 1
                if await _tab_select(ws, mid, tab) == 'no-tab':
                    print(f'  (could not find the {tab} tab -- console layout changed?)')
                await asyncio.sleep(2)
                active = tab
            mid += 1
            if await _search(ws, mid, lane) == 'no-search-box':
                sys.exit('the console page is not the Free Quota view -- open it and retry')
            await asyncio.sleep(2.5)
            mid += 1
            await ws.send(
                json.dumps(
                    {
                        'id': mid,
                        'method': 'Runtime.evaluate',
                        'params': {'expression': READ_ROWS, 'returnByValue': True},
                    }
                )
            )
            while True:
                m = json.loads(await ws.recv())
                if m.get('id') == mid:
                    rows = json.loads(m['result']['result'].get('value') or '[]')
                    break
            hit = next((r for r in rows if r and r[0].strip() == lane), None)
            if not hit:
                print(f'  {lane:26s} not listed')
            elif 'Not Supported' in ' '.join(hit):
                print(f'  {lane:26s} NO FREE QUOTA -- every call is billed')
            else:
                print(f'  {lane:26s} {" | ".join(hit[1:4])}')


if __name__ == '__main__':
    asyncio.run(main())

"""CDP client. Drives the Chrome that scripts/chrome-session.sh brings up.

Every call is bounded. CDP interleaves events with responses, so a reply is
matched by id; if it never arrives -- the page navigated out from under the
execution context, or the tab crashed -- an unbounded recv() loop wedges the run
silently. Measured during the spike: a crashed tab froze a 50-note batch for 20
minutes with no error anywhere.
"""

import asyncio
import contextlib
import json
import urllib.request

import websockets

PORT = 9222


def new_tab(url='about:blank'):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/json/new?{url}', method='PUT')
    return json.load(urllib.request.urlopen(req))


def close_tab(tid):
    with contextlib.suppress(Exception):
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/close/{tid}').read()


def alive():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=5).read()
        return True
    except Exception:
        return False


class Page:
    def __init__(self, ws):
        self.ws = ws
        self._n = 0

    async def send(self, method, timeout=30.0, **params):
        self._n += 1
        want = self._n
        await self.ws.send(json.dumps({'id': want, 'method': method, 'params': params}))

        async def _reply():
            while True:
                msg = json.loads(await self.ws.recv())
                if msg.get('id') == want:
                    return msg

        msg = await asyncio.wait_for(_reply(), timeout=timeout)
        if 'error' in msg:
            raise RuntimeError(f'{method}: {msg["error"]}')
        return msg.get('result', {})

    async def goto(self, url, settle=6.0):
        await self.send('Page.navigate', url=url, timeout=45.0)
        await asyncio.sleep(settle)

    async def js(self, expression):
        r = await self.send('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        res = r.get('result', {})
        if res.get('subtype') == 'error':
            raise RuntimeError(res.get('description', 'js error'))
        return res.get('value')


class Session:
    def __init__(self, url='about:blank'):
        self.url = url

    async def __aenter__(self):
        self.tab = new_tab(self.url)
        self.ws = await websockets.connect(self.tab['webSocketDebuggerUrl'], max_size=100_000_000)
        return Page(self.ws)

    async def __aexit__(self, *exc):
        with contextlib.suppress(Exception):
            await self.ws.close()
        close_tab(self.tab['id'])

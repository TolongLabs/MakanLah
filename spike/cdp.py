"""CDP client for the spike. Drives the already-running Chrome from scripts/chrome-session.sh."""

import asyncio
import contextlib
import json
import urllib.request

import websockets

PORT = 9222


def _targets():
    return json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))


def new_tab(url='about:blank'):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/json/new?{url}', method='PUT')
    return json.load(urllib.request.urlopen(req))


def close_tab(tid):
    with contextlib.suppress(Exception):
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/close/{tid}').read()


class Page:
    def __init__(self, ws):
        self.ws = ws
        self._n = 0

    async def send(self, method, **params):
        self._n += 1
        await self.ws.send(json.dumps({'id': self._n, 'method': method, 'params': params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get('id') == self._n:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})

    async def goto(self, url, settle=6.0):
        await self.send('Page.navigate', url=url)
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
        await self.ws.close()
        close_tab(self.tab['id'])

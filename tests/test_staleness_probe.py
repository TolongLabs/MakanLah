"""The staleness probe, against a real socket.

No mock of urlopen. The failure this probe exists to catch is a live host answering
200 with the wrong body, so the content type has to travel through an actual HTTP
response for the test to mean anything -- a stubbed fetch would assert the shape of
the stub. The server is localhost on an ephemeral port, so the suite stays hermetic.
"""

import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from scripts import staleness_probe as probe

SPA_SHELL = '<!doctype html><html><body><div id="root"></div></body></html>'


def _serve(body, content_type):
    """A one-route host. Returns (base_url, shutdown)."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = body.encode()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}', server.shutdown


@pytest.fixture
def host():
    shutdowns = []

    def start(body, content_type='application/json'):
        url, stop = _serve(body, content_type)
        shutdowns.append(stop)
        return url

    yield start
    for stop in shutdowns:
        stop()


def _git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout.strip()


def _stamp(commit, built='2026-08-28T00:00:00.000Z'):
    return f'{{"commit": "{commit}", "built_at": "{built}"}}'


def test_matching_commit_is_current(host):
    head = _git('rev-parse', 'HEAD')
    url = host(_stamp(head))
    stamp, failure = probe.fetch_stamp(url)
    assert failure is None
    verdict = probe.compare(stamp, head, url)
    assert verdict.state == probe.CURRENT
    assert verdict.code == 0


def test_spa_fallback_is_not_a_deploy(host):
    """A 200 proves nothing: _redirects answers unknown paths with index.html."""
    url = host(SPA_SHELL, 'text/html; charset=utf-8')
    stamp, failure = probe.fetch_stamp(url)
    assert stamp is None
    assert failure.state == probe.STALE
    assert failure.code == 1
    assert 'no build stamp at all' in failure.headline


def test_older_commit_reports_how_far_behind(host):
    """Regression: git() returns '' for `cat-file -e`, which is falsy but not failure.

    Testing that truthily treated every known commit as unknown, so the probe said
    'diverged from main' for a commit one step behind it and dropped the list of what
    was missing -- a true verdict with its most useful half silently removed.
    """
    head = _git('rev-parse', 'HEAD')
    parent = _git('rev-parse', 'HEAD~1')
    url = host(_stamp(parent))
    stamp, failure = probe.fetch_stamp(url)
    assert failure is None
    verdict = probe.compare(stamp, head, url)
    assert verdict.state == probe.STALE
    assert '1 commits behind' in verdict.headline
    assert 'Not on the live site' in verdict.detail


def test_unknown_commit_does_not_crash(host):
    head = _git('rev-parse', 'HEAD')
    url = host(_stamp('deadbeef' * 5))
    stamp, _ = probe.fetch_stamp(url)
    verdict = probe.compare(stamp, head, url)
    assert verdict.state == probe.STALE
    assert 'not a commit in this clone' in verdict.detail


def test_unparseable_stamp_is_stale_not_a_crash(host):
    url = host('not json at all')
    stamp, failure = probe.fetch_stamp(url)
    assert stamp is None
    assert failure.state == probe.STALE


def test_stamp_without_a_commit_is_stale(host):
    url = host('{"built_at": "2026-08-28T00:00:00.000Z"}')
    stamp, failure = probe.fetch_stamp(url)
    assert stamp is None
    assert failure.state == probe.STALE


def test_unreachable_is_its_own_state():
    """Distinct from stale on purpose: a down host and an old host need different fixes."""
    url, stop = _serve('', 'application/json')
    stop()
    stamp, failure = probe.fetch_stamp(url)
    assert stamp is None
    assert failure.state == probe.UNREACHABLE
    assert failure.code == 2

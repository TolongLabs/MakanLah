"""Ask the live site which commit it is serving, and say so when that is not main.

Why this exists. The deploy job in .github/workflows/ci.yml skips when the Cloudflare
credentials are absent, and .claude/hooks/guard-merge.sh counts SKIPPED alongside
SUCCESS when it decides whether CI stood in for a reviewer. So a rotated or expired
token turns "did not deploy" into a green review, and the hosted site drifts behind
main with nothing anywhere reporting it. That is issue #36 a second time through a
different door, and the door is in our own workflow.

Why it reads a stamp rather than comparing builds. Rebuilding main and diffing bundle
hashes against the live ones tests build determinism as much as it tests the deploy,
and a probe that cries stale over an unrelated hash change is one everybody learns to
ignore. web/scripts/stamp.mjs writes dist/build.json at build time; this reads it back.
The build asserts a fact about itself and the probe checks that fact -- neither is the
other's own definition, which is the failure this repo keeps rediscovering
(docs/AUTONOMY.md, "never verify a fix with the fix's own definition").

A 200 proves nothing. web/public/_redirects answers every unknown path with index.html,
so a site with no stamp at all returns 200 and 1059 bytes of HTML for /build.json. The
content type is the assertion; the status code is noise.

Exit code 0 means the live site is current, 1 means it is not, and 2 means the probe
could not reach it to find out. Run it by hand against any deployment:

    uv run python scripts/staleness_probe.py --url https://makanlah-b5h.pages.dev
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_URL = 'https://makanlah-b5h.pages.dev'
CURRENT, STALE, UNREACHABLE = 'current', 'stale', 'unreachable'


@dataclass
class Verdict:
    state: str
    headline: str
    detail: str = ''

    @property
    def code(self) -> int:
        return {CURRENT: 0, STALE: 1, UNREACHABLE: 2}[self.state]


def git(*args: str) -> str | None:
    try:
        out = subprocess.run(['git', *args], capture_output=True, text=True, timeout=30, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return out.stdout.strip()


def describe(sha: str) -> str:
    """One line about a commit, or a bare sha when this clone has never seen it."""
    if git('cat-file', '-e', f'{sha}^{{commit}}') is None:
        return f'{sha[:12]} (not a commit in this clone)'
    subject = git('log', '-1', '--format=%s', sha) or ''
    when = git('log', '-1', '--format=%cs', sha) or ''
    return f'{sha[:12]} {when} {subject}'.strip()


def fetch_stamp(base: str) -> tuple[dict | None, Verdict | None]:
    """Read /build.json off the live site. The second element is set only on failure."""
    # The cache buster is belt and braces next to the no-store header in
    # web/public/_headers: an edge-cached stamp would describe the previous deploy and
    # the probe would report a fresh site as stale.
    target = f'{base.rstrip("/")}/build.json?probe={int(time.time())}'
    request = urllib.request.Request(
        target, headers={'Cache-Control': 'no-cache', 'User-Agent': 'makanlah-staleness-probe'}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get('Content-Type', '')
            body = response.read(64_000).decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return None, Verdict(UNREACHABLE, f'{base} answered HTTP {error.code} for /build.json.')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return None, Verdict(UNREACHABLE, f'{base} could not be reached: {error}.')

    if 'json' not in content_type.lower():
        return None, Verdict(
            STALE,
            f'{base} has no build stamp at all.',
            f"/build.json served '{content_type}' and {len(body)} bytes rather than JSON. _redirects answers unknown "
            'paths with index.html, so this is the SPA shell: the live build predates the stamp entirely and cannot '
            'be newer than the commit that introduced it.',
        )
    try:
        stamp = json.loads(body)
    except json.JSONDecodeError as error:
        return None, Verdict(STALE, f'{base} served an unreadable build stamp.', f'{error}. Body: {body[:200]!r}')
    if not isinstance(stamp, dict) or not stamp.get('commit'):
        return None, Verdict(STALE, f'{base} served a build stamp with no commit in it.', f'Body: {body[:200]!r}')
    return stamp, None


def compare(stamp: dict, expected: str, base: str) -> Verdict:
    live = str(stamp['commit'])
    built = str(stamp.get('built_at', 'an unrecorded time'))
    if live == expected:
        return Verdict(CURRENT, f'{base} is serving {live[:12]}, which is main.', f'Built at {built}.')

    # `git cat-file -e` prints nothing and reports through its exit code, so git() returns
    # '' on success here and None on failure. Testing truthiness silently treats every known
    # commit as unknown, which is how this first shipped: it read 'diverged from' for a
    # commit three behind main and dropped the list of what was missing.
    known = git('cat-file', '-e', f'{live}^{{commit}}') is not None
    behind = git('rev-list', '--count', f'{live}..{expected}') if known else None
    gap = f'{behind} commits behind' if behind and behind != '0' else 'diverged from'
    lines = [
        f'Live:  {describe(live)}',
        f'Main:  {describe(expected)}',
        f'Built at {built}.',
    ]
    if behind and behind != '0':
        missing = git('log', '--oneline', '--no-decorate', '-20', f'{live}..{expected}') or ''
        if missing:
            lines += ['', 'Not on the live site:', missing]
    return Verdict(STALE, f'{base} is {gap} main.', '\n'.join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default=os.environ.get('PUBLIC_URL') or DEFAULT_URL)
    parser.add_argument('--expected', default=None, help='commit the site should be serving (default: HEAD)')
    args = parser.parse_args()

    expected = args.expected or git('rev-parse', 'HEAD')
    if not expected:
        print('::error::could not read HEAD, so there is nothing to compare the live site against')
        return 2

    stamp, failure = fetch_stamp(args.url)
    verdict = failure if failure else compare(stamp, expected, args.url)

    checked = datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
    print(f'{verdict.state.upper()}: {verdict.headline}')
    if verdict.detail:
        print()
        print(verdict.detail)
    print()
    print(f'Checked {checked} against {args.url}')

    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as handle:
            handle.write(f'state={verdict.state}\n')
            handle.write(f'headline={verdict.headline}\n')
    return verdict.code


if __name__ == '__main__':
    sys.exit(main())

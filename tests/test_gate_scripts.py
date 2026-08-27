"""The gate scripts are the first thing an unattended run executes.

Both defects these cover were silent: preflight reported a clean credential
section while the key every model lane reads went unchecked, and verify probed
the host the session is NOT signed in to, reporting a login wall for a session
that was live.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_preflight_checks_the_keys_config_actually_reads():
    preflight = (ROOT / 'scripts' / 'preflight.sh').read_text()
    config = (ROOT / 'makanlah' / 'config.py').read_text()

    checked = set()
    for line in preflight.splitlines():
        m = re.search(r'^\s*for k in (.+); do\s*$', line)
        if m:
            checked.update(m.group(1).split())

    for key in ('DASHSCOPE_API_KEY', 'DATABASE_URL'):
        assert f"'{key}'" in config or key in config, f'{key} is not read by config.py'
        assert key in checked, f'preflight does not report {key}, which config.py reads'

    assert 'MODELSCOPE_API_KEY' not in checked, 'preflight still checks the abandoned ModelScope key'


def test_verify_probes_the_host_the_scraper_uses():
    session = (ROOT / 'scripts' / 'chrome-session.sh').read_text()
    scraper = (ROOT / 'ingest' / 'rednote.py').read_text()

    assert "BASE = 'https://www.rednote.com'" in scraper
    assert 'rednote.com/search_result' in session, 'verify does not probe rednote.com'
    assert 'xiaohongshu.com/search_result' not in session, (
        'verify probes xiaohongshu.com, a separate session from the one ingestion uses'
    )


def test_verify_does_not_pass_without_asserting_content():
    session = (ROOT / 'scripts' / 'chrome-session.sh').read_text()
    body = session[session.index('do_verify()') : session.index('do_start()')]

    assert 'uv run' in body and '--with websockets' in body, (
        'verify falls back to an interpreter without websockets and asserts nothing'
    )
    # The ModuleNotFoundError branch must still be a failure, never a warn-and-pass.
    warn = body.index('websockets not installed')
    assert 'SystemExit(1)' in body[warn : warn + 400]

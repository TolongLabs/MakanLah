"""Who may call this API from a browser.

`*` was right for a local API and wrong for a public one -- not because it leaks
a session (auth is a Bearer header, not a cookie, so `allow_credentials` is off
and no site can ride a signed-in user) but because every request spends a model
call. An open policy invites someone else's page to spend the budget.

It does nothing to curl. The daily ceiling in api/main.py is the real control;
this raises the bar for the browser-based case only, and saying so is the point.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from makanlah.config import _default_cors_regex  # noqa: E402

RX = re.compile(_default_cors_regex('makanlah-b5h'))


@pytest.mark.parametrize(
    'origin',
    [
        'https://makanlah-b5h.pages.dev',
        'https://fix-something.makanlah-b5h.pages.dev',  # a preview branch
        'http://localhost:5188',
        'http://127.0.0.1:5173',
        'http://localhost',
    ],
)
def test_ours_is_allowed(origin):
    assert RX.match(origin)


@pytest.mark.parametrize(
    'origin',
    [
        'https://evil.pages.dev',  # somebody else on the same shared domain
        'https://makanlah-b5h.pages.dev.attacker.com',  # suffix attack
        'https://notmakanlah-b5h.pages.dev',
        'http://makanlah-b5h.pages.dev',  # plain http on the public host
        'https://example.com',
    ],
)
def test_everyone_else_is_not(origin):
    assert not RX.match(origin)


def test_the_project_name_is_actually_used():
    """A regex that ignored its argument would pass every test above while
    allowing another project's previews."""
    other = re.compile(_default_cors_regex('someone-else'))
    assert other.match('https://someone-else.pages.dev')
    assert not other.match('https://makanlah-b5h.pages.dev')

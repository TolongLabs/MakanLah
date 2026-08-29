"""Test-wide isolation for the spend ledger.

The ledger picks its backend from the environment: postgres when DATABASE_URL is
set. A developer's .env sets DATABASE_URL, so without this the suite runs against
the **production** Neon ledger -- reading real accumulated spend, writing test
charges into it, and taking a network round trip per counter operation. Observed
before this existed: 12 failures asserting against real production values, and a
six-minute run where the same suite takes under thirty seconds.

CI has no DATABASE_URL and so never saw it, which is the dangerous shape: green
in the only place anyone was looking, wrong everywhere a person actually works.

SQLite in a tmp directory is out-of-process, which is the property the ledger
tests need, and it is nobody's production data.
"""

import pytest


@pytest.fixture(autouse=True)
def _never_touch_the_real_ledger(tmp_path):
    # Per test, not per session. The ledger persists by design, so one file
    # shared across the suite carries spend from one test into the next and every
    # assertion after the first sees a number it did not put there.
    import os

    path = tmp_path / 'test-ledger.db'
    previous = {k: os.environ.get(k) for k in ('LEDGER_PATH', 'DATABASE_URL')}
    os.environ['LEDGER_PATH'] = str(path)
    os.environ.pop('DATABASE_URL', None)
    yield
    for k, v in previous.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

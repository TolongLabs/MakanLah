"""The spend ceiling must bound the bill across processes, not inside one.

Measured against production on 2026-08-29, and this is not a hypothetical. The
guest bucket allows 20 per 300s. Thirty sequential requests behaved exactly as
designed -- 20 served, 10 refused. Twenty-five requests fired *in parallel*
against that same already-exhausted bucket returned **ten 200s**, because Vercel
answered them from containers that had never seen the first thirty.

Every counter in api/main.py is a module-level dict: `_spend`, `_ip_spend`,
`_attempts`, `_companion`. On a single long-lived process -- Render, or a laptop
-- that is correct and cheap. On serverless each concurrent request can land in a
fresh container, so N containers each believe they hold the whole RM10 day.
The ceiling multiplies by the concurrency an attacker chooses, which is the
opposite of a ceiling.

The owner set DAILY_BUDGET_MYR at 10 and asked twice for protection against
someone looping the public endpoint. These tests encode the thing that actually
has to be true: **state that bounds money must outlive the process that holds
it.**

A fresh container is simulated by resetting the module globals, which is exactly
what a cold start does.
"""

import pytest
from fastapi import HTTPException

from api import main as api_main


@pytest.fixture(autouse=True)
def out_of_process_ledger(tmp_path, monkeypatch):
    """Point the ledger at a real store outside this process.

    CI has no DATABASE_URL, so without this the suite could only assert the bug,
    never the fix. SQLite is not the production backend -- Postgres on Neon is --
    but it exercises the same code path and it is genuinely out of process, which
    is the property under test. A test that can only pass in production is not a
    test.
    """
    monkeypatch.setenv('LEDGER_PATH', str(tmp_path / 'ledger.db'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    # Reset the in-memory mirrors at setup as well as on demand. Without
    # this, _companion_minute carries across tests and the per-minute cap
    # binds before the daily one, failing a test for a reason that has
    # nothing to do with what it is checking.
    api_main._spend.update({'day': -1.0, 'myr': 0.0})
    api_main._ip_spend.clear()
    api_main._attempts.clear()
    api_main._companion.update({'day': -1.0, 'used': 0.0})
    api_main._companion_minute.clear()
    yield


@pytest.fixture
def fresh_process():
    """Simulate a cold start: new container, empty in-memory counters.

    Anything the ledger truly persists is unaffected by this; anything held in a
    module global is lost, which is exactly the distinction being tested.
    """

    def restart():
        api_main._spend.update({'day': -1.0, 'myr': 0.0})
        api_main._ip_spend.clear()
        api_main._attempts.clear()
        api_main._companion.update({'day': -1.0, 'used': 0.0})
        api_main._companion_minute.clear()

    return restart


class TestSpendSurvivesRestart:
    def test_spend_is_not_forgotten_when_the_container_is_replaced(self, fresh_process, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 0.01)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 0.005)
        # The per-IP share must not be what refuses this, or the test passes
        # while the day budget it claims to check is wide open.
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)

        class Req:
            client = type('c', (), {'host': '203.0.113.9'})()
            headers: dict[str, str] = {}

        req = Req()
        api_main._charge(req, 2)  # spends the whole 0.01
        assert not api_main._affordable(req, 1), 'budget should be gone before the restart'

        fresh_process()

        assert not api_main._affordable(req, 1), (
            'a replaced container believes the day is untouched, so the RM budget '
            'multiplies by however many containers the caller can provoke'
        )

    def test_one_ip_share_is_not_reset_by_a_restart(self, fresh_process, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 10.0)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 0.1)

        class Req:
            client = type('c', (), {'host': '198.51.100.4'})()
            headers: dict[str, str] = {}

        req = Req()
        api_main._charge(req, 1)  # the whole 10% share
        assert not api_main._affordable(req, 1)

        fresh_process()

        assert not api_main._affordable(req, 1), 'the per-IP share reset, so one troll gets a fresh slice per container'


class TestRateLimitSurvivesRestart:
    def test_a_bucket_is_not_refilled_by_a_replacement_container(self, fresh_process):
        class Req:
            client = type('c', (), {'host': '192.0.2.55'})()
            headers: dict[str, str] = {}

        req = Req()
        allowed, _window = api_main.RATE_LIMIT['guest']
        for _ in range(allowed):
            api_main._rate_limit('guest', req)
        with pytest.raises(HTTPException):
            api_main._rate_limit('guest', req)

        fresh_process()

        with pytest.raises(HTTPException):
            api_main._rate_limit('guest', req)


class TestCompanionQuotaSurvivesRestart:
    def test_the_free_tier_counter_is_shared_across_processes(self, fresh_process, monkeypatch):
        # Crossing a free tier starts charging rather than failing, so this
        # counter is the thing standing between us and a surprise bill.
        monkeypatch.setattr(api_main, 'COMPANION_DAILY', 2)
        api_main._companion.update({'day': float(api_main._budget_day()), 'used': 2.0})
        assert not api_main._companion_quota()

        fresh_process()

        assert not api_main._companion_quota(), 'the free-tier day reset on a cold start'


class TestOneCounterNotTwo:
    """Persistence alone is not enough.

    /companion and /suggestions share a free tier. Two counters that each survive
    a cold start would each satisfy every other test in this file and together
    spend twice the quota. Crossing a free tier starts charging rather than
    failing, so the pair has to draw from one place.

    Raised by the frontend session, which owns /suggestions and noticed the gap
    in this spec.
    """

    def test_the_two_endpoints_draw_from_a_single_quota(self, fresh_process, monkeypatch):
        monkeypatch.setattr(api_main, 'COMPANION_DAILY', 4)
        granted = 0
        while api_main._companion_quota() and granted < 20:
            granted += 1
        assert granted == 4, f'granted {granted} against a cap of 4'

        fresh_process()

        assert not api_main._companion_quota(), (
            'the free tier refilled on a cold start, so each container spends the whole daily quota for both endpoints'
        )

    def test_concurrent_charges_are_not_lost(self, monkeypatch):
        """A persisted counter can still lose updates on a read-then-write race,
        and every lost update is budget given away."""
        import threading

        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 1000.0)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)

        class Req:
            client = type('c', (), {'host': '203.0.113.77'})()
            headers: dict[str, str] = {}

        threads, each = 8, 25
        errors: list[Exception] = []

        def hammer():
            try:
                for _ in range(each):
                    api_main._charge(Req(), 1)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        workers = [threading.Thread(target=hammer) for _ in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        assert not errors, f'ledger raised under concurrency: {errors[:2]}'
        spent = api_main.DAILY_BUDGET_MYR - api_main._spend_left()
        assert abs(spent - threads * each) < 0.001, f'lost updates: recorded {spent} of {threads * each}'


class TestBackendIsHonestAboutItself:
    """A ledger that cannot say where it lives cannot be audited from outside."""

    def test_it_names_its_backend(self):
        assert hasattr(api_main, 'ledger_backend'), (
            'api.main must name where its counters live, or nothing can assert '
            'that a deploy is not silently memory-backed'
        )

    def test_memory_is_only_acceptable_without_a_database(self, monkeypatch):
        # CI has no DATABASE_URL, so memory is correct there and the suite must
        # not demand otherwise. What must never happen is a *configured*
        # deployment quietly falling back to per-container counters.
        monkeypatch.setenv('DATABASE_URL', 'postgresql://example/db')
        assert api_main.ledger_backend() != 'memory', (
            'DATABASE_URL is set and the ledger still holds its counters in '
            'process memory, so each serverless container gets its own budget'
        )

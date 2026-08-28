"""The re-rank is bounded by the interactive budget, not by a generous ceiling.

It is 94% of p95, and its tail is upstream variance rather than anything in this
repo: the same prompts against the same lane measured p95 1.64s in one window and
8.87s in another. A 60s timeout let one slow call miss a 3s target by 4x.

docs/TRD.md already called re-ranking an enhancement rather than a gate. This
makes the timeout agree with that: past the budget, retrieval order ships.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from makanlah import models  # noqa: E402

CANDIDATES = [
    {'name': f'Place {i}', 'area': 'KL', 'dishes': ['x'], 'citations': [{'excerpt': 'good'}]} for i in range(6)
]


class FakeSettings:
    rerank_api_key = 'k'
    rerank_base_url = 'https://example.invalid/v1'
    rerank_model = 'm'
    rerank_thinking = False
    rerank_timeout = 0.4


@pytest.fixture
def budgeted(monkeypatch):
    monkeypatch.setattr(models.config, 'settings', lambda: FakeSettings())


class TestTheBudgetIsHonoured:
    def test_a_slow_lane_falls_back_rather_than_waiting(self, budgeted, monkeypatch):
        def slow(url, payload, key, timeout=60):
            time.sleep(min(timeout, 2.0))
            raise TimeoutError('too slow')

        monkeypatch.setattr(models, '_post', slow)
        started = time.perf_counter()
        picked = models.rerank('bak kut teh', CANDIDATES, limit=5)
        elapsed = time.perf_counter() - started

        assert elapsed < 1.5, f'the budget was not enforced: took {elapsed:.2f}s'
        assert len(picked) == 5, 'the fallback must still return a shortlist'
        assert [i for i, _ in picked] == [0, 1, 2, 3, 4], 'the fallback is retrieval order'

    def test_the_budget_covers_the_retry_not_each_attempt(self, budgeted, monkeypatch):
        """Retrying against a fresh full timeout is how a 4 second bound becomes eight."""
        calls = []

        def slow(url, payload, key, timeout=60):
            calls.append(timeout)
            time.sleep(min(timeout, 2.0))
            raise TimeoutError('slow')

        monkeypatch.setattr(models, '_post', slow)
        started = time.perf_counter()
        models.rerank('x', CANDIDATES, limit=5, retries=3)
        assert time.perf_counter() - started < 1.5
        assert all(t <= FakeSettings.rerank_timeout for t in calls), f'a call got more than the budget: {calls}'

    def test_a_fast_lane_is_untouched(self, budgeted, monkeypatch):
        monkeypatch.setattr(models, '_post', lambda *a, **k: {'ok': 1})
        monkeypatch.setattr(models, '_content', lambda b: '{}')
        monkeypatch.setattr(models, '_json_object', lambda t: {'results': [{'index': 2, 'why': 'good broth'}]})
        picked = models.rerank('x', CANDIDATES, limit=5)
        assert picked == [(2, 'good broth')]

    def test_the_fallback_never_returns_more_than_asked(self, budgeted, monkeypatch):
        monkeypatch.setattr(models, '_post', lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
        assert len(models.rerank('x', CANDIDATES, limit=3)) == 3

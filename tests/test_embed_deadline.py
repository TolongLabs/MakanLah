"""The embedding call needs the deadline the re-rank call already has (issue #41).

Two of four full eval runs hit a 120s+ maximum while p95 stayed at 2.7-3.1s, so
this is a thin tail rather than a slowdown. `rerank` bounds itself with
`RERANK_TIMEOUT`; `embed` passes no timeout at all and inherits `_post`'s 120s
default, which matches the observed 131.88s and 122.14s maxima almost exactly.

The bound has to be shared across batches, not per call. A per-call timeout on a
three-batch embed is a three-times-the-timeout worst case -- the same arithmetic
that turned a "4 second" re-rank bound into eight and is commented as such in
models.py. Getting that wrong looks fixed and is not.
"""

import time

import pytest

from makanlah import config, models


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """embed() only needs a key, a base url and a model name. Everything else in
    settings() reaches for env this test has no business depending on."""
    real = config.settings()
    monkeypatch.setattr(
        config,
        'settings',
        lambda: real.__class__(**{**real.__dict__, 'embed_api_key': 'test-key'}) if hasattr(real, '__dict__') else real,
    )
    yield


class TestEmbedDeadline:
    def test_embed_passes_an_explicit_bounded_timeout(self, monkeypatch):
        seen = []

        def fake_post(url, payload, key, timeout=120):
            seen.append(timeout)
            return {'data': [{'index': i, 'embedding': [0.0]} for i in range(len(payload['input']))]}

        monkeypatch.setattr(models, '_post', fake_post)
        models.embed(['a'])
        assert seen, 'embed did not call _post'
        assert seen[0] is not None
        assert seen[0] <= 30, f'embed inherited a {seen[0]}s timeout; the 120s default is the #41 tail'

    def test_batches_share_one_deadline(self, monkeypatch):
        # More rows than one batch, each call burning most of the budget. The total
        # must stay bounded rather than scaling with the number of batches.
        budget = []

        def fake_post(url, payload, key, timeout=120):
            budget.append(timeout)
            return {'data': [{'index': i, 'embedding': [0.0]} for i in range(len(payload['input']))]}

        monkeypatch.setattr(models, '_post', fake_post)
        models.embed([f'row {i}' for i in range(models.EMBED_BATCH * 3)])
        assert len(budget) >= 2, 'expected several batches'
        assert all(b < a for a, b in zip(budget, budget[1:], strict=False)), (
            f'each batch got a fresh timeout ({budget}); the deadline must shrink as it is spent, '
            'or three batches cost three times the bound'
        )

    def test_a_hanging_provider_does_not_hang_the_request(self, monkeypatch):
        def slow_post(url, payload, key, timeout=120):
            time.sleep(min(timeout, 1.0) + 0.05)
            raise TimeoutError('provider did not answer')

        monkeypatch.setattr(models, '_post', slow_post)
        started = time.monotonic()
        with pytest.raises((RuntimeError, TimeoutError)):
            models.embed(['a'])
        elapsed = time.monotonic() - started
        assert elapsed < 20, f'embed took {elapsed:.1f}s to give up'

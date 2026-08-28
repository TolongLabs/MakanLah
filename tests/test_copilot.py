"""The copilot's one rule: it never introduces a fact.

Every answer either quotes an excerpt already in the database or reports that
the posts do not cover the question. SWARM.md says there is no acceptance test
for "the copilot feels good" -- true of tone, false of grounding, which is what
these assert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from makanlah import copilot  # noqa: E402

VENUE = {'id': 'v-1', 'name': '兴记肉骨茶', 'area': 'Kepong', 'city': 'Kuala Lumpur', 'lat': 3.2, 'lng': 101.6}
ROWS = [
    {
        'excerpt': '汤头浓郁，本地人回头率高',
        'dishes': ['肉骨茶'],
        'sentiment': 'positive',
        'confidence': 0.9,
        'post_url': 'https://www.rednote.com/explore/abc',
        'platform': 'rednote',
        'author_handle': 'someone',
        'posted_at_raw': 'Feb 17',
    },
    {
        'excerpt': 'Queue was long but worth it',
        'dishes': [],
        'sentiment': 'positive',
        'confidence': 0.7,
        'post_url': 'https://maps.google.com/x',
        'platform': 'google_maps',
        'author_handle': None,
        'posted_at_raw': '2 months ago',
    },
]


class FakeCon:
    pass


class FakeSettings:
    """Pinned, so these assert behaviour rather than whatever .env happens to hold.

    They passed locally and failed in CI purely because the build machine has a
    DASHSCOPE_API_KEY and CI does not, so CI only ever ran the no-key branch.
    A test whose result depends on ambient environment is not a test.
    """

    copilot_api_key = 'test-key'
    copilot_base_url = 'https://example.invalid/v1'
    copilot_model = 'test-model'
    copilot_thinking = False


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(copilot.config, 'settings', lambda: FakeSettings())
    monkeypatch.setattr(copilot.db, 'venue_by_id', lambda con, vid: VENUE if vid == 'v-1' else None)
    monkeypatch.setattr(copilot.db, 'venue_evidence', lambda con, vid, limit=40: ROWS)


def _model(monkeypatch, payload):
    monkeypatch.setattr(copilot.models, '_post', lambda *a, **k: {'ok': True})
    monkeypatch.setattr(copilot.models, '_content', lambda body: '{}')
    monkeypatch.setattr(copilot.models, '_json_object', lambda text: payload)


class TestGrounding:
    def test_a_covered_answer_cites_a_real_stored_excerpt(self, wired, monkeypatch):
        _model(monkeypatch, {'covered': True, 'answer': 'Rich broth.', 'used': [0]})
        out = copilot.ask('v-1', 'how is the broth?', con=FakeCon())
        assert out['covered'] is True
        assert out['citations'][0]['excerpt'] == ROWS[0]['excerpt']
        assert out['citations'][0]['post_url'] == ROWS[0]['post_url']

    def test_a_claim_of_coverage_with_no_excerpt_is_downgraded(self, wired, monkeypatch):
        """The model does not get to assert grounding it did not use."""
        _model(monkeypatch, {'covered': True, 'answer': 'It is definitely halal.', 'used': []})
        out = copilot.ask('v-1', 'is it halal?', con=FakeCon())
        assert out['covered'] is False
        assert out['citations'] == []

    def test_an_uncovered_question_returns_no_citations(self, wired, monkeypatch):
        _model(monkeypatch, {'covered': False, 'answer': 'The posts do not say.', 'used': []})
        out = copilot.ask('v-1', 'is there parking?', con=FakeCon())
        assert out['covered'] is False
        assert out['citations'] == []

    def test_an_excerpt_number_the_model_invented_is_discarded(self, wired, monkeypatch):
        """Out-of-range indices are a hallucinated citation by another name."""
        _model(monkeypatch, {'covered': True, 'answer': 'Something.', 'used': [0, 99, -3]})
        out = copilot.ask('v-1', 'how is it?', con=FakeCon())
        assert len(out['citations']) == 1
        assert out['citations'][0]['excerpt'] == ROWS[0]['excerpt']

    def test_citations_are_built_from_rows_not_from_model_text(self, wired, monkeypatch):
        """A model asked for a URL produces a plausible one."""
        _model(
            monkeypatch,
            {
                'covered': True,
                'answer': 'See https://evil.example/fake',
                'used': [1],
                'citations': [{'post_url': 'https://evil.example/fake'}],
            },
        )
        out = copilot.ask('v-1', 'busy?', con=FakeCon())
        assert [c['post_url'] for c in out['citations']] == [ROWS[1]['post_url']]
        assert all('evil.example' not in c['post_url'] for c in out['citations'])


class TestDegradedPaths:
    def test_an_unknown_venue_is_reported_not_invented(self, wired, monkeypatch):
        out = copilot.ask('nope', 'anything?', con=FakeCon())
        assert out['covered'] is False and out['citations'] == []

    def test_a_venue_with_no_evidence_says_so(self, monkeypatch):
        monkeypatch.setattr(copilot.config, 'settings', lambda: FakeSettings())
        monkeypatch.setattr(copilot.db, 'venue_by_id', lambda con, vid: VENUE)
        monkeypatch.setattr(copilot.db, 'venue_evidence', lambda con, vid, limit=40: [])
        out = copilot.ask('v-1', 'how is it?', con=FakeCon())
        assert out['covered'] is False
        assert out['citations'] == []

    def test_a_model_failure_does_not_invent_an_answer(self, wired, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError('upstream 500')

        monkeypatch.setattr(copilot.models, '_post', boom)
        out = copilot.ask('v-1', 'how is it?', con=FakeCon())
        assert out['covered'] is False
        assert out['citations'] == []


class TestWithNoModelLane:
    """CI has no API key, so this is the branch it always takes. It must honour
    the contract rather than being an untested special case."""

    def test_an_unavailable_copilot_returns_no_citations(self, monkeypatch):
        class NoKey(FakeSettings):
            copilot_api_key = None

        monkeypatch.setattr(copilot.config, 'settings', lambda: NoKey())
        monkeypatch.setattr(copilot.db, 'venue_by_id', lambda con, vid: VENUE)
        monkeypatch.setattr(copilot.db, 'venue_evidence', lambda con, vid, limit=40: ROWS)
        out = copilot.ask('v-1', 'how is it?', con=FakeCon())
        assert out['covered'] is False
        assert out['citations'] == [], 'covered:false must never carry citations'

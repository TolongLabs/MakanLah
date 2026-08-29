"""The suggestion chips, and the one property that makes them safe.

A chip is a promise that tapping it returns something. The model is therefore
never allowed to write one: it is handed a numbered list of dishes that are
already in the database and returns indices. Everything here is about what
happens when it returns something else.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from makanlah import suggest

POOL = [
    {'dish': '肉骨茶', 'posts': 14, 'venues': 9},
    {'dish': 'nasi lemak', 'posts': 9, 'venues': 5},
    {'dish': 'char kuey teow', 'posts': 7, 'venues': 4},
    {'dish': 'roti canai', 'posts': 6, 'venues': 6},
    {'dish': 'coffee', 'posts': 5, 'venues': 5},
    {'dish': 'satay', 'posts': 4, 'venues': 3},
    {'dish': 'tiramisu', 'posts': 3, 'venues': 3},
]


class TestMealTime:
    @pytest.mark.parametrize(
        ('hour', 'band'),
        [(7, 'breakfast'), (12, 'lunch'), (19, 'dinner'), (1, 'late night supper'), (23, 'late night supper')],
    )
    def test_bands(self, hour, band):
        assert suggest._band(hour) == band


class TestFolding:
    def test_folds_case_variants_and_keeps_the_bigger_one(self, monkeypatch):
        # The corpus really does store 'nasi lemak' and 'Nasi Lemak' separately.
        # Offering both as two chips says the app cannot read its own data.
        monkeypatch.setattr(
            suggest.db,
            'popular_dishes',
            lambda con, n: [
                {'dish': 'Nasi Lemak', 'posts': 4, 'venues': 5},
                {'dish': 'nasi lemak', 'posts': 9, 'venues': 5},
            ],
        )
        out = suggest._candidates(None)
        assert [c['dish'] for c in out] == ['nasi lemak']

    def test_does_not_fold_a_translation(self, monkeypatch):
        # 椰浆饭 IS nasi lemak, and they stay separate on purpose: the corpus keeps
        # what the writer wrote, and issue #59 owns venue-level folding.
        monkeypatch.setattr(
            suggest.db,
            'popular_dishes',
            lambda con, n: [
                {'dish': 'nasi lemak', 'posts': 9, 'venues': 5},
                {'dish': '椰浆饭', 'posts': 4, 'venues': 4},
            ],
        )
        assert len(suggest._candidates(None)) == 2


class TestChips:
    def _pool(self, monkeypatch):
        monkeypatch.setattr(suggest.db, 'popular_dishes', lambda con, n: list(POOL))
        monkeypatch.setattr(suggest.db, 'connect', _fake_connect)

    def test_falls_back_to_corpus_order_with_no_key(self, monkeypatch):
        # CI has no key, so this is the branch CI actually runs.
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings(key=None))
        out = suggest.chips(now=_at(12))
        assert out['source'] == 'corpus'
        assert [c['label'] for c in out['chips']] == [p['dish'] for p in POOL[: suggest.CHIPS]]

    def test_a_model_reorders_but_cannot_write_a_label(self, monkeypatch):
        # The property the whole module exists for. The model asks for index 3
        # first; index 3's STRING is what renders, and it came from the database.
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _picks({'pick': [3, 1]}))
        out = suggest.chips(now=_at(8))
        assert out['source'] == 'model'
        assert out['chips'][0]['label'] == 'roti canai'
        assert out['chips'][1]['label'] == 'nasi lemak'
        assert all(c['label'] in {p['dish'] for p in POOL} for c in out['chips'])

    def test_an_invented_dish_cannot_reach_the_page(self, monkeypatch):
        # A model that answers with text instead of indices contributes nothing.
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _picks({'pick': ['Hokkien Mee At Jalan Alor']}))
        out = suggest.chips(now=_at(8))
        assert out['source'] == 'corpus'
        assert all(c['label'] in {p['dish'] for p in POOL} for c in out['chips'])

    def test_out_of_range_indices_are_dropped(self, monkeypatch):
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _picks({'pick': [99, -4, 2]}))
        out = suggest.chips(now=_at(8))
        assert out['chips'][0]['label'] == 'char kuey teow'
        assert len(out['chips']) == suggest.CHIPS

    def test_duplicate_picks_do_not_duplicate_a_chip(self, monkeypatch):
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _picks({'pick': [0, 0, 0, 1]}))
        labels = [c['label'] for c in suggest.chips(now=_at(8))['chips']]
        assert len(labels) == len(set(labels))

    def test_a_short_answer_is_still_topped_up(self, monkeypatch):
        # Two usable indices must still yield a full row of chips.
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _picks({'pick': [5]}))
        out = suggest.chips(now=_at(8))
        assert len(out['chips']) == suggest.CHIPS
        assert out['chips'][0]['label'] == 'satay'

    def test_a_dead_lane_is_not_an_error(self, monkeypatch):
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        monkeypatch.setattr(suggest.models, '_post', _boom)
        assert suggest.chips(now=_at(8))['source'] == 'corpus'

    def test_every_chip_carries_the_posts_behind_it(self, monkeypatch):
        # The count is the honesty. A chip with no number is just a guess.
        self._pool(monkeypatch)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings(key=None))
        assert all(c['posts'] >= 1 for c in suggest.chips(now=_at(8))['chips'])

    def test_an_empty_corpus_offers_nothing_rather_than_inventing(self, monkeypatch):
        monkeypatch.setattr(suggest.db, 'popular_dishes', lambda con, n: [])
        monkeypatch.setattr(suggest.db, 'connect', _fake_connect)
        monkeypatch.setattr(suggest.config, 'settings', lambda: _settings())
        assert suggest.chips(now=_at(8))['chips'] == []


def _at(hour):
    return datetime(2026, 8, 29, hour, 0, tzinfo=suggest.MYT)


def _settings(key='k'):
    class S:
        companion_api_key = key
        companion_base_url = 'https://example.invalid/v1'
        companion_model = 'test-model'
        companion_timeout = 3.0

    return S()


class _FakeConnect:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def _fake_connect():
    return _FakeConnect()


def _picks(obj):
    import json

    def post(url, payload, key, timeout=120):
        return {'choices': [{'message': {'content': json.dumps(obj)}}]}

    return post


def _boom(url, payload, key, timeout=120):
    raise RuntimeError('upstream is down')

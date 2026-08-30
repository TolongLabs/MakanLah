"""A radius so tight that nothing matches must still say why.

`recommend` returned `{results: []}` with no `distance_gap` and no `evidence_gap`
whenever `filter_candidates` came back empty, because that early return sits
above the gap logic. `bak kut teh` at 300m returned a bare empty list while the
same query wider returned five picks -- and the corpus knew where the nearest
bak kut teh was the whole time.

That is precisely the case the gap surface exists for: the tighter the radius,
the more likely the honest answer is "not here, but 2km that way", and the more
likely the old code was to say nothing at all.

Found by @makanlah-73 against prod.
"""

import contextlib

import pytest

from makanlah import rank


@pytest.fixture
def no_candidates_in_range(monkeypatch):
    """A corpus that is healthy and simply has nothing inside the radius."""

    class Con:
        def execute(self, *a, **k):
            raise AssertionError('this path must not reach SQL')

    @contextlib.contextmanager
    def connect(*a, **k):
        yield Con()

    monkeypatch.setattr(rank.db, 'connect', connect)
    monkeypatch.setattr(rank.db, 'filter_candidates', lambda con, **k: [])
    monkeypatch.setattr(rank.db, 'source_health', lambda con: (False, None, []))


def test_the_gap_is_computed_even_when_no_candidate_is_in_range(monkeypatch, no_candidates_in_range):
    """The regression. An empty candidate set must not short-circuit the reason."""
    called = []
    monkeypatch.setattr(
        rank,
        'distance_gap_for',
        lambda con, q, lat, lng: called.append(q) or {'term': 'bak kut teh', 'nearest': [{'name': 'Restoran X'}]},
    )

    out = rank.recommend('bak kut teh', lat=3.139, lng=101.6869, radius_m=300)

    assert called == ['bak kut teh'], 'the gap was never computed for an empty candidate set'
    assert out['results'] == []
    assert out['distance_gap']['term'] == 'bak kut teh'


def test_an_empty_result_with_no_known_dish_stays_a_plain_empty(monkeypatch, no_candidates_in_range):
    """No invention. If the corpus cannot name the dish there is no gap to state,
    and the response says nothing rather than guessing a nearest anything."""
    monkeypatch.setattr(rank, 'distance_gap_for', lambda con, q, lat, lng: None)

    out = rank.recommend('xyzzy noodles', lat=3.139, lng=101.6869, radius_m=300)

    assert out['results'] == []
    assert 'distance_gap' not in out


def test_a_query_with_no_location_asks_for_no_gap(monkeypatch, no_candidates_in_range):
    """`nearest_serving` needs a position. Without one there is no distance to
    report, so the gap is not attempted and nothing claims one."""
    monkeypatch.setattr(rank, 'distance_gap_for', lambda con, q, lat, lng: None)

    out = rank.recommend('bak kut teh')

    assert out['results'] == []
    assert 'distance_gap' not in out

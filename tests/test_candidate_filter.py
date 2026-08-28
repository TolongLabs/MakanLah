"""Stage 1 of ranking, the distance filter.

Every one of these failed before 2026-08-28. `filter_candidates` built a
statement with five placeholders and passed six parameters, so any request
carrying a radius raised ProgrammingError -- and `api/main.py` turned that into
a 200 with `degraded: true`, which reads as a corpus outage rather than a bug.
The whole distance path was dead in the shipped client and no test touched it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from makanlah import db  # noqa: E402


class RecordingConnection:
    """Asserts the placeholder/parameter contract psycopg enforces at runtime.

    A live database is not needed to catch an arity bug, and docs/TRD.md rules
    out a suite that needs one.
    """

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [{'id': f'v{i}'} for i in range(3)]
        self.calls = []

    def execute(self, sql, params=()):
        placeholders = sql.count('%s')
        if placeholders != len(params):
            raise AssertionError(
                f'the query has {placeholders} placeholders but {len(params)} parameters were passed\n{sql}'
            )
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows


class TestPlaceholderArity:
    def test_a_radius_query_passes_one_parameter_per_placeholder(self):
        con = RecordingConnection()
        db.filter_candidates(con, lat=3.1390, lng=101.6869, radius_m=3000)

    def test_an_unbounded_query_passes_one_parameter_per_placeholder(self):
        con = RecordingConnection()
        db.filter_candidates(con)

    @pytest.mark.parametrize('radius', [500, 3000, 25000])
    def test_arity_holds_across_radii(self, radius):
        con = RecordingConnection()
        db.filter_candidates(con, lat=3.1390, lng=101.6869, radius_m=radius)


class TestTheDistanceArgumentsAreInTheRightOrder:
    def test_latitude_and_longitude_are_not_transposed(self):
        """The original tuple was (lat, lng, lng, lat, ...) -- both duplicated and swapped.

        The spherical law of cosines needs the query latitude twice and the
        query longitude once, in that order.
        """
        con = RecordingConnection()
        db.filter_candidates(con, lat=3.1390, lng=101.6869, radius_m=3000)
        _, params = con.calls[0]
        assert params[:3] == (3.1390, 101.6869, 3.1390), (
            f'expected (lat, lng, lat) for the cosine terms, got {params[:3]}'
        )
        assert params[3] == 3000, 'the fourth parameter is the radius bound'


class TestTheCandidateSetIsDeterministic:
    def test_both_branches_order_their_results(self):
        """`limit 400` with no ORDER BY returns an arbitrary set that can differ
        between calls, which makes a ranking bug impossible to reproduce."""
        for kwargs in ({}, {'lat': 3.139, 'lng': 101.687, 'radius_m': 3000}):
            con = RecordingConnection()
            db.filter_candidates(con, **kwargs)
            sql = con.calls[0][0].lower()
            assert 'order by' in sql, f'no ORDER BY for {kwargs or "the unbounded branch"}'

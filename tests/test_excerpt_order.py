"""Which excerpt leads a citation, and which one must not.

Before 2026-08-28 both citation queries ordered by `m.confidence desc`.
Confidence measures how easy the text was to extract, which is close to the
opposite of whether it is worth reading: on this corpus the >=0.95 band averages
75 characters against 180 for the band below it, and is nearly twice as likely to
carry no opinion at all. A postal address is trivially extractable, so it won
every time -- 82 of 243 venues led with one, and one of them was the hero frame
of the demo video.

A live database is not needed to catch a reintroduction, and docs/TRD.md rules
out a suite that needs one. The measured effect on real data (82 address-shaped
leads down to 28) is in the PR, not here.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah import db  # noqa: E402


class RecordingConnection:
    """Captures the statement instead of running it, and enforces the
    placeholder/parameter contract psycopg checks at runtime."""

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
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

    def fetchone(self):
        return self.rows[0] if self.rows else None


def _order_clause(sql):
    """The ORDER BY of the outermost statement, whitespace-collapsed."""
    tail = sql.rsplit('order by', 1)[1]
    tail = tail.split('limit')[0]
    return re.sub(r'\s+', ' ', tail).strip()


class TestVenueEvidenceOrder:
    def test_the_lead_is_not_chosen_by_extractor_confidence(self):
        con = RecordingConnection()
        db.venue_evidence(con, 'v1')
        clause = _order_clause(con.calls[0][0])
        assert not clause.startswith('m.confidence'), clause

    def test_an_excerpt_that_argues_outranks_one_that_does_not(self):
        con = RecordingConnection()
        db.venue_evidence(con, 'v1')
        clause = _order_clause(con.calls[0][0])
        assert 'm.sentiment <> 0' in clause
        assert 'length(m.excerpt)' in clause

    def test_the_order_is_total_so_the_same_query_returns_the_same_excerpt(self):
        con = RecordingConnection()
        db.venue_evidence(con, 'v1')
        assert _order_clause(con.calls[0][0]).endswith('m.id')

    def test_placeholders_and_parameters_still_agree(self):
        con = RecordingConnection()
        db.venue_evidence(con, 'v1', limit=7)
        assert con.calls[0][1] == ('v1', 7)


class TestVenuesWithCitationsOrder:
    def test_the_lead_is_not_chosen_by_extractor_confidence(self):
        con = RecordingConnection()
        db.venues_with_citations(con, ['v1'])
        clause = _order_clause(con.calls[0][0])
        assert 'm.confidence' not in clause, clause

    def test_rows_stay_grouped_by_venue(self):
        con = RecordingConnection()
        db.venues_with_citations(con, ['v1'])
        assert _order_clause(con.calls[0][0]).startswith('v.id')

    def test_placeholders_and_parameters_still_agree(self):
        con = RecordingConnection()
        db.venues_with_citations(con, ['v1', 'v2'])
        assert con.calls[0][1] == (['v1', 'v2'],)


class TestOneDefinition:
    """Two queries drifting apart is how the venue page and the result row would
    start disagreeing about which post a pick rests on."""

    def test_both_queries_use_the_same_ordering(self):
        a, b = RecordingConnection(), RecordingConnection()
        db.venue_evidence(a, 'v1')
        db.venues_with_citations(b, ['v1'])
        shared = re.sub(r'\s+', ' ', db.EXCERPT_ORDER).strip()
        assert shared in re.sub(r'\s+', ' ', a.calls[0][0])
        assert shared in re.sub(r'\s+', ' ', b.calls[0][0])

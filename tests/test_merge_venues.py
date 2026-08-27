"""Venue merging is the one destructive operation in the pipeline.

docs/TRD.md keeps ambiguity as separate rows because "merging later is safe, a
wrong merge is not". These tests pin what counts as evidence, and the ordering
that keeps the merge from violating the (post_id, venue_id) unique key.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.merge_venues import merge_group


class RecordingCon:
    """Records SQL in order. The order is the thing under test."""

    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(' '.join(sql.split()))
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []


def steps(con):
    """Classify each statement by what it does, in order."""
    out = []
    for s in con.sql:
        low = s.lower()
        if low.startswith('update venue set aliases'):
            out.append('aliases')
        elif low.startswith('delete from mention'):
            out.append('drop_conflicting_mentions')
        elif low.startswith('update mention set venue_id'):
            out.append('repoint_mentions')
        elif low.startswith('delete from venue_embedding'):
            out.append('drop_embeddings')
        elif low.startswith('delete from venue'):
            out.append('drop_venues')
    return out


class TestMergeOrdering:
    def test_conflicting_mentions_are_dropped_before_repointing(self):
        # If a post already mentions the survivor, re-pointing the duplicate's
        # mention at it violates unique (post_id, venue_id). The delete must
        # come first or the whole merge aborts.
        con = RecordingCon()
        merge_group(con, 'keep', ['drop'], ['A', 'B'])
        s = steps(con)
        assert s.index('drop_conflicting_mentions') < s.index('repoint_mentions')

    def test_venue_rows_are_dropped_last(self):
        # Dropping the venue first would cascade its mentions away before they
        # could be re-pointed, silently losing evidence.
        con = RecordingCon()
        merge_group(con, 'keep', ['drop'], ['A', 'B'])
        s = steps(con)
        assert s[-1] == 'drop_venues'

    def test_mentions_are_repointed_before_the_venue_disappears(self):
        con = RecordingCon()
        merge_group(con, 'keep', ['drop'], ['A', 'B'])
        s = steps(con)
        assert s.index('repoint_mentions') < s.index('drop_venues')

    def test_stale_embeddings_are_removed_for_both_sides(self):
        # The survivor's document changed, so its old vector no longer describes
        # it. Keeping it would rank the merged venue on pre-merge text.
        con = RecordingCon()
        merge_group(con, 'keep', ['drop'], ['A', 'B'])
        assert 'drop_embeddings' in steps(con)
        emb = [s for s in con.sql if s.lower().startswith('delete from venue_embedding')][0]
        assert 'venue_id = any' in emb.lower()

    def test_names_are_preserved_as_aliases(self):
        # The place stays findable under every name it was written with.
        con = RecordingCon()
        merge_group(con, 'keep', ['drop'], ['何九茶室', 'Ho Kow Hainam Kopitiam'])
        assert steps(con)[0] == 'aliases'

    def test_every_step_runs_exactly_once(self):
        con = RecordingCon()
        merge_group(con, 'keep', ['d1', 'd2'], ['A', 'B', 'C'])
        s = steps(con)
        assert sorted(s) == sorted(set(s))
        assert len(s) == 5


class TestReviewUrl:
    """A citation that does not resolve is worse than no citation: it looks like
    evidence and is not. An earlier version built this from the venue's internal
    UUID and produced a URL that went nowhere."""

    def test_the_url_resolves_to_a_real_maps_search(self):
        from ingest.enrich_gmaps import review_url

        u = review_url('Village Park')
        assert u.startswith('https://www.google.com/maps/search/?api=1&query=')
        assert 'Village' in u

    def test_no_internal_identifier_leaks_into_the_url(self):
        from ingest.enrich_gmaps import review_url

        u = review_url('Village Park')
        assert 'place_id:' not in u
        assert '-' * 4 not in u  # no uuid fragment

    def test_a_chinese_name_is_escaped_rather_than_dropped(self):
        from ingest.enrich_gmaps import review_url

        u = review_url('兴记肉骨茶')
        assert '%' in u.split('query=')[1]
        assert len(u.split('query=')[1]) > 10

    def test_the_city_is_included_so_the_search_lands_in_kl(self):
        from urllib.parse import unquote

        from ingest.enrich_gmaps import review_url

        assert 'Kuala Lumpur' in unquote(review_url('Yut Kee'))

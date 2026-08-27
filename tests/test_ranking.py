"""Ranking behaviour that does not need a database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah.rank import _distance_m, maps_url


class TestDistance:
    def test_known_kl_distance_is_about_right(self):
        # KLCC to Mid Valley is roughly 6 km.
        d = _distance_m(3.1578, 101.7117, 3.1177, 101.6770)
        assert 5000 < d < 7000

    def test_a_missing_coordinate_yields_none_rather_than_zero(self):
        assert _distance_m(3.1, 101.7, None, 101.7) is None
        assert _distance_m(None, None, 3.1, 101.7) is None

    def test_identical_points_are_zero(self):
        assert _distance_m(3.1, 101.7, 3.1, 101.7) == 0


class TestMapsUrl:
    """No maps SDK, no key, no billing."""

    def test_url_contains_the_venue_and_needs_no_key(self):
        u = maps_url({'name': 'Village Park', 'area': 'Damansara Uptown', 'city': 'Petaling Jaya'})
        assert u.startswith('https://www.google.com/maps/search/?api=1&query=')
        assert 'Village' in u
        assert 'key=' not in u

    def test_place_id_is_used_to_disambiguate_a_chain(self):
        u = maps_url({'name': 'Oriental Kopi', 'area': None, 'city': 'Kuala Lumpur', 'place_id': 'ChIJabc'})
        assert 'query_place_id=ChIJabc' in u

    def test_a_chinese_name_is_escaped_not_dropped(self):
        u = maps_url({'name': '兴记肉骨茶', 'area': None, 'city': 'Kuala Lumpur'})
        assert '%' in u.split('query=')[1]


class TestDedupe:
    """Two rows for one restaurant waste a slot and read like a bug. This
    collapses them for one response only — the corpus keeps both, because
    docs/TRD.md is explicit that a wrong merge is not recoverable."""

    def _v(self, name, urls, dishes=()):
        return {
            'name': name,
            'dishes': list(dishes),
            'citations': [{'post_url': u, 'excerpt': 'x'} for u in urls],
        }

    def test_a_contained_name_collapses_into_the_longer_one(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('Village Park', ['a']), self._v('Village Park Nasi Lemak', ['b', 'c'])])
        assert len(out) == 1

    def test_the_better_evidenced_row_survives(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('Village Park', ['a']), self._v('Village Park Nasi Lemak', ['b', 'c'])])
        assert out[0]['name'] == 'Village Park Nasi Lemak'

    def test_citations_are_merged_not_discarded(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('Village Park', ['a']), self._v('Village Park Nasi Lemak', ['b', 'c'])])
        assert {c['post_url'] for c in out[0]['citations']} == {'a', 'b', 'c'}

    def test_dishes_are_merged(self):
        from makanlah.rank import dedupe

        out = dedupe(
            [
                self._v('Village Park', ['a'], ['nasi lemak']),
                self._v('Village Park Nasi Lemak', ['b', 'c'], ['ayam goreng']),
            ]
        )
        assert set(out[0]['dishes']) == {'nasi lemak', 'ayam goreng'}

    def test_merely_sharing_a_word_does_not_collapse_two_venues(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('Village Park', ['a']), self._v('Park Cafe', ['b'])])
        assert len(out) == 2

    def test_distinct_venues_are_untouched(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('Village Park', ['a']), self._v('Yut Kee', ['b']), self._v('兴记肉骨茶', ['c'])])
        assert len(out) == 3

    def test_a_chinese_generic_suffix_still_collapses(self):
        from makanlah.rank import dedupe

        out = dedupe([self._v('适苑', ['a']), self._v('适苑酒家', ['b', 'c'])])
        assert len(out) == 1


class TestAnswerLanguage:
    """The answer comes back in the language the question was asked in.

    Naming it in the system prompt was not enough: the model anchored on the
    language of the excerpts and answered an English question in Chinese because
    every cited post was Chinese.
    """

    def test_english_question(self):
        from makanlah.models import answer_language

        assert answer_language('spicy noodles for supper') == 'English'

    def test_malay_question(self):
        from makanlah.models import answer_language

        assert answer_language('nasi lemak yang sedap') == 'Malay'

    def test_chinese_question(self):
        from makanlah.models import answer_language

        assert answer_language('好吃的肉骨茶') == 'Chinese'

    def test_english_words_that_are_also_malay_slang_stay_english(self):
        from makanlah.models import answer_language

        # "best" is Malay slang and an English word; misrouting English to Malay
        # is the worse error, because English is the safe fallback.
        assert answer_language('best cafe in Bangsar') == 'English'

    def test_a_latin_venue_name_inside_a_chinese_question_stays_chinese(self):
        from makanlah.models import answer_language

        assert answer_language('Village Park 好吃吗') == 'Chinese'

    def test_a_malay_dish_name_in_an_english_sentence_stays_english(self):
        from makanlah.models import answer_language

        assert answer_language('where can I get good nasi lemak and ayam goreng') == 'English'

    def test_empty_query_does_not_crash(self):
        from makanlah.models import answer_language

        assert answer_language('') == 'English'


class TestSourceHealth:
    """docs/PRD.md FR6: the API must say when a source was unreachable.

    Before this existed, `degraded` was hardcoded false, which is worse than
    omitting the field: the UI promised honesty it could not deliver.
    """

    class _Cur:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    class _Con:
        def __init__(self, statuses, fresh=True):
            self.statuses = statuses
            self.fresh = fresh

        def execute(self, sql, params=None):
            from tests.test_ranking import TestSourceHealth as T

            if 'source_status' in sql:
                return T._Cur(self.statuses)
            return T._Cur([{'fresh': self.fresh}])

    def test_all_sources_healthy_is_not_degraded(self):
        from makanlah.db import source_health

        con = self._Con([{'platform': 'rednote', 'ok': True}, {'platform': 'google_maps', 'ok': True}])
        degraded, ok, reasons = source_health(con)
        assert degraded is False
        assert set(ok) == {'rednote', 'google_maps'}
        assert reasons == []

    def test_a_failed_source_degrades_and_names_itself(self):
        from makanlah.db import source_health

        con = self._Con([{'platform': 'rednote', 'ok': False}, {'platform': 'google_maps', 'ok': True}])
        degraded, ok, reasons = source_health(con)
        assert degraded is True
        assert ok == ['google_maps']
        assert any('RedNote' in r for r in reasons)

    def test_a_run_that_never_finished_is_not_counted_as_a_pass(self):
        # ok = null means the run died mid-batch. An absent verifier must never
        # look like success.
        from makanlah.db import source_health

        con = self._Con([{'platform': 'rednote', 'ok': None}, {'platform': 'google_maps', 'ok': True}])
        degraded, _, reasons = source_health(con)
        assert degraded is True
        assert any('did not finish' in r for r in reasons)

    def test_a_source_that_never_ran_degrades(self):
        from makanlah.db import source_health

        con = self._Con([{'platform': 'rednote', 'ok': True}])
        degraded, _, reasons = source_health(con)
        assert degraded is True
        assert any('Google Maps' in r for r in reasons)

    def test_a_stale_corpus_degrades_even_when_every_source_passed(self):
        from makanlah.db import source_health

        con = self._Con([{'platform': 'rednote', 'ok': True}, {'platform': 'google_maps', 'ok': True}], fresh=False)
        degraded, _, reasons = source_health(con)
        assert degraded is True
        assert any('collected' in r for r in reasons)

    def test_reasons_are_user_facing_prose_not_identifiers(self):
        # These strings render straight to the user. docs/DESIGN.md: sentence
        # case body copy, plain language, no internal identifiers.
        from makanlah.db import source_health

        con = self._Con([])
        _, _, reasons = source_health(con)
        assert reasons
        for r in reasons:
            assert 'google_maps' not in r, r
            assert '_' not in r, r
            assert r[0].islower(), r
            assert not r.endswith('.'), r


class TestCitationDiversity:
    """Two sources the user cannot see is the same as one source.

    Ordering citations purely by confidence handed every slot to whichever
    source the extractor was most sure about, which was RedNote across the whole
    corpus. Google Maps evidence existed and never appeared.
    """

    def _c(self, platform, n):
        return [{'platform': platform, 'post_url': f'{platform}-{i}'} for i in range(n)]

    def test_each_platform_gets_a_slot_before_any_gets_a_second(self):
        from makanlah.db import diverse_citations

        got = diverse_citations(self._c('rednote', 5) + self._c('google_maps', 8), 3)
        assert [c['platform'] for c in got] == ['rednote', 'google_maps', 'rednote']

    def test_a_single_platform_still_fills_every_slot(self):
        from makanlah.db import diverse_citations

        got = diverse_citations(self._c('rednote', 5), 3)
        assert len(got) == 3
        assert {c['platform'] for c in got} == {'rednote'}

    def test_best_first_order_is_preserved_within_a_platform(self):
        from makanlah.db import diverse_citations

        got = diverse_citations(self._c('rednote', 5) + self._c('google_maps', 8), 4)
        rednote = [c['post_url'] for c in got if c['platform'] == 'rednote']
        assert rednote == ['rednote-0', 'rednote-1']

    def test_fewer_citations_than_the_limit_is_not_padded(self):
        from makanlah.db import diverse_citations

        assert len(diverse_citations(self._c('rednote', 1), 3)) == 1

    def test_no_citations_yields_none_rather_than_a_placeholder(self):
        from makanlah.db import diverse_citations

        assert diverse_citations([], 3) == []

    def test_three_platforms_each_appear_before_any_repeats(self):
        from makanlah.db import diverse_citations

        got = diverse_citations(self._c('rednote', 3) + self._c('google_maps', 3) + self._c('instagram', 3), 3)
        assert len({c['platform'] for c in got}) == 3


class TestPartialRunIsNotAPermanentFailure:
    """A run cut off by `timeout` used to leave its ingest_run row open forever
    with ok = null, so the source read as permanently broken and `degraded` could
    never clear, after a run that had done most of its work.

    SIGTERM becomes SystemExit and Ctrl-C becomes KeyboardInterrupt. Neither is
    an Exception, so `except Exception` never saw them.
    """

    def test_the_handler_catches_baseexception(self):
        import inspect

        from ingest import enrich_gmaps

        src = inspect.getsource(enrich_gmaps.run)
        assert 'except BaseException' in src
        assert 'except Exception as' not in src

    def test_a_partial_run_that_did_work_is_recorded_as_a_pass(self):
        import inspect

        from ingest import enrich_gmaps

        src = inspect.getsource(enrich_gmaps.run)
        # ok is True only when it stopped early AND actually resolved something.
        assert "ok=stopped_early and stats['coords'] > 0" in src

    def test_a_real_error_is_not_recorded_as_a_pass(self):
        import inspect

        from ingest import enrich_gmaps

        src = inspect.getsource(enrich_gmaps.run)
        assert 'stopped_early = isinstance(e, (SystemExit, KeyboardInterrupt))' in src

    def test_a_run_that_never_finished_still_reads_as_not_a_pass(self):
        # The other half of the guarantee: an open row must not look like success.
        from makanlah.db import source_health

        con = TestSourceHealth._Con([{'platform': 'rednote', 'ok': True}, {'platform': 'google_maps', 'ok': None}])
        degraded, _, reasons = source_health(con)
        assert degraded is True
        assert any('did not finish' in r for r in reasons)

"""The guarantees that make a citation trustworthy.

These are unit tests over pure functions: no network, no database, no platform.
A suite that hits RedNote is a suite that fails when a session expires, and a red
check that means nothing trains everyone to ignore red checks (docs/TRD.md).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from makanlah.models import repair_excerpt
from makanlah.text import NOT_A_VENUE, detect_langs, normalize

POST = """吉隆坡9️⃣家地道美食合集
1️⃣兴记肉骨茶 Hing Kee Bakuteh
🕙3pm-2:30am
👉汤头浓郁，本地人回头率高
4️⃣Village Park
👉椰浆饭天花板"""


class TestExcerptIsVerbatim:
    """A fabricated quote behind a citation is worse than no citation."""

    def test_a_real_substring_passes_through_unchanged(self):
        span = '4️⃣Village Park\n👉椰浆饭天花板'
        out, origin = repair_excerpt(span, 'Village Park', [], POST)
        assert out == span
        assert origin == 'model'

    def test_a_stitched_excerpt_is_repaired_to_a_real_span(self):
        # The measured failure: the model drops the hours line and returns text
        # that reads correctly and does not appear in the post.
        stitched = '1️⃣兴记肉骨茶 Hing Kee Bakuteh\n👉汤头浓郁，本地人回头率高'
        assert stitched not in POST
        out, origin = repair_excerpt(stitched, '兴记肉骨茶', ['Hing Kee Bakuteh'], POST)
        assert origin == 'repaired'
        assert out in POST

    def test_repair_falls_back_to_an_alias_when_the_name_is_absent(self):
        out, origin = repair_excerpt('invented', 'Not In Post', ['Village Park'], POST)
        assert origin == 'repaired'
        assert out in POST

    def test_an_unanchorable_excerpt_is_dropped_rather_than_invented(self):
        out, origin = repair_excerpt('invented', 'Nowhere', ['Also Nowhere'], POST)
        assert out is None
        assert origin == 'dropped'

    @pytest.mark.parametrize('excerpt', [None, ''])
    def test_a_missing_excerpt_is_not_treated_as_verbatim(self, excerpt):
        out, origin = repair_excerpt(excerpt, 'Village Park', [], POST)
        assert origin == 'repaired'
        assert out in POST

    def test_every_returned_excerpt_is_a_substring_or_none(self):
        for name, aliases in [('Village Park', []), ('兴记肉骨茶', ['Hing Kee Bakuteh']), ('Ghost', [])]:
            out, _ = repair_excerpt('definitely not in the post', name, aliases, POST)
            assert out is None or out in POST


class TestRepairPrefersTestimony:
    """The repair used to anchor on the venue name, and on a RedNote listicle the
    line carrying the name is the pin line. So the guard against a fabricated
    quote was reintroducing address-as-testimony (#25). It now anchors on the
    model's own words first, and refuses to return chrome at all."""

    def test_a_rewrapped_excerpt_is_recovered_rather_than_replaced(self):
        # The model joined two real lines with a space. Nothing was invented, so
        # the repair should hand back the real span, not a window at the name.
        rewrapped = '1️⃣兴记肉骨茶 Hing Kee Bakuteh 👉汤头浓郁，本地人回头率高'
        out, origin = repair_excerpt(rewrapped, '兴记肉骨茶', [], POST)
        assert origin == 'repaired'
        assert out in POST
        assert '汤头浓郁' in out, 'the opinion is the part worth keeping'

    def test_a_window_of_only_chrome_is_dropped_not_returned(self):
        post = '📍Deeriang Restaurant\n48-G, Jalan Sultan, 50000 Kuala Lumpur\n#KLFood #CariMakan'
        out, origin = repair_excerpt('invented entirely', 'Deeriang Restaurant', [], post)
        assert out is None
        assert origin == 'dropped', 'an address is not testimony, and neither are hashtags'

    def test_opening_hours_are_chrome_too(self):
        post = 'Lucky Coffee Bar\n⏰ 12pm-5am\n#KLcafe #kualalumpur'
        out, origin = repair_excerpt('invented', 'Lucky Coffee Bar', [], post)
        assert out is None
        assert origin == 'dropped'

    def test_testimony_under_a_pin_line_survives(self):
        post = '📍Shin Yangpyung\n猪骨汤味道很正宗，肉炖到超嫩！其他菜也基本没踩雷～'
        out, origin = repair_excerpt('invented', 'Shin Yangpyung', [], post)
        assert origin == 'repaired'
        assert out in post
        assert not out.startswith('📍'), 'the pin line is dropped, the verdict is kept'

    def test_a_terse_chinese_verdict_is_not_mistaken_for_chrome(self):
        # Six characters is a whole verdict in Chinese. A length rule tuned on
        # English would discard this, which is the bias AGENTS.md warns about.
        out, origin = repair_excerpt('invented', 'Village Park', [], POST)
        assert origin == 'repaired'
        assert '椰浆饭天花板' in out


class TestVenueNormalization:
    """Ambiguity creates a new venue; merging later is safe, a wrong merge is not.
    But the same venue written two ways must collapse to one row."""

    def test_restoran_and_restaurant_collapse_to_one_key(self):
        assert normalize('Restoran Village Park') == normalize('Village Park Restaurant')

    def test_case_and_punctuation_do_not_split_a_venue(self):
        assert normalize('HO KOW, Hainam Kopitiam!') == normalize('ho kow hainam kopitiam')

    def test_chinese_names_survive_normalization(self):
        assert normalize('兴记肉骨茶') == '兴记肉骨茶'

    def test_a_chinese_suffix_is_stripped_like_its_latin_equivalent(self):
        assert normalize('适苑酒家') == normalize('适苑')

    def test_distinct_venues_do_not_collide(self):
        assert normalize('Village Park') != normalize('Yut Kee')

    def test_an_empty_name_normalizes_to_nothing(self):
        assert normalize('') == ''
        assert normalize('   ') == ''


class TestNotAVenue:
    """A district is not a restaurant. One bad row poisons a whole area's ranking."""

    @pytest.mark.parametrize('name', ['Kuala Lumpur', 'Bangsar', 'Mid Valley', 'PJ'])
    def test_places_and_malls_are_rejected(self, name):
        assert normalize(name) in NOT_A_VENUE

    @pytest.mark.parametrize('name', ['Village Park', 'Sek Yuen', '兴记肉骨茶'])
    def test_real_venues_are_not_rejected(self, name):
        assert normalize(name) not in NOT_A_VENUE


class TestLanguageDetection:
    """Plural by design. A single-language column would erase the code-switching
    that is the whole point of this corpus."""

    def test_a_code_switched_sentence_reports_every_language_present(self):
        langs = detect_langs('Village Park 的 nasi lemak is the best')
        assert set(langs) == {'zh', 'ms', 'en'}

    def test_chinese_only(self):
        assert detect_langs('椰浆饭天花板') == ['zh']

    def test_never_returns_empty(self):
        assert detect_langs('') == ['und']
        assert detect_langs('!!!') == ['und']


class TestStarSentiment:
    """Google Maps reviews take sentiment from the star rating, not from a model.

    The rating is the writer's judgement stated numerically, so inferring it from
    prose would be less accurate and cost a model call per review.
    """

    def test_five_stars_is_maximum_positive(self):
        from ingest.enrich_gmaps import star_sentiment

        assert star_sentiment('5 stars') == 1.0

    def test_one_star_is_maximum_negative(self):
        from ingest.enrich_gmaps import star_sentiment

        assert star_sentiment('1 star') == -1.0

    def test_three_stars_is_neutral(self):
        from ingest.enrich_gmaps import star_sentiment

        assert star_sentiment('3 stars') == 0.0

    def test_a_label_without_a_rating_is_null_not_neutral(self):
        # Null means "we do not know". Zero means "the writer was ambivalent".
        # Collapsing the two would make missing data look like a real judgement.
        from ingest.enrich_gmaps import star_sentiment

        assert star_sentiment('') is None
        assert star_sentiment(None) is None
        assert star_sentiment('Photo of a plate') is None

    def test_every_rating_lands_inside_the_schema_range(self):
        from ingest.enrich_gmaps import star_sentiment

        for n in range(1, 6):
            v = star_sentiment(f'{n} stars')
            assert v is not None and -1.0 <= v <= 1.0


class TestGmapsCoordinateParsing:
    """A Maps place URL embeds coordinates as !3d<lat>!4d<lng>. That is why this
    source needs no API key and no billing account."""

    def test_coordinates_are_read_out_of_a_place_url(self):
        from ingest.gmaps import _coords_from

        href = '/maps/place/Village+Park/data=!4m7!3m6!1s0x31cc:0x21aa!8m2!3d3.1376947!4d101.6233261'
        assert _coords_from(href) == (3.1376947, 101.6233261)

    def test_a_url_without_coordinates_yields_none(self):
        from ingest.gmaps import _coords_from

        assert _coords_from('/maps/search/nasi+lemak') == (None, None)
        assert _coords_from('') == (None, None)

    def test_place_id_is_extracted_for_chain_disambiguation(self):
        from ingest.gmaps import _place_id_from

        href = '/maps/place/X/data=!4m7!3m6!1s0x31cc4931330bf621:0x21aac39e1d6f6f3c!8m2!3d3.1!4d101.6'
        assert _place_id_from(href) == '0x31cc4931330bf621:0x21aac39e1d6f6f3c'

    def test_no_place_id_yields_none_rather_than_a_guess(self):
        from ingest.gmaps import _place_id_from

        assert _place_id_from('/maps/search/x') is None


class TestDishDedupe:
    """Extraction from reviews repeats a dish when the review does
    ("savoury pork ... so good ... pork"). A duplicated dish inflates the
    venue's dish list and its embedding document.
    """

    def _batch(self, monkeypatch, payload):
        import ingest.enrich_dishes as ed

        monkeypatch.setattr(ed.models, '_post', lambda *a, **k: {})
        monkeypatch.setattr(ed.models, '_content', lambda body: '')
        monkeypatch.setattr(ed.models, '_json_object', lambda text: payload)
        monkeypatch.setattr(
            ed.config,
            'settings',
            lambda: type('S', (), {'extract_model': 'm', 'extract_base_url': 'u', 'extract_api_key': 'k'})(),
        )
        return ed.extract_batch([{'excerpt': 'x'}, {'excerpt': 'y'}])

    def test_repeats_are_collapsed(self, monkeypatch):
        got = self._batch(monkeypatch, {'reviews': [{'index': 0, 'dishes': ['pork', 'noodles', 'pork']}]})
        assert got[0] == ['pork', 'noodles']

    def test_dedupe_is_case_insensitive_and_keeps_the_first_spelling(self, monkeypatch):
        got = self._batch(monkeypatch, {'reviews': [{'index': 0, 'dishes': ['Roti Babi', 'roti babi']}]})
        assert got[0] == ['Roti Babi']

    def test_blank_and_non_string_entries_are_dropped(self, monkeypatch):
        got = self._batch(monkeypatch, {'reviews': [{'index': 0, 'dishes': ['nasi lemak', '', '  ', None, 7]}]})
        assert got[0] == ['nasi lemak']

    def test_an_empty_list_is_preserved_rather_than_guessed(self, monkeypatch):
        # Most reviews are about service or queues. Empty is the correct answer.
        got = self._batch(monkeypatch, {'reviews': [{'index': 0, 'dishes': []}]})
        assert got[0] == []

    def test_an_out_of_range_index_is_ignored(self, monkeypatch):
        got = self._batch(monkeypatch, {'reviews': [{'index': 9, 'dishes': ['x']}, {'index': 1, 'dishes': ['y']}]})
        assert 9 not in got
        assert got[1] == ['y']

    def test_chinese_dishes_survive_unchanged(self, monkeypatch):
        got = self._batch(monkeypatch, {'reviews': [{'index': 0, 'dishes': ['肉骨茶', '椰浆饭']}]})
        assert got[0] == ['肉骨茶', '椰浆饭']


class TestCjkGenerics:
    """Malaysian-Chinese venue names carry suffixes that are not part of the
    identity. 茶餐室 and 冰室 were missing from the list, so 华阳 and 华阳冰室 stayed
    two venue rows for one kopitiam."""

    @pytest.mark.parametrize(
        'bare,full',
        [('华阳', '华阳冰室'), ('镒记', '镒记茶餐室'), ('适苑', '适苑酒家'), ('金莲', '金莲记餐厅')],
    )
    def test_a_generic_suffix_does_not_split_a_venue(self, bare, full):
        assert normalize(full).startswith(normalize(bare))

    def test_the_longest_suffix_matches_first(self):
        # 茶餐室 must match before 餐室, or the leading 茶 survives and the key differs.
        assert normalize('镒记茶餐室') == normalize('镒记')

    def test_a_dish_in_the_name_is_not_stripped(self):
        # 兴记 and 兴记肉骨茶 may be one place, but 肉骨茶 is a dish. Stripping
        # dishes would collapse different businesses sharing a speciality.
        assert normalize('兴记肉骨茶') != normalize('兴记')

    def test_a_name_that_is_only_a_generic_normalizes_to_nothing(self):
        assert normalize('茶餐室') == ''


class TestPronounsAreNotVenues:
    """A post says 他们家 ("their place") meaning a venue it named earlier, and
    the extractor takes the phrase as the name. Found in the live corpus as a
    real venue row with a mention behind it."""

    @pytest.mark.parametrize('name', ['他们家', '这家', '那家', 'this place', 'That Place'])
    def test_deictics_are_rejected(self, name):
        assert normalize(name) in NOT_A_VENUE

    @pytest.mark.parametrize('name', ['Village Park', '华阳', '海脚人', 'Yut Kee'])
    def test_real_venues_are_not_rejected(self, name):
        assert normalize(name) not in NOT_A_VENUE

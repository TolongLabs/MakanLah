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

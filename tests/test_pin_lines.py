"""Stripping the pin line off a RedNote excerpt.

RedNote posts are listicles -- a location line, then the opinion -- and the
extractor took the first line. The excerpt was verbatim, cited and real, and it
argued nothing (#25).

The pure function is tested here; the backfill it drives needs the corpus and is
verified by its own post-conditions, which it deliberately does not own.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ingest'))

from strip_pin_lines import MIN_REMAINDER, _weight, strip_pins  # noqa: E402


class TestStrips:
    def test_a_pin_line_above_testimony_is_dropped(self):
        assert strip_pins('📍店名：香港楼\n👉 必点咖喱鸭丝粥！浓郁顺滑真的香迷糊了，配烧肉饭一秒沦陷') == (
            '👉 必点咖喱鸭丝粥！浓郁顺滑真的香迷糊了，配烧肉饭一秒沦陷'
        )

    def test_a_listicle_number_and_a_pin_are_both_dropped(self):
        out = strip_pins('6. Roberts Char Kuey Teow\n📍1082, Jalan 17/29\nWok hei is unreal, and the portion is huge')
        assert out == 'Wok hei is unreal, and the portion is huge'

    def test_a_blank_line_between_them_does_not_stop_the_strip(self):
        assert strip_pins('📍 Somewhere\n\nThe curry laksa here is the best I have had in KL') == (
            'The curry laksa here is the best I have had in KL'
        )

    def test_a_postcode_line_counts_as_locating(self):
        out = strip_pins('Le Pont, 6, Jalan 1/137C, 58000 Kuala Lumpur\nThe sourdough is worth the drive out here')
        assert out == 'The sourdough is worth the drive out here'


class TestLeavesAlone:
    """Returning None rather than an empty string matters: the caller writes only
    what it is given, so a bad excerpt survives instead of being blanked."""

    def test_a_pin_line_with_nothing_under_it_is_left_alone(self):
        assert strip_pins('📍 Heun Kee Claypot Chicken Rice @ Taman Connaught') is None

    def test_testimony_that_never_had_a_pin_line_is_untouched(self):
        assert strip_pins('Food came promptly. Very flavorful and tasty, we ordered the small claypot') is None

    def test_a_remainder_too_short_to_be_testimony_is_left_alone(self):
        assert _weight('好吃') < MIN_REMAINDER
        assert strip_pins('📍興记肉骨茶\n好吃') is None

    def test_empty_and_none_are_handled(self):
        assert strip_pins('') is None
        assert strip_pins(None) is None


class TestLanguageParity:
    """A plain character count sets a bar Chinese clears trivially and English
    cannot, so the same sentence would survive in one language and be discarded in
    the other. That bias is invisible unless it is asserted."""

    def test_the_same_sentence_survives_in_both_scripts(self):
        en = '📍 Somewhere\nThe curry laksa here is the best I have had'
        zh = '📍 某处\n这里的咖喱叻沙是我在吉隆坡吃过最好的'
        assert strip_pins(en) is not None
        assert strip_pins(zh) is not None

    def test_a_fragment_is_discarded_in_both_scripts(self):
        assert strip_pins('📍 Somewhere\nGood') is None
        assert strip_pins('📍 某处\n好吃') is None


class TestKeepsTheInvariant:
    """`mention.excerpt` must stay a substring of `source_post.raw_text`, enforced
    by a trigger. Removing a prefix leaves a suffix, which is contiguous in the
    same place -- so the result must always be a suffix of the input, modulo the
    trailing strip."""

    def test_the_result_is_a_suffix_of_the_input(self):
        for src in (
            '📍店名：香港楼\n👉 必点咖喱鸭丝粥！浓郁顺滑真的香迷糊了，配烧肉饭一秒沦陷',
            '6. Roberts\n📍1082, Jalan 17/29\nWok hei is unreal, and the portion is huge',
            '📍 Somewhere\n\nThe curry laksa here is the best I have had in KL',
        ):
            out = strip_pins(src)
            assert out is not None
            assert src.rstrip().endswith(out)

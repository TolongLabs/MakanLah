"""#158: a figure in a post is not automatically what a meal there costs.

Measured over the live corpus: of 315 posts the parser reads a figure from, 240
state an explicit RM range and 17 carry a per-person marker. The remaining 58 are
a bare figure somewhere in the prose, and that shape is wrong often enough to
matter -- one post reading "on the pricey side (a mangorange drink costs around
RM12)" parsed to band 1, the cheapest, on a venue the writer called expensive.

So the parser stays as specified and this gate decides whether the figure it
found describes the meal. A wrong price is worse than no price: it is the one
number a reader uses to rule a place in or out before reading any evidence.
"""

from ingest.backfill_prices import figure_describes_the_meal as ok


def test_an_explicit_ringgit_range_is_a_price_statement():
    assert ok('Damage: RM 20–40 per visit') is True
    assert ok('expect RM60-80') is True


def test_a_per_person_marker_qualifies_a_single_figure():
    for t in ['人均80令吉', 'about RM35 per person', 'RM30 seorang', 'RM25 each', 'RM90 per pax']:
        assert ok(t) is True, t


def test_a_bare_figure_in_prose_does_not_qualify():
    """The measured failure. The writer priced one drink, not the meal."""
    assert ok('on the pricey side (a mangorange drink costs around RM12)') is False
    assert ok('the laksa was RM8 and I also had dessert') is False


def test_text_with_no_figure_at_all_does_not_qualify():
    assert ok('best bak kut teh in KL') is False
    assert ok('') is False
    assert ok(None) is False


def test_a_chinese_per_person_marker_qualifies():
    assert ok('一个人马币20') is True

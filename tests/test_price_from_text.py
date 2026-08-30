"""#158: 82% of venues carry no price, and the tester said so before we measured it.

The honesty constraint from the issue is the hard part, not the parsing: a venue
with no price evidence must say NOTHING. Guessing a band from area or cuisine is
the same defect as #126 for halal.

Bands are per-person RM, matching Google Maps' own four levels:
  1  < 15      2  15-40      3  40-100      4  > 100
"""

import pytest

from makanlah.prices import price_band_from_text


@pytest.mark.parametrize(
    'text,band',
    [
        ('Nasi lemak here is RM8, cheapest in Bangsar', 1),
        ('about RM 25 per person', 2),
        ('we paid RM60 each', 3),
        ('RM250 a head, special occasion only', 4),
        ('rm12 only', 1),
    ],
)
def test_reads_a_ringgit_figure_in_english(text, band):
    assert price_band_from_text(text) == band


@pytest.mark.parametrize(
    'text,band',
    [
        ('人均80令吉', 3),
        ('一个人马币20', 2),
        ('这里一碗才RM9', 1),
        ('80块一个人', 3),
    ],
)
def test_reads_a_ringgit_figure_in_chinese(text, band):
    assert price_band_from_text(text) == band


def test_reads_the_han_numeral_the_issue_named():
    """`三份肉马币八十` -- RM80 for three meats -- is in the corpus today and
    carries no price_band. It is the issue's flagship example."""
    assert price_band_from_text('三份肉马币八十') == 3


def test_reads_a_malay_figure():
    assert price_band_from_text('harga sekitar RM30 seorang') == 2


def test_a_range_takes_its_midpoint():
    assert price_band_from_text('mains are RM20-30') == 2
    assert price_band_from_text('RM80 to RM120 per pax') == 4


def test_says_nothing_when_the_post_names_no_figure():
    """The honesty constraint. Never infer a band from cuisine, area or tone."""
    for t in ['Best bak kut teh in KL, worth the queue', 'sangat sedap', '很好吃，推荐', '']:
        assert price_band_from_text(t) is None


def test_does_not_read_a_number_that_is_not_a_price():
    """The corpus is full of numbers that are not money. A parser that grabs any
    digit reports prices that were never written -- worse than no price at all."""
    for t in ['open until 10pm', 'we waited 45 minutes', 'rated 4.8 by 1643 people', 'Jalan Alor 21']:
        assert price_band_from_text(t) is None


def test_none_and_non_text_are_normal_outcomes():
    assert price_band_from_text(None) is None
    assert price_band_from_text(12345) is None

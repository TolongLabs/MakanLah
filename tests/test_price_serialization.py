"""#158: the price path stops at the database.

`price_band` is in the extraction schema and populated for 45 venues. `rank.py`
never serialized it, the API never returned it, and the client had nothing to
render -- so a UAT round over 58 production payloads measured 0 structured price
fields while the corpus held 49. Filling the column further would not have moved
that number by one.

A band is a claim about a venue, so it follows the same rule as every other claim
here: derived from evidence, or absent. Never inferred from area or cuisine.
"""

from makanlah.db import price_for_venue


def test_a_single_priced_mention_carries_through():
    assert price_for_venue([{'price_band': 2}]) == 2


def test_unpriced_mentions_are_ignored_not_counted_as_cheap():
    """None means 'the post did not say', not 'band 1'. Averaging nulls to a low
    band is how a venue nobody costed becomes the cheap option on screen."""
    assert price_for_venue([{'price_band': None}, {'price_band': 4}, {'price_band': None}]) == 4


def test_disagreeing_posts_take_the_most_common_band():
    assert price_for_venue([{'price_band': 2}, {'price_band': 2}, {'price_band': 3}]) == 2


def test_a_tie_takes_the_lower_band_rather_than_rounding_up():
    """Two writers, two bands, no majority. Overstating what a meal costs turns a
    usable suggestion into one the reader skips, so a tie resolves downward."""
    assert price_for_venue([{'price_band': 2}, {'price_band': 3}]) == 2


def test_no_price_evidence_is_none_never_a_guess():
    assert price_for_venue([]) is None
    assert price_for_venue([{'price_band': None}]) is None
    assert price_for_venue([{}]) is None


def test_an_out_of_range_band_is_discarded():
    """price_band is 1..4. Anything else came from a bad extraction and must not
    reach a reader as a price."""
    assert price_for_venue([{'price_band': 0}, {'price_band': 9}, {'price_band': 'cheap'}]) is None
    assert price_for_venue([{'price_band': 7}, {'price_band': 3}]) == 3

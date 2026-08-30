"""The copilot said "the posts do not cover the price" about venues we had priced.

`_shape` fed the model excerpt text, dishes and sentiment, and the system prompt
forbade stating a price unless an excerpt said so. Both were right when the only
price we had was whatever a writer happened to mention. They stopped being right
once 627 of 823 venues carried a band, and the result is a chat that answers "how
much per person" with a refusal while the card beside it renders a price.

The two provenances are NOT interchangeable, which is the whole difficulty:

  - a band parsed from a post's own text is evidence, and cites that post
  - a band from Google's `priceRange` is a third party's figure carried without
    a citation -- true, useful, and not something a post said (#179)

Conflating them would let the copilot answer "a reviewer said RM20" about a
figure no reviewer wrote, which is a fabricated citation on a product whose one
promise is that every claim traces to a post.
"""

from makanlah.copilot import price_facts


def test_a_band_parsed_from_a_post_is_attributed_to_that_post():
    rows = [{'n': 0, 'price_band': 2, 'extractor_model': 'qwen-plus'}]
    got = price_facts(rows)
    assert got == {'band': 2, 'source': 'post', 'from_excerpt': 0}


def test_a_google_band_is_attributed_to_google_and_cites_nothing():
    rows = [{'n': 0, 'price_band': 3, 'extractor_model': 'places_api_stars'}]
    got = price_facts(rows)
    assert got == {'band': 3, 'source': 'google', 'from_excerpt': None}


def test_a_post_derived_band_wins_over_a_google_one():
    """A figure a human wrote about this shop beats a platform's bucket."""
    rows = [
        {'n': 0, 'price_band': 4, 'extractor_model': 'places_api_stars'},
        {'n': 1, 'price_band': 2, 'extractor_model': 'google_maps_stars'},
    ]
    assert price_facts(rows) == {'band': 2, 'source': 'post', 'from_excerpt': 1}


def test_no_price_anywhere_is_none_so_the_refusal_stays_correct():
    assert price_facts([{'n': 0, 'price_band': None, 'extractor_model': 'qwen-plus'}]) is None
    assert price_facts([]) is None


def test_an_out_of_range_band_is_ignored():
    assert price_facts([{'n': 0, 'price_band': 9, 'extractor_model': 'qwen-plus'}]) is None


def test_the_band_carries_a_ringgit_range_a_reader_can_act_on():
    """`2` means nothing to a person. The prompt needs words."""
    from makanlah.copilot import BAND_WORDS

    assert BAND_WORDS[1] == 'under RM15 per person'
    assert BAND_WORDS[4] == 'over RM100 per person'
    assert set(BAND_WORDS) == {1, 2, 3, 4}

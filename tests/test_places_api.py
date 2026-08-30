"""Places API (New) as the ingestion path, replacing CDP browser driving.

Three things the browser could not do, measured on one live call to Village Park:

  1. **Untruncated review text.** 1,008 of 1,388 scraped posts carried Google's
     own "… More" control because the DOM collapses a long review (#15). The API
     returns the whole thing -- 1,430 characters on one of these five.
  2. **A real price range in ringgit.** `priceRange: RM1-20`, per venue, from
     Google. Better than the band this project parses out of prose and better
     than the $-$$$$ the card renders.
  3. **One request instead of a browser.** ~1s against ~25s of tab driving, and
     no Chrome to crash mid-run.

This module is the parsing half. The HTTP half is not unit-tested -- it is
verified against the live API, because a mocked Google is a test of the mock.
"""

import pytest

from ingest.places_api import price_band_from_level, price_band_from_range, review_to_post


@pytest.mark.parametrize(
    'level,band',
    [
        ('PRICE_LEVEL_INEXPENSIVE', 1),
        ('PRICE_LEVEL_MODERATE', 2),
        ('PRICE_LEVEL_EXPENSIVE', 3),
        ('PRICE_LEVEL_VERY_EXPENSIVE', 4),
    ],
)
def test_google_price_levels_map_onto_our_bands(level, band):
    assert price_band_from_level(level) == band


def test_an_unknown_or_absent_level_is_none_not_a_guess():
    for x in ['PRICE_LEVEL_UNSPECIFIED', 'PRICE_LEVEL_FREE', None, '', 'NONSENSE']:
        assert price_band_from_level(x) is None


def test_a_ringgit_range_beats_the_enum_because_it_carries_figures():
    """`priceRange` is what a reader actually wants: RM1-20, not a symbol."""
    rng = {'startPrice': {'currencyCode': 'MYR', 'units': '1'}, 'endPrice': {'currencyCode': 'MYR', 'units': '20'}}
    assert price_band_from_range(rng) == 1


def test_a_range_uses_its_midpoint_like_the_text_parser_does():
    rng = {'startPrice': {'currencyCode': 'MYR', 'units': '40'}, 'endPrice': {'currencyCode': 'MYR', 'units': '80'}}
    assert price_band_from_range(rng) == 3


def test_a_non_ringgit_range_is_refused_rather_than_converted():
    """A USD range would silently become a wrong ringgit band. We do not hold an
    exchange rate and inventing one is worse than saying nothing."""
    rng = {'startPrice': {'currencyCode': 'USD', 'units': '10'}, 'endPrice': {'currencyCode': 'USD', 'units': '20'}}
    assert price_band_from_range(rng) is None


def test_a_malformed_or_missing_range_is_none():
    for bad in [None, {}, {'startPrice': {}}, 'RM1-20', 42]:
        assert price_band_from_range(bad) is None


def test_a_review_becomes_a_post_carrying_its_own_identity():
    """Google has no per-review URL, so the citation points at the place page.
    The review NAME is what makes two reviews of one venue distinct -- deduping
    on the URL collapsed three reviewers into one citation (#153)."""
    rv = {
        'name': 'places/ChIJabc/reviews/xyz789',
        'rating': 4,
        'text': {'text': 'The nasi lemak was excellent and the sambal had real heat.'},
        'relativePublishTimeDescription': '2 months ago',
        'authorAttribution': {'displayName': 'A Reviewer'},
    }
    post = review_to_post(rv, 'ChIJabc', 'Village Park')
    assert post['platform_post_id'] == 'places/ChIJabc/reviews/xyz789'
    assert 'nasi lemak' in post['raw_text']
    assert post['sentiment'] == 0.5
    assert post['posted_at_raw'] == '2 months ago'
    assert post['author_handle'] == 'A Reviewer'
    assert 'ChIJabc' in post['url']


def test_the_star_rating_is_the_sentiment_not_a_model_call():
    """The rating IS the writer's judgement stated numerically. Asking a model to
    infer it from the prose would be less accurate and cost a call per review."""
    for stars, s in [(1, -1.0), (2, -0.5), (3, 0.0), (4, 0.5), (5, 1.0)]:
        rv = {'name': 'r', 'rating': stars, 'text': {'text': 'x' * 40}}
        assert review_to_post(rv, 'p', 'v')['sentiment'] == s


def test_a_review_with_no_usable_text_is_dropped():
    """A star with no prose cites nothing, and a citation with no excerpt is the
    thing the product promises never to return."""
    for bad in [{'name': 'r', 'rating': 5}, {'name': 'r', 'rating': 5, 'text': {'text': '   '}}]:
        assert review_to_post(bad, 'p', 'v') is None


def test_original_text_is_used_when_the_translation_is_absent():
    """Malay and Chinese reviews often carry only originalText."""
    rv = {'name': 'r', 'rating': 5, 'originalText': {'text': '这家的肉骨茶非常好吃，汤头浓郁'}}
    post = review_to_post(rv, 'p', 'v')
    assert '肉骨茶' in post['raw_text']


def test_a_scraped_hex_cid_is_not_an_api_place_id():
    """The CDP path stored the `!1s0x...:0x...` pair out of the Maps URL. That is
    a CID, not a Places API place ID, and handing it to the API returns 400
    INVALID_ARGUMENT. 809 of 821 stored ids are this shape, so trusting the
    column without checking sent one bad request per venue -- 505 of them in a
    single run before it was stopped."""
    from ingest.places_api import is_api_place_id

    assert is_api_place_id('0x31cc49e5fd3b1b39:0x5876916611066eab') is False
    assert is_api_place_id('0x31cc3775aebb642f:0x4837e0e3660a4111') is False


def test_a_real_api_place_id_is_accepted():
    from ingest.places_api import is_api_place_id

    assert is_api_place_id('ChIJIfYLMzFJzDERPG9vHZ7DqiE') is True


def test_absent_or_malformed_ids_are_refused():
    from ingest.places_api import is_api_place_id

    for bad in [None, '', '   ', 42, [], '0x123']:
        assert is_api_place_id(bad) is False

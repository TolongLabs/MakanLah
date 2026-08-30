"""Sentiment is reported as counts, never as an average.

871 of 1653 mentions sit at exactly 1.0, so a mean reads "excellent" on nearly
every venue. Counts carry information a mean cannot: 163 of 186 multi-mention
venues span more than one bucket, and 73 of 247 carry at least one negative.
"""

from makanlah.db import sentiment_bucket, tally_sentiment


def test_the_top_of_the_scale_is_positive():
    assert sentiment_bucket(1.0) == 'positive'
    assert sentiment_bucket(0.6) == 'positive'


def test_the_middle_is_mixed_not_positive():
    # 0.5 is the second most common value in the corpus. Calling it positive
    # would put nearly everything in one bucket and empty the signal.
    assert sentiment_bucket(0.5) == 'mixed'
    assert sentiment_bucket(0.0) == 'mixed'
    assert sentiment_bucket(-0.1) == 'mixed'


def test_a_single_critic_is_not_rounded_away():
    # The negative boundary is deliberately closer to zero than the positive one:
    # one person saying a place was bad is worth surfacing even when nine disagree.
    assert sentiment_bucket(-0.2) == 'negative'
    assert sentiment_bucket(-0.5) == 'negative'
    assert sentiment_bucket(-1.0) == 'negative'


def test_a_missing_score_is_not_a_bucket():
    # None must not silently become 'mixed' -- that would invent a mention.
    assert sentiment_bucket(None) is None


def test_the_thresholds_are_asymmetric_on_purpose():
    # Guards the asymmetry itself: a symmetric split at +/-0.6 would file every
    # mild complaint as 'mixed' and the negative bucket would almost never fill.
    assert sentiment_bucket(-0.3) == 'negative'
    assert sentiment_bucket(0.3) == 'mixed'


def _row(venue_id, post_url, sentiment, dead=None):
    return {'venue_id': venue_id, 'post_url': post_url, 'sentiment': sentiment, 'dead': dead}


def test_one_post_is_one_vote_however_many_mentions_it_makes():
    # The defect this file now guards: a post naming a venue three times counted
    # three times, so a card read "1 post" and "All 3 posts positive" at once.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p1', 1.0), _row('v1', 'p1', 1.0)]
    assert tally_sentiment(rows)['v1'] == {'positive': 1, 'mixed': 0, 'negative': 0}


def test_a_dead_post_casts_no_vote():
    # #111 again: a breakdown counting posts a reader cannot open is an assertion
    # with no evidence behind it, which is the one thing this product must not do.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p2', 1.0, dead=True)]
    assert tally_sentiment(rows)['v1'] == {'positive': 1, 'mixed': 0, 'negative': 0}


def test_a_venue_whose_every_post_is_dead_reports_nothing():
    assert tally_sentiment([_row('v1', 'p1', 1.0, dead=True)]) == {}


def test_the_harshest_line_in_a_post_is_the_one_that_counts():
    # Averaging within a post would let a complaint be cancelled by the same
    # author's milder sentences.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p1', -0.9)]
    assert tally_sentiment(rows)['v1'] == {'positive': 0, 'mixed': 0, 'negative': 1}


def test_totals_equal_the_number_of_live_posts():
    # The invariant the client gates on: sum(sentiment) must equal the post count
    # the corroboration line shows, or the card stays dark.
    rows = [
        _row('v1', 'p1', 1.0),
        _row('v1', 'p1', 0.5),
        _row('v1', 'p2', -0.5),
        _row('v1', 'p3', 0.0),
        _row('v1', 'p4', 1.0, dead=True),
    ]
    counts = tally_sentiment(rows)['v1']
    assert sum(counts.values()) == 3


def test_venues_are_counted_separately():
    rows = [_row('v1', 'p1', 1.0), _row('v2', 'p1', -1.0)]
    got = tally_sentiment(rows)
    assert got['v1'] == {'positive': 1, 'mixed': 0, 'negative': 0}
    assert got['v2'] == {'positive': 0, 'mixed': 0, 'negative': 1}


def test_only_the_posts_the_card_shows_are_counted():
    # citations are trimmed to per_venue before they ship and add_corroboration
    # counts what survives. Tallying every live post in the corpus gave Village Park
    # 7 sentiment against 3 posts -- four real posts that were not on the card.
    rows = [_row('v1', f'p{i}', 1.0) for i in range(1, 8)]
    kept = {'v1': {'p1', 'p2', 'p3'}}
    assert sum(tally_sentiment(rows, kept)['v1'].values()) == 3


def test_a_kept_set_that_excludes_everything_reports_nothing():
    assert tally_sentiment([_row('v1', 'p1', 1.0)], {'v1': set()}) == {}


def test_no_kept_set_means_count_every_live_post():
    # The two-argument form must stay usable without the filter, or the pure
    # function silently changes meaning for any other caller.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p2', -1.0)]
    assert sum(tally_sentiment(rows)['v1'].values()) == 2

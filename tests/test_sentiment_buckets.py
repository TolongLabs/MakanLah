"""Sentiment is reported as counts, never as an average.

871 of 1653 mentions sit at exactly 1.0, so a mean reads "excellent" on nearly
every venue. Counts carry information a mean cannot: 163 of 186 multi-mention
venues span more than one bucket, and 73 of 247 carry at least one negative.
"""

from makanlah.db import sentiment_bucket


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

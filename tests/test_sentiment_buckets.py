"""Sentiment is reported as counts, never as an average.

871 of 1653 mentions sit at exactly 1.0, so a mean reads "excellent" on nearly
every venue. Counts carry information a mean cannot: 163 of 186 multi-mention
venues span more than one bucket, and 73 of 247 carry at least one negative.
"""

from makanlah.db import sentiment_bucket, tally_sentiment


def test_four_and_five_stars_are_positive():
    # star_sentiment is (stars - 3) / 2, so 0.5 is a four-star review. Filing that
    # as 'mixed' invents a reservation the reviewer did not express.
    assert sentiment_bucket(1.0) == 'positive'
    assert sentiment_bucket(0.5) == 'positive'


def test_three_stars_and_mild_qualification_are_mixed():
    # -0.2 was the old negative boundary and it caught an odd drink and a room
    # called plain, which the card then reported as a critical verdict (#149).
    assert sentiment_bucket(0.0) == 'mixed'
    assert sentiment_bucket(-0.2) == 'mixed'
    assert sentiment_bucket(-0.3) == 'mixed'


def test_one_and_two_stars_are_critical():
    assert sentiment_bucket(-0.5) == 'negative'
    assert sentiment_bucket(-1.0) == 'negative'


def test_a_missing_score_is_not_a_bucket():
    # None must not silently become 'mixed' -- that would invent a mention.
    assert sentiment_bucket(None) is None


def test_the_cut_points_sit_on_the_star_scale():
    # The scale most of these scores come from: 4-5 positive, 3 mixed, 1-2 critical.
    assert [sentiment_bucket((n - 3) / 2) for n in (1, 2, 3, 4, 5)] == [
        'negative',
        'negative',
        'mixed',
        'positive',
        'positive',
    ]
    assert sentiment_bucket(0.3) == 'mixed'


def _row(venue_id, post_url, sentiment, dead=None, post_id=None):
    # post_id defaults to post_url so a case that does not care reads unchanged; the
    # Maps cases pass them separately, because that is the whole point of #153.
    return {
        'venue_id': venue_id,
        'post_id': post_id or post_url,
        'post_url': post_url,
        'sentiment': sentiment,
        'dead': dead,
    }


def test_one_post_is_one_vote_however_many_mentions_it_makes():
    # The defect this file now guards: a post naming a venue three times counted
    # three times, so a card read "1 post" and "All 3 posts positive" at once.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p1', 1.0), _row('v1', 'p1', 1.0)]
    assert tally_sentiment(rows)['v1'] == {'positive': 1, 'mixed': 0, 'negative': 0}


def test_a_dead_post_on_the_card_does_vote():
    # The opposite of what corroboration does, deliberately. Corroboration claims a
    # reader can go and check two independent people, so a post nobody can open is
    # not a second source (#111). This summarises the testimony ON the card, and the
    # card shows dead citations -- labelled, but shown. 1919餐馆 displayed 「别去」
    # (don't go) and read "all positive" because the tally skipped the dead post the
    # reader was looking at. What we show is what we count.
    rows = [_row('v1', 'p1', 1.0), _row('v1', 'p2', -1.0, dead=True)]
    assert tally_sentiment(rows)['v1'] == {'positive': 1, 'mixed': 0, 'negative': 1}


def test_a_venue_whose_every_post_is_dead_still_reports_what_it_shows():
    # Its citations are still rendered, so a silent breakdown beside a visible
    # excerpt is the same contradiction in the other direction.
    assert tally_sentiment([_row('v1', 'p1', 1.0, dead=True)])['v1']['positive'] == 1


def test_mentions_behind_one_url_are_averaged_not_reduced_to_the_worst():
    # post_url is not one author. Maps has no per-review URL, so 1,388 mentions
    # share 178 URLs and the worst-wins rule turned one 1-star review into a verdict
    # on eight (#149). 王美记's eight Maps reviews mean +0.19 -- genuinely mixed.
    rows = [_row('v1', 'p1', s) for s in (-1.0, -0.5, -0.5, 0.5, 0.5, 0.5, 1.0, 1.0)]
    assert tally_sentiment(rows)['v1'] == {'positive': 0, 'mixed': 1, 'negative': 0}


def test_a_lone_bad_review_is_still_reported_as_bad():
    # Averaging must not become a way of hiding criticism: one review, one identity,
    # nothing to average it against.
    assert tally_sentiment([_row('v1', 'p1', -1.0)])['v1']['negative'] == 1


def test_totals_equal_the_number_of_posts_shown():
    # The client reads `sentiment_posts` rather than inferring agreement with
    # corroboration.posts, which counts a different set on purpose: corroboration
    # excludes dead posts, this does not.
    rows = [
        _row('v1', 'p1', 1.0),
        _row('v1', 'p1', 0.9),
        _row('v1', 'p2', -0.5),
        _row('v1', 'p3', 0.0),
        _row('v1', 'p4', 1.0, dead=True),
    ]
    counts = tally_sentiment(rows)['v1']
    assert sum(counts.values()) == 4


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


def test_the_cut_separates_a_verdict_from_a_qualification():
    """Read by hand across all 14 negative RedNote mentions in the corpus (#155).

    RedNote has no stars; the extraction model scores it continuously, and it
    compresses negative text -- a post saying 不推荐 twice scores only -0.4. These
    are the two sides of where that population actually separates.
    """
    # 王美记: "不推荐" twice, "性价比很低", dry chicken, char siew not freshly made.
    assert sentiment_bucket(-0.4) == 'negative'
    # 兴记: "中规中矩... 特意去没必要" -- mediocre, not worth a special trip.
    assert sentiment_bucket(-0.3) == 'mixed'
    # 海脚人: "可吃可不吃" -- take it or leave it.
    assert sentiment_bucket(-0.2) == 'mixed'


def test_the_cut_does_not_move_google_maps():
    """Maps is quantised by star_sentiment, so only RedNote feels the exact value.

    Guards the reasoning that made -0.4 safe to pick: if a future change puts a
    Maps score between -0.5 and 0, the two platforms stop being separable this way.
    """
    assert [sentiment_bucket((n - 3) / 2) for n in (1, 2, 3, 4, 5)] == [
        'negative',
        'negative',
        'mixed',
        'positive',
        'positive',
    ]

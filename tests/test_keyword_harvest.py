"""#159: the scraper's vocabulary must come from the corpus, not from a typed list.

554 distinct hashtags sit in 120 captured posts and not one has ever been searched.
Harvesting them is the snowball: capture -> harvest -> search -> capture more.
"""

import pytest

from ingest.keywords import harvest_tags


def test_ranks_by_frequency_and_strips_the_hash():
    posts = [
        {'tags': ['#kl探店', '#klcafe']},
        {'tags': ['#kl探店']},
        {'tags': ['#kl探店', '#klcafe']},
        {'tags': ['#pjcafe']},
    ]
    assert harvest_tags(posts, known=[]) == [('kl探店', 3), ('klcafe', 2), ('pjcafe', 1)]


def test_excludes_terms_already_in_the_keyword_list():
    """A keyword we already search is not a discovery. This is the whole point:
    the caller passes KEYWORDS and gets back only what is genuinely new."""
    posts = [{'tags': ['#吉隆坡美食', '#吉隆坡探店']}]
    assert harvest_tags(posts, known=['吉隆坡美食']) == [('吉隆坡探店', 1)]


def test_exclusion_ignores_case_and_the_hash_on_either_side():
    posts = [{'tags': ['#KLCafe', '#kl food', '#pjcafe']}]
    out = dict(harvest_tags(posts, known=['klcafe', '#KL Food']))
    assert 'pjcafe' in out
    assert 'KLCafe' not in out and 'klcafe' not in out
    assert 'kl food' not in out


def test_ties_break_alphabetically_so_the_order_is_deterministic():
    posts = [{'tags': ['#zzz', '#aaa', '#mmm']}]
    assert harvest_tags(posts, known=[]) == [('aaa', 1), ('mmm', 1), ('zzz', 1)]


def test_posts_without_tags_are_normal_not_an_error():
    """5 of 120 cached posts carry no tags. A missing key is a normal outcome."""
    assert harvest_tags([{'tags': []}, {}, {'tags': None}], known=[]) == []


def test_whitespace_only_and_bare_hash_tags_are_dropped():
    posts = [{'tags': ['#', '  ', '#real']}]
    assert harvest_tags(posts, known=[]) == [('real', 1)]


@pytest.mark.parametrize('bad', ['notalist', 42, None])
def test_a_malformed_tags_field_drops_the_post_and_continues(bad):
    """AGENTS.md: a bad row is dropped and counted, never an aborted batch."""
    assert harvest_tags([{'tags': bad}, {'tags': ['#ok']}], known=[]) == [('ok', 1)]

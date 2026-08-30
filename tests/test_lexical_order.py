"""The lexical lane must hand the re-ranker its best candidates, not its first.

`models.rerank` reads only the first RERANK_CANDIDATES (16) of whatever it is
given. The lexical lane was built by iterating `venue_dishes`, whose order is
whatever the query returned, so with a small corpus the 16 covered nearly every
match and the arbitrariness never showed.

At 823 venues it shows badly. `nasi lemak` matched 192 venues, the first 16 by
dict order reached the model, and **one** came back -- on the most written-about
dish in the corpus, from a user standing in the middle of the city.

`filter_candidates` already returns candidates nearest-first. Preserving that
order costs nothing and makes the 16 the sixteen NEAREST places serving the
dish, which is what someone deciding where to eat in the next two minutes wants.
"""

from makanlah.rank import lexical_hits


def test_hits_come_back_in_candidate_order_not_dict_order():
    """candidate_ids is distance-ordered, so the output must be too."""
    candidate_ids = ['near', 'mid', 'far']
    tags = {'far': ['nasi lemak'], 'near': ['nasi lemak'], 'mid': ['nasi lemak']}
    assert lexical_hits(candidate_ids, tags, {'nasi lemak'}) == ['near', 'mid', 'far']


def test_only_venues_carrying_a_named_dish_are_hits():
    candidate_ids = ['a', 'b', 'c']
    tags = {'a': ['nasi lemak'], 'b': ['satay'], 'c': ['nasi lemak', 'teh']}
    assert lexical_hits(candidate_ids, tags, {'nasi lemak'}) == ['a', 'c']


def test_no_named_dish_means_no_lexical_lane():
    assert lexical_hits(['a'], {'a': ['nasi lemak']}, set()) == []
    assert lexical_hits(['a'], {'a': ['nasi lemak']}, None) == []


def test_a_candidate_with_no_tags_is_skipped_not_an_error():
    assert lexical_hits(['a', 'b'], {'b': ['nasi lemak']}, {'nasi lemak'}) == ['b']


def test_the_order_is_stable_across_calls():
    ids = [f'v{i}' for i in range(40)]
    tags = {i: ['nasi lemak'] for i in reversed(ids)}
    assert lexical_hits(ids, tags, {'nasi lemak'}) == lexical_hits(ids, tags, {'nasi lemak'}) == ids


def test_a_venue_written_about_repeatedly_for_the_dish_outranks_a_passing_mention():
    """Distance alone is not enough once review text is tagged. Tagging Maps
    reviews took `nasi lemak` from a handful of venues to 192, most of which
    merely mention it once -- so the sixteen nearest were vegetarian caterers
    and the actual nasi lemak shops never reached the model."""
    ids = ['near_weak', 'far_strong']
    tags = {'near_weak': ['nasi lemak'], 'far_strong': ['nasi lemak']}
    counts = {'near_weak': {'nasi lemak': 1}, 'far_strong': {'nasi lemak': 9}}
    assert lexical_hits(ids, tags, {'nasi lemak'}, counts) == ['far_strong', 'near_weak']


def test_equal_strength_falls_back_to_candidate_order():
    """Nearest-first is the right tie-break: same evidence, closer wins."""
    ids = ['near', 'far']
    tags = {'near': ['nasi lemak'], 'far': ['nasi lemak']}
    counts = {'near': {'nasi lemak': 3}, 'far': {'nasi lemak': 3}}
    assert lexical_hits(ids, tags, {'nasi lemak'}, counts) == ['near', 'far']


def test_strength_sums_across_every_matching_dish_form():
    """`named` can hold several folded spellings of one dish."""
    ids = ['a', 'b']
    tags = {'a': ['nasi lemak', 'Nasi Lemak'], 'b': ['nasi lemak']}
    counts = {'a': {'nasi lemak': 2, 'Nasi Lemak': 3}, 'b': {'nasi lemak': 4}}
    assert lexical_hits(ids, tags, {'nasi lemak'}, counts) == ['a', 'b']


def test_without_counts_the_order_is_still_candidate_order():
    ids = ['a', 'b']
    tags = {'b': ['nasi lemak'], 'a': ['nasi lemak']}
    assert lexical_hits(ids, tags, {'nasi lemak'}) == ['a', 'b']

"""Maps reviews name dishes and the corpus stores none of them.

`enrich_gmaps` writes every Maps mention with `dishes=[]`, so 84% of the evidence
is invisible to the lexical dish lane. A venue known only from Maps cannot be
found by asking for what it serves. Measured consequence: `roti canai` returns 0
results across the whole city while two RedNote venues carry the tag and dozens of
Maps-enriched Indian restaurants have reviews that name it.

The matching rule is the one that survived three failures on 2026-08-28:
**whole-word for Latin, substring for Han.** `踩雷` inside `不踩雷` inverted a
sentiment, `ckt` inside `mocktail` invented a dish, and `length < 3` flagged
`鱼你` -- but 肉骨茶 inside 中药肉骨茶 is genuinely the same dish.
"""

from makanlah.dishes import dishes_in_text

VOCAB = frozenset({'roti canai', 'nasi lemak', 'char kway teow', 'bak kut teh', '肉骨茶', '蛋挞', 'chicken rice'})


def test_finds_a_dish_named_in_a_review():
    got = dishes_in_text('The roti canai here is flaky and cheap, we come every Sunday', VOCAB)
    assert 'roti canai' in got


def test_finds_several_dishes_in_one_review():
    got = dishes_in_text('Had the nasi lemak and the chicken rice. Both solid.', VOCAB)
    assert set(got) == {'nasi lemak', 'chicken rice'}


def test_a_latin_dish_must_match_on_word_boundaries():
    """`ckt` inside `mocktail` was a real invented dish. Latin is whole-word."""
    assert dishes_in_text('their mocktail selection is good', frozenset({'ckt'})) == []
    assert dishes_in_text('the ckt was smoky', frozenset({'ckt'})) == ['ckt']


def test_a_han_dish_matches_as_a_substring():
    """肉骨茶 inside 中药肉骨茶 is genuinely the same dish, so Han is substring."""
    assert '肉骨茶' in dishes_in_text('这家的中药肉骨茶很香', VOCAB)


def test_a_han_dish_is_found_without_surrounding_spaces():
    """Chinese does not delimit words, so a whole-word rule finds nothing at all."""
    assert '蛋挞' in dishes_in_text('必点蛋挞和奶茶', VOCAB)


def test_a_dish_not_in_the_vocabulary_is_never_invented():
    assert dishes_in_text('the beef rendang was incredible', VOCAB) == []


def test_returns_nothing_for_empty_or_non_text():
    for bad in ['', None, 42, []]:
        assert dishes_in_text(bad, VOCAB) == []


def test_an_empty_vocabulary_finds_nothing():
    assert dishes_in_text('roti canai and nasi lemak', frozenset()) == []


def test_the_result_is_deduped_and_ordered_so_two_runs_agree():
    got = dishes_in_text('roti canai, more roti canai, and nasi lemak', VOCAB)
    assert got == sorted(set(got))
    assert got.count('roti canai') == 1


def test_a_very_long_review_is_still_scanned():
    """dish_named_inside caps at 12 words because it reads a QUERY. A review is
    not a query, and capping it would silently skip most of the corpus."""
    text = 'padding word ' * 200 + 'and finally the roti canai arrived'
    assert 'roti canai' in dishes_in_text(text, VOCAB)


def test_case_variants_in_the_vocabulary_yield_one_tag_not_three():
    """The corpus carries `Nasi Lemak`, `nasi lemak`, `Fried Chicken`, `Fried
    chicken` and `fried chicken` as separate strings, because different posts
    spelled them differently. Writing all of them onto one review makes a venue
    look like it serves three dishes when the reviewer named one -- the same
    count-that-is-false-as-English shape as #87 and #153. Measured: 166 of 773
    rows carried at least one such duplicate."""
    vocab = frozenset({'Nasi Lemak', 'nasi lemak', 'Fried Chicken', 'Fried chicken', 'fried chicken'})
    got = dishes_in_text('the nasi lemak and the fried chicken were both good', vocab)
    assert len(got) == 2, got
    assert {g.casefold() for g in got} == {'nasi lemak', 'fried chicken'}


def test_the_surviving_spelling_is_stable_across_runs():
    vocab = frozenset({'Nasi Lemak', 'nasi lemak', 'NASI LEMAK'})
    assert dishes_in_text('nasi lemak here', vocab) == dishes_in_text('nasi lemak here', vocab)
    assert len(dishes_in_text('nasi lemak here', vocab)) == 1

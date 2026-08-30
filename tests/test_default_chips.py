"""What the app offers before you have told it anything.

The six chips on /discover are the only surface every user meets unprompted, and
they were ranked on raw corpus frequency alone: `soup` 535, `rice` 473, `chicken`
471, **`pork` 316**, `curry` 195, `fish` 189. In a Muslim-majority market that
makes the one universal surface an accident of what the scraper happened to read.

**This is a neutral-defaults decision and NOT a halal safeguard**, and the
distinction is load-bearing. @makanlah-92 measured that the `soup` chip -- which
stays -- returns three bak kut teh houses in its top six, with `pork` rendered as
a visible dish tag. So the chip row still exposes pork one tap in. What changes
is that the app no longer *offers* it unprompted; what does not change is that a
user can still meet it. Calling this a safeguard would overclaim exactly where
`rank.py` says overclaiming is unforgivable.

**No non-halal dish list.** A list catching `pork` but missing `siu yuk`,
`char siew`, `babi` or `肉骨茶` looks like a safeguard and is not, and three
hand-written heuristics over food terms failed in one day on 2026-08-28. This
excludes terms that name pork *in so many words*, from the default pool only.
Search, ranking and every dish tag are untouched.
"""

from makanlah.suggest import DEFAULT_POOL_EXCLUDED, offerable


def test_a_chip_that_says_pork_is_not_offered_unprompted():
    assert offerable('pork') is False
    assert offerable('Pork') is False
    assert offerable('  PORK  ') is False


def test_the_same_word_in_another_language_is_also_not_offered():
    """Excluding the English spelling only would be theatre."""
    for t in ['babi', '猪肉', '豬肉']:
        assert offerable(t) is False, t


def test_a_dish_that_merely_contains_pork_is_still_offered():
    """The line is what the chip SAYS, not what the dish contains. `bak kut teh`
    stays because excluding it would be the dietary list this refuses to build --
    and it would remove the most iconic thing in this corpus from the Chinese
    Malaysian audience it belongs to."""
    for t in ['bak kut teh', '肉骨茶', 'char siew', 'siu yuk', 'wantan mee']:
        assert offerable(t) is True, t


def test_everything_else_is_offerable():
    for t in ['nasi lemak', 'soup', 'rice', 'chicken', 'laksa', 'roti canai', '蛋挞']:
        assert offerable(t) is True, t


def test_empty_or_non_text_is_not_offerable():
    for t in [None, '', '   ', 42]:
        assert offerable(t) is False


def test_the_excluded_set_stays_small_and_literal():
    """If this grows into a cuisine filter, it has become the thing the module
    docstring refuses to be. Six terms is a spelling list, not a dietary one."""
    assert len(DEFAULT_POOL_EXCLUDED) <= 6


def test_the_spelling_list_catches_the_word_inside_a_longer_label():
    """`sup tulang babi` names pork in so many words and was still offerable.

    The exclusion compared the WHOLE label against four strings, so it only ever
    caught a chip labelled exactly `pork`. Anything carrying the term as one word
    of several walked straight through -- which is the list failing at its own
    documented job, not the cuisine question it deliberately declines.
    """
    assert offerable('sup tulang babi') is False
    assert offerable('babi panggang') is False
    assert offerable('pork chop') is False
    assert offerable('minced pork noodle') is False


def test_the_deliberate_decision_is_not_quietly_reversed():
    """`bak kut teh` stays offerable. That is a recorded call, not an oversight.

    Widening to whole-word matching must not become the hand-written non-halal
    list `suggest.py` refuses to build. Han matching is substring by project rule,
    so this also pins that `猪肉` does not appear inside `肉骨茶` and cannot catch
    it by accident.
    """
    for dish in ('bak kut teh', 'bkt', '肉骨茶', '中药肉骨茶', 'char siew', 'siu yuk'):
        assert offerable(dish) is True, dish


def test_a_word_boundary_is_a_boundary_not_a_substring():
    """Latin is whole-word, so a term buried in an unrelated word does not match."""
    assert offerable('porkkala') is True
    assert offerable('babika') is True

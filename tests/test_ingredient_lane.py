"""Ingredient queries must reach the dish lane (#140).

Measured on the live corpus: 14 of 14 common ingredients returned None from
`canonical_for_query`, while `crab` alone appears in 9 distinct dish strings. A
`crab` search on prod returned five venues all on the semantic lane, one of them a
Hainanese chicken rice shop, while `Roe Crab` and `Flower crab in spicy tomato
cream sauce` sat in the corpus unmatched.
"""

from makanlah.dishes import named_in

# Real dish strings from the corpus, verbatim.
VOCAB = frozenset(
    {
        'roe crab',
        'flower crab in spicy tomato cream sauce',
        'salted white pepper prawns',
        '海南鸡饭',
        'hainanese chicken rice',
        'roasted chicken',
        'char siew',
        'nasi lemak',
        'eggplant with minced pork',
        'century egg porridge',
        'beef noodle soup',
        'seafood pottage with rice',
    }
)


def test_an_ingredient_reaches_the_dishes_that_contain_it():
    found, label = named_in('crab', VOCAB)
    assert 'roe crab' in found
    assert 'flower crab in spicy tomato cream sauce' in found
    assert label


def test_chicken_reaches_chicken_dishes():
    found, _ = named_in('chicken', VOCAB)
    assert 'roasted chicken' in found
    assert 'hainanese chicken rice' in found


def test_an_ingredient_does_not_match_a_word_that_merely_starts_the_same():
    # 'egg' inside 'eggplant' is a different food. Substring matching without a
    # word boundary would put aubergine on an egg query.
    found, _ = named_in('egg', VOCAB)
    assert 'eggplant with minced pork' not in found
    assert 'century egg porridge' in found


def test_an_ingredient_does_not_drag_in_unrelated_dishes():
    found, _ = named_in('crab', VOCAB)
    assert 'nasi lemak' not in found
    assert 'hainanese chicken rice' not in found


def test_a_mood_query_still_names_no_dish():
    # The property that keeps vague queries on the semantic lane, which is what it
    # is for. An ingredient lane must not turn every sentence into a dish match.
    assert named_in('somewhere nice for dinner', VOCAB)[0] == frozenset()
    assert named_in('something not too heavy', VOCAB)[0] == frozenset()


def test_a_named_dish_still_resolves_exactly_as_before():
    found, label = named_in('nasi lemak', VOCAB)
    assert 'nasi lemak' in found
    assert label == 'nasi lemak'

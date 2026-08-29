"""Which dish a query names, when the vocabulary is the corpus rather than a list.

`dishes.DISH_ALIASES` hand-lists fifteen dishes. The corpus carries 838 distinct
dish strings across 1033 dish-mentions, so the hand table recognised **12.3% of
strings, 18.1% of mentions, and 0 of 10 mixed-script strings** (#85). Every case
below that is marked "was invisible" is one the old lane returned nothing for and
was measured present in the live corpus.

The vocabulary here is a fixture, not the database, so the suite stays hermetic --
docs/TRD.md is explicit that a check hitting live infrastructure fails when a
session expires and teaches everyone to ignore red.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from makanlah import dishes

# Real strings, taken from the live corpus with their venue counts, including the
# spelling mistakes. `cha seiw` is a genuine row and is why near-matching exists.
VOCAB = frozenset(
    {
        'nasi lemak',
        '椰浆饭',
        '肉骨茶',
        '干肉骨茶',
        '汤肉骨茶',
        'bak kut teh',
        '蛋挞',
        'char siew',
        'cha seiw',
        'coffee',
        '咖啡',
        'ayam gepuk',
        'ramen',
        'local food',
        'pork',
        'rice',
        'cendol 冰',
        'matcha latte',
        'noodle',
        'noodles',
        'rosated chicken',
        'roasted chicken',
    }
)


def names(query):
    return dishes.named_in(query, VOCAB)


class TestTheCorpusIsTheVocabulary:
    @pytest.mark.parametrize(
        ('query', 'expected'),
        [('coffee', 'coffee'), ('咖啡', '咖啡'), ('ayam gepuk', 'ayam gepuk'), ('ramen', 'ramen')],
    )
    def test_dishes_measured_present_and_still_outside_the_hand_table(self, query, expected):
        """Each of these was measured in the live corpus -- `coffee` 7 venues,
        `咖啡` 5, `ayam gepuk` 4, `ramen` 1 -- and each returns None from the hand
        table. They resolve because the vocabulary is the corpus, and they are the
        cases that prove it: extending the hand table by two entries below does not
        make these pass."""
        assert dishes.canonical_for_query(query) is None
        found, _ = names(query)
        assert expected in found

    def test_the_lane_does_not_depend_on_the_hand_table_growing(self):
        """The structural claim, stated once so it cannot be quietly lost by adding
        aliases. 838 corpus strings against fifteen hand-listed dishes is not a gap
        anybody closes by typing; the vocabulary has to be the data."""
        outside = [v for v in VOCAB if dishes.canonical(v) is None]
        assert outside, 'fixture no longer exercises the corpus lane at all'
        for v in outside:
            assert v in names(v)[0]

    def test_case_and_width_fold_onto_one_key(self):
        assert names('Char Siew')[0] == names('char siew')[0]
        # NFKC: a full-width copy is the same dish to a person reading it.
        assert 'coffee' in names('ｃｏｆｆｅｅ')[0]


class TestTwoAliasesAddedFromMeasurement:
    """#85 measured both. The corpus tags 叉烧杨家家来 with `叉烧` and Oh Yeah
    Kopitiam with `Char Siew`, and nothing joined them; `egg tart` found nothing
    while `蛋挞` found two venues. Folding cannot bridge either -- only the table can."""

    def test_an_english_query_reaches_the_chinese_tag(self):
        assert '蛋挞' in names('egg tart')[0]

    def test_a_chinese_query_reaches_the_english_tag(self):
        assert 'char siew' in names('叉烧')[0]

    def test_no_short_form_swallows_its_container(self):
        """`canonical()` matches on substring in BOTH directions, so adding `pork`
        or `bbq pork` as a char siew alias would fold `roast pork`, `pork noodles`
        and `braised pork rice` into it. This is why neither is in the table, and
        this test is what stops the next person adding them."""
        assert dishes.canonical('roast pork') != 'char siew'
        assert dishes.canonical('braised pork rice') != 'char siew'
        assert dishes.canonical('pork') != 'char siew'


class TestTheAliasTableStillDoesTheJobFoldingCannot:
    def test_a_query_in_one_language_reaches_venues_tagged_in_another(self):
        """No amount of string folding turns `bak kut teh` into `肉骨茶`. This is
        the whole remaining purpose of the hand table and it must not regress."""
        found, label = names('bak kut teh')
        assert label == 'bak kut teh'
        assert {'肉骨茶', '干肉骨茶', '汤肉骨茶', 'bak kut teh'} <= found

    def test_the_alias_lane_wins_over_a_bare_exact_match(self):
        # `肉骨茶` is in the vocabulary verbatim, but answering with only that row
        # would drop the venues tagged in the other language and the two variants.
        found, _ = names('肉骨茶')
        assert len(found) > 1


class TestNearMatchIsForTheCorpusOwnTypos:
    def test_a_correctly_spelled_query_reaches_the_rows_spelled_differently(self):
        """The lanes union rather than stopping at the first hit, so a query does
        not lose the near rows just because it matched exactly. Both pairs here are
        from the measured set: 29 near-pairs across the whole 810-key vocabulary,
        no key with more than two neighbours, and every one of them the same dish
        twice."""
        assert {'noodle', 'noodles'} <= names('noodles')[0]
        assert {'roasted chicken', 'rosated chicken'} <= names('roasted chicken')[0]

    def test_a_typo_far_enough_out_is_still_only_reachable_by_repeating_it(self):
        """The honest limit of this. `cha seiw` is 0.82 from `char siew`, under the
        0.85 cutoff, so that venue is found by somebody misspelling it the same way
        and not by somebody spelling it right. Lowering the cutoff to reach it is
        what let `halal food` match `local food`, so it stays out of reach and this
        records why rather than leaving it to be rediscovered."""
        assert 'cha seiw' not in names('char siew')[0]
        assert 'cha seiw' in names('cha siew')[0]

    def test_a_misspelling_reaches_the_dish(self):
        assert 'char siew' in names('cha siew')[0]
        assert 'nasi lemak' in names('nasi lemat')[0]

    def test_it_does_not_answer_a_dietary_question_with_a_food_word(self):
        """At cutoff 0.80 `halal food` matched `local food`, which is a lexical
        lane answering a question about religious dietary law with somebody's word
        for cheap. 0.85 is where that stops. The corpus carries no halal signal at
        all (#86) and the honest result here is nothing."""
        assert names('halal food')[0] == frozenset()

    def test_a_fragment_is_not_guessed_at(self):
        # Under MIN_NEAR_LEN. `pork` and `rice` are in the vocabulary and resolve
        # exactly; it is the three-letter stubs that must not be near-matched.
        assert names('por')[0] == frozenset()
        assert 'pork' in names('pork')[0]


class TestAMoodQueryStaysOnTheSemanticLane:
    @pytest.mark.parametrize(
        'query',
        [
            'something not too heavy',
            'a light dinner near me',
            'cheap eats',
            'somewhere nice for a first date',
            'sedap tak mahal',
        ],
    )
    def test_it_names_no_dish(self, query):
        """The lexical lane reorders results ahead of the vector lane. A mood query
        that matched anything would put one arbitrary dish in front of a question
        that was not about a dish."""
        assert names(query) == (frozenset(), None)

    def test_an_empty_or_enormous_query_names_nothing(self):
        assert names('')[0] == frozenset()
        assert names(None)[0] == frozenset()
        assert names('x' * 41)[0] == frozenset()


class TestWhatIsAbsentStaysAbsent:
    @pytest.mark.parametrize('query', ['ayam goreng berempah', 'char kuey teow', 'poutine', 'borscht'])
    def test_a_dish_the_corpus_does_not_carry_matches_nothing(self, query):
        """Measured against the live corpus: none of these exist in it in any
        spelling. The lane must not invent a match -- #98 is about the fact that
        the app still answers these from the vector lane, and a lexical lane that
        guessed here would make that worse rather than better."""
        assert names(query)[0] == frozenset()

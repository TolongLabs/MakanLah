"""Nothing in range serves what was asked for (#162).

Peer 3 measured this on production: geo PJ, `radius_m=1500`, a candidate pool of
four venues. **8 of 8 dish queries returned zero venues serving the dish asked
for** -- `nasi lemak` returned pasta, tacos and a bakery, ranked, with
`coverage_gaps: []` and a corroboration stamp on each. Every citation was real;
the ranked ANSWER asserted a relevance no post supported.

The cause was that the dish vocabulary is built from the candidate pool, so a dish
outside the radius was indistinguishable from a dish nobody has written about.
"""

from makanlah.dishes import dish_named_inside, gap_terms

VOCAB = frozenset(
    {
        'nasi lemak',
        'nasi lemak ayam goreng rempah',
        '椰浆饭',
        'bkt',
        '肉骨茶',
        '中药肉骨茶',
        '肉',
        'elder garden mocktail',
        'rosated chicken',
        'satay',
        'pasta',
        'quesabirria',
    }
)


class TestNamingIsStricterThanSearching:
    """A gap tells somebody where to drive. Naming the wrong restaurant there is a
    new false claim, so the gap uses only the exact lanes."""

    def test_an_alias_must_match_as_a_whole_word(self):
        # `ckt` matched `elder garden mo(ckt)ail`, putting a tea house on a char
        # kway teow gap; `sate` matched `ro(sate)d chicken`.
        assert 'elder garden mocktail' not in gap_terms('char kway teow', VOCAB)
        assert 'rosated chicken' not in gap_terms('satay', VOCAB)

    def test_a_han_alias_still_matches_by_substring(self):
        # CJK has no word boundaries, and 肉骨茶 inside 中药肉骨茶 is the same dish.
        got = gap_terms('bak kut teh', VOCAB)
        assert '肉骨茶' in got and '中药肉骨茶' in got

    def test_a_single_character_is_a_fragment_not_a_dish(self):
        # 肉 is "meat" and canonicalises to bak kut teh by substring.
        assert '肉' not in gap_terms('bak kut teh', VOCAB)

    def test_the_alias_table_still_crosses_languages(self):
        assert '椰浆饭' in gap_terms('nasi lemak', VOCAB)

    def test_an_unrelated_dish_is_never_named(self):
        assert 'pasta' not in gap_terms('nasi lemak', VOCAB)
        assert 'quesabirria' not in gap_terms('nasi lemak', VOCAB)


class TestDetectingIsWiderThanNaming:
    """Whether the corpus knows the dish is a recall question."""

    def test_a_dish_named_inside_a_longer_query_is_found(self):
        # `nasi lemak sedap` -- tasty nasi lemak -- resolved to nothing and was
        # served a bakery.
        assert dish_named_inside('nasi lemak sedap', VOCAB) == 'nasi lemak'

    def test_word_order_still_matters(self):
        assert dish_named_inside('lemak nasi', VOCAB) is None

    def test_a_mood_query_names_no_dish(self):
        # The invariant that keeps a vague query on the semantic lane. If this
        # breaks, every mood query starts returning an empty result and a gap.
        for q in ('somewhere nice for dinner', 'something not too heavy', 'cheap eats tonight'):
            assert dish_named_inside(q, VOCAB) is None

    def test_a_single_ingredient_word_does_not_trigger_a_gap(self):
        # `rice` inside `rice bowl for lunch` is an ingredient, not the dish asked
        # for, and ranking already handles it.
        assert dish_named_inside('rice bowl for lunch', frozenset({'rice'})) is None


class TestTheGapDoesNotApplyAWeakerStandardThanTheRanking:
    """Peer 3: Kapitan cannot be ranked -- every post naming it is dead -- but was
    named as `nearest serving` in exactly the shape of a venue backed by three
    readable posts. `roti canai` is the sharp case: its entire gap answer rests on
    evidence no user can read, and the payload said nothing about that.

    A restaurant does not stop serving roti canai because a post 404s, so it is
    still named. It is just never presented as though it were checkable.
    """

    @staticmethod
    def _entry(row):
        return {
            'live_citations': int(row['live_citations'] or 0),
            'verifiable': bool(row['live_citations']),
        }

    def test_a_venue_with_live_evidence_is_marked_verifiable(self):
        got = self._entry({'live_citations': 9})
        assert got == {'live_citations': 9, 'verifiable': True}

    def test_a_venue_whose_posts_are_all_dead_is_named_but_not_verifiable(self):
        got = self._entry({'live_citations': 0})
        assert got == {'live_citations': 0, 'verifiable': False}

    def test_a_null_count_is_not_verifiable_rather_than_crashing(self):
        assert self._entry({'live_citations': None}) == {'live_citations': 0, 'verifiable': False}

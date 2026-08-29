"""Two branches of one shop must not read as a duplicate (issue #31).

兴记肉骨茶 and 興记肉骨茶 are different businesses ~900m apart with different
place_ids, so `rank.dedupe` is right to keep both. The bug is that a reader
cannot see the difference: 兴 and 興 are the simplified and traditional forms of
one character, and the second venue's aliases contain the first one's exact name.

So the fix is not a merge. It is (a) noticing the collision, which needs a fold
that ignores the script variant, and (b) labelling each side with something true.

The second half is where this is easy to get wrong. When the corpus does not know
where a venue is, the honest label is no label -- a placeholder invented to fill
the slot is the hallucination-with-a-rating this product exists to avoid. These
tests pin that: a pair that cannot be told apart is reported as such, never
papered over.
"""

from makanlah.rank import disambiguate
from makanlah.text import fold_variants


def entry(name, area=None, vid=None, distance_m=None):
    return {
        'venue': {'id': vid or name, 'name': name, 'area': area, 'lat': 3.21, 'lng': 101.64},
        'distance_m': distance_m,
    }


class TestFoldVariants:
    """Detection. Must see through the script variant without merging anything."""

    def test_simplified_and_traditional_fold_together(self):
        assert fold_variants('兴记肉骨茶') == fold_variants('興记肉骨茶')

    def test_latin_gloss_does_not_break_the_fold(self):
        # The real pair: one row carries an English gloss, the other does not.
        assert fold_variants('兴记肉骨茶 Hing Kee Bakuteh') == fold_variants('興记肉骨茶')

    def test_different_shops_still_differ(self):
        # The fold must not become a merge. These are genuinely different names.
        assert fold_variants('兴记肉骨茶') != fold_variants('新记肉骨茶')
        assert fold_variants('Village Park') != fold_variants('Sri Nirwana')

    def test_fold_is_stable_and_total(self):
        for s in ('', None, '   ', '!!!'):
            assert fold_variants(s) == ''


class TestDisambiguate:
    """Labelling. Only ever from data the corpus actually holds."""

    def test_uncollided_results_are_untouched(self):
        out = disambiguate([entry('Village Park'), entry('Sri Nirwana')])
        assert all(e['venue'].get('disambiguator') is None for e in out)

    def test_collision_labelled_from_area_when_known(self):
        out = disambiguate([entry('兴记肉骨茶', area='Kepong'), entry('興记肉骨茶', area='Jalan Ipoh')])
        labels = [e['venue']['disambiguator'] for e in out]
        assert labels == ['Kepong', 'Jalan Ipoh']

    def test_collision_with_no_area_is_flagged_not_invented(self):
        # Both venues in issue #31 have area=None today. Nothing may be fabricated.
        out = disambiguate([entry('兴记肉骨茶'), entry('興记肉骨茶')])
        assert all(e['venue']['disambiguator'] is None for e in out)
        assert all(e['venue']['ambiguous_with_sibling'] is True for e in out)

    def test_distance_is_used_when_area_is_missing_but_location_is_known(self):
        out = disambiguate([entry('兴记肉骨茶', distance_m=400), entry('興记肉骨茶', distance_m=1300)])
        labels = [e['venue']['disambiguator'] for e in out]
        assert labels == ['400 m away', '1.3 km away']

    def test_identical_areas_do_not_disambiguate_anything(self):
        # Same name, same area: a label that reads identically on both rows is
        # worse than none, because it looks like the duplicate it is denying.
        out = disambiguate([entry('兴记肉骨茶', area='Kepong'), entry('興记肉骨茶', area='Kepong')])
        assert all(e['venue']['disambiguator'] is None for e in out)
        assert all(e['venue']['ambiguous_with_sibling'] is True for e in out)

    def test_three_way_collision(self):
        out = disambiguate(
            [
                entry('兴记肉骨茶', area='Kepong'),
                entry('興记肉骨茶', area='Jalan Ipoh'),
                entry('兴记肉骨茶', area='Cheras'),
            ]
        )
        assert [e['venue']['disambiguator'] for e in out] == ['Kepong', 'Jalan Ipoh', 'Cheras']

    def test_order_and_length_are_preserved(self):
        given = [entry('a'), entry('b'), entry('c')]
        out = disambiguate(given)
        assert [e['venue']['name'] for e in out] == ['a', 'b', 'c']

    def test_empty_input(self):
        assert disambiguate([]) == []

"""Collapse a venue written twice, without asserting it in the corpus (#59).

Measured against the live corpus. Six venue groups fold to one name; three of
them are one business recorded twice, and they share a shape: one row carries a
`place_id`, its twin carries none, and nothing contradicts the match.

    偆园茶餐室 Choon Guan Hainan Coffee 1956 (9 mentions) + 偆园茶餐室 (1)
    八大八小 The Eight (1) + 八大八小 (8)       -- both independently Bukit Jalil
    强记炖汤 Keong Kee (9) + 强记炖汤 (2)

The other three are not duplicates and must survive untouched: 兴记肉骨茶 has two
`place_id`s 914m apart, 华阳 has two 11,970m apart, and 碧华楼 has two 159m apart
with a mention each.

**This is not a corpus merge and must not become one.** A row without a
`place_id` might be an ungeocoded third branch, and `docs/TRD.md` keeps ambiguity
as separate rows because a wrong merge is unrecoverable. `dedupe` already exists
for this and already says so: collapsing for one response is reversible by
definition. So the rule is deliberately narrow -- fold-equal names AND no
competing place_id -- and it keeps the row with the better evidence.
"""

from makanlah.rank import dedupe


def v(name, place_id=None, mentions=1, area=None):
    """A shortlist candidate in the shape rank.dedupe actually receives."""
    return {
        'name': name,
        'place_id': place_id,
        'area': area,
        'citations': [{'post_url': f'https://example.test/{name}/{i}'} for i in range(mentions)],
        'dishes': [],
    }


class TestCollapsesATwinWithNoCompetingEvidence:
    def test_the_ungeocoded_twin_is_dropped(self):
        out = dedupe([v('偆园茶餐室 Choon Guan Hainan Coffee 1956', 'p-51cfa22f', 9), v('偆园茶餐室', None, 1)])
        assert len(out) == 1
        assert out[0]['place_id'] == 'p-51cfa22f', 'kept the row without the evidence'

    def test_the_richer_row_survives_regardless_of_order(self):
        rows = [v('八大八小 The Eight', None, 1, 'Bukit Jalil'), v('八大八小', 'p-0f6bc74f', 8, 'Bukit Jalil')]
        out = dedupe(rows)
        assert len(out) == 1
        assert out[0]['place_id'] == 'p-0f6bc74f'
        assert len(out[0]['citations']) >= 8

    def test_simplified_and_traditional_twins_collapse(self):
        out = dedupe([v('強记炖汤 Keong Kee', 'p-5f1f1e65', 9), v('强记炖汤', None, 2)])
        assert len(out) == 1


class TestLeavesRealBranchesAlone:
    """Two place_ids is evidence of two businesses. It outranks a name match."""

    def test_two_place_ids_are_two_venues(self):
        # 兴记肉骨茶, 914m apart.
        out = dedupe([v('興记肉骨茶', 'p-04d0223e', 6), v('兴记肉骨茶 Hing Kee Bakuteh', 'p-babee426', 2)])
        assert len(out) == 2, 'collapsed two businesses that have distinct place_id evidence'

    def test_a_chains_outlets_are_not_one_venue(self):
        # 华阳, 11,970m apart. The comment in text.py calling these one kopitiam
        # is wrong; Oriental Kopi is a chain.
        out = dedupe([v('华阳冰室', 'p-7019142c', 6), v('华阳 Oriental Kopi', 'p-70090359', 2)])
        assert len(out) == 2

    def test_three_rows_collapse_only_the_evidence_free_one(self):
        out = dedupe(
            [
                v('興记肉骨茶', 'p-04d0223e', 6),
                v('兴记肉骨茶', None, 2),
                v('兴记肉骨茶 Hing Kee Bakuteh', 'p-babee426', 2),
            ]
        )
        assert len(out) == 2, f'expected the two real branches, got {[r["name"] for r in out]}'
        assert {r['place_id'] for r in out} == {'p-04d0223e', 'p-babee426'}

    def test_different_shops_are_untouched(self):
        out = dedupe([v('Village Park', None, 5), v('Sri Nirwana', None, 5)])
        assert len(out) == 2

    def test_two_rows_with_no_place_id_at_all_still_collapse(self):
        # Neither has evidence, so nothing contradicts the name match.
        out = dedupe([v('强记炖汤', None, 9), v('强记炖汤', None, 2)])
        assert len(out) == 1
        assert len(out[0]['citations']) >= 9

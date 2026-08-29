"""When the corpus knows the dish and cannot show anybody writing about it.

Measured on prod: `roti canai` returned Mon Beef Roti, RAYs @ B.LAND, Potato
Corner, kaiia kanteen and Menya Aburi. The lane had resolved the dish correctly
and found exactly the two venues carrying it, Devi's Corner and Kapitan; both
were dropped by `with_live_citations` because each has a single RedNote citation
and both are dead.

Every step behaved as designed and the user was shown a potato shop. That is #98
in its sharpest form -- the app is most misleading exactly where it knows most --
and unlike `ayam goreng berempah` it needs no signal we do not have.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah.rank import evidence_gap


def venue(name, dishes, citations, place_id='p1', area='PJ'):
    return {'id': name, 'name': name, 'area': area, 'place_id': place_id, 'dishes': dishes, 'citations': citations}


def dead():
    return [{'post_url': 'https://rednote/x', 'platform': 'rednote', 'dead': True, 'excerpt': 'x'}]


def live():
    return [{'post_url': 'https://rednote/y', 'platform': 'rednote', 'dead': None, 'excerpt': 'y'}]


NAMED = frozenset({'roti canai'})


class TestItFiresWhenTheEvidenceIsGone:
    def _gap(self, candidates):
        devis = venue("Devi's Corner", ['roti canai'], dead())
        kapitan = venue('Kapitan', ['roti canai', 'nasi kandar'], dead(), place_id='p2')
        return evidence_gap(
            NAMED, 'roti canai', ["Devi's Corner", 'Kapitan'], {"Devi's Corner": devis, 'Kapitan': kapitan}, candidates
        )

    def test_it_names_both_venues(self):
        gap = self._gap([venue('Potato Corner', ['fries'], live())])
        assert gap is not None
        assert [v['name'] for v in gap['venues']] == ["Devi's Corner", 'Kapitan']
        assert gap['term'] == 'roti canai'
        assert gap['total'] == 2

    def test_each_named_venue_is_independently_checkable(self):
        """The reason for naming rather than counting. That a post said something
        is unverifiable once the post is gone; that the RESTAURANT exists is
        verifiable in ten seconds, and the place_id link is what makes it so."""
        gap = self._gap([venue('Potato Corner', ['fries'], live())])
        for v in gap['venues']:
            assert 'query_place_id=' in v['maps_url']

    def test_it_stays_quiet_when_a_surviving_venue_carries_the_dish(self):
        # The ordinary case. One live roti canai venue and the gap does not exist.
        assert self._gap([venue('Mansion', ['roti canai'], live())]) is None


class TestItStaysQuietWhereItCannotProveAnything:
    def test_a_mood_query_names_nothing_and_never_reaches_here(self):
        assert evidence_gap(frozenset(), None, [], {}, []) is None

    def test_a_dish_the_corpus_never_had_is_not_this(self):
        """`ayam goreng berempah` and `char kuey teow` are absent from the corpus in
        every spelling, so nothing resolves and no venue is lexical. They must keep
        the 'closest in meaning' register -- claiming lost evidence for a dish the
        corpus never carried would be a new false statement, not a fix for one."""
        assert evidence_gap(frozenset({'ayam goreng berempah'}), 'ayam goreng berempah', [], {}, []) is None

    def test_a_venue_with_no_citation_at_all_is_never_named(self):
        """`enriched` inner-joins mentions, so an uncited venue does not appear in
        it. Nothing here may say 'the posts can no longer be opened' about a venue
        that never had one -- that is #42's uncited_venue and a different sentence."""
        assert evidence_gap(NAMED, 'roti canai', ['ghost'], {}, []) is None
        assert evidence_gap(NAMED, 'roti canai', ['ghost'], {'ghost': venue('ghost', ['roti canai'], [])}, []) is None

    def test_a_venue_whose_dishes_are_empty_does_not_suppress_the_gap(self):
        # A candidate carrying no dish tags at all cannot be the thing that proves
        # the dish survived, and `None` in that column must not raise.
        gap = evidence_gap(
            NAMED,
            'roti canai',
            ['d'],
            {'d': venue('d', ['roti canai'], dead())},
            [venue('x', None, live()), venue('y', [], live())],
        )
        assert gap is not None


class TestTheListIsBounded:
    def test_it_reports_the_total_even_when_it_lists_fewer(self):
        many = {f'v{i}': venue(f'v{i}', ['roti canai'], dead(), place_id=f'p{i}') for i in range(9)}
        gap = evidence_gap(NAMED, 'roti canai', list(many), many, [])
        assert len(gap['venues']) == 5
        # Silently listing five of nine reads as "there are five". #98's own rule:
        # a bounded list says what it dropped.
        assert gap['total'] == 9

"""Say what the corpus cannot answer, rather than answering anyway (#86).

UAT, three rounds, one persona: `tempat makan halal untuk keluarga` returns
Hock Kee Heritage, 鱼你 and Sisters Place. She asked for halal in Malay and got
a Chinese fish restaurant, with the word "halal" appearing nowhere on the page.

**The corpus carries no halal signal and must not invent one.** Inferring it from
a venue name or cuisine is exactly the confident wrong answer this product exists
to avoid, and getting it wrong is not a ranking miss -- it is a person eating
something they hold themselves not to.

What is available without new data is honesty. `/ask` already does this well:

    covered: False
    "The provided excerpts do not mention whether Wanjo椰浆饭 is halal."

A ranked list has no equivalent, so a query about something the corpus cannot
speak to returns an unmarked list that reads as an answer. This adds the missing
half: the results still come back, and they come back with the gap named.
"""

import pytest

from makanlah.rank import coverage_gaps


class TestDetectsWhatWeCannotAnswer:
    @pytest.mark.parametrize(
        'query',
        [
            'tempat makan halal untuk keluarga',
            'halal food near me',
            'is this place halal',
            'makanan HALAL sedap',
            '清真餐厅',
        ],
    )
    def test_a_halal_query_is_flagged(self, query):
        assert 'halal' in coverage_gaps(query)

    @pytest.mark.parametrize('query', ['nasi lemak', '肉骨茶', 'char kuey teow', 'something light lah'])
    def test_an_ordinary_query_is_not_flagged(self, query):
        assert coverage_gaps(query) == []

    def test_a_venue_named_halal_is_not_a_halal_query(self):
        # "Restoran Halal Corner" is a name, not a dietary constraint. Flagging it
        # would put a disclaimer on a search that did not ask for one.
        assert coverage_gaps('restoran halal corner bangsar') == []

    def test_empty_and_none(self):
        assert coverage_gaps('') == []
        assert coverage_gaps(None) == []


class TestTheMosqueTrap:
    """清真寺 is a mosque and 清真 is a prefix of it.

    Found in the corpus by the UAT session: one excerpt contains both 清真友好
    ("halal-friendly", a real claim by a real person) and 清真寺 used as a
    landmark. A substring match reads "near a mosque" as "is halal" and
    mislabels a venue on the strength of its neighbours.

    Being wrong about halal is not a ranking miss. It is the one error a
    Malaysian user will not forgive, and rightly.
    """

    def test_a_mosque_is_not_a_halal_query(self):
        assert coverage_gaps('清真寺') == []

    def test_a_mosque_as_a_landmark_is_not_a_halal_query(self):
        assert coverage_gaps('附近有清真寺的餐厅') == []

    def test_the_real_halal_term_still_matches(self):
        assert coverage_gaps('清真友好') == ['halal']
        assert coverage_gaps('清真餐厅') == ['halal']


class TestTheNoteIsHonestNotDecorative:
    def test_it_names_the_gap_rather_than_apologising(self):
        note = coverage_gaps('halal food')
        assert note == ['halal'], 'the caller decides the wording; this reports the gap'

    def test_pork_is_not_treated_as_a_halal_signal(self):
        # Absence of a pork mention says nothing about certification, and
        # inferring from cuisine is the failure mode this exists to prevent.
        assert coverage_gaps('bak kut teh') == []

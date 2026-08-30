"""The candidate cap was tuned for a corpus a third of this size.

`filter_candidates` returns the N nearest venues in range and everything
downstream sees only those. At 247 venues, N=400 was larger than the corpus and
the cap never bound. At 823 it truncates, and it truncates by DISTANCE, which
silently removes whole dishes from the vocabulary the lexical lane is built from.

Measured, 20km from KL centre: 400 candidates give a 624-term vocabulary and
`steamboat` does not match; the uncapped 740 give 806 terms and it does. So
`steamboat` returned 2 results this afternoon and 0 tonight -- not because the
corpus lost steamboat, but because 400 newer venues sat between the user and it.

This is also why citable grew 229% while reachable grew 25%: two thirds of the
new evidence was behind a ceiling nobody moved.
"""

from makanlah.db import CANDIDATE_CEILING


def test_the_ceiling_clears_the_current_corpus_with_room():
    """It has to exceed the venue count, or the nearest N crowd out the rest.
    823 venues today; this leaves room to roughly double before it binds again."""
    assert CANDIDATE_CEILING >= 1500


def test_the_default_is_the_ceiling_not_a_smaller_literal():
    """The 400 was passed as a default argument, so raising it in one call site
    would have left the others truncating."""
    import inspect

    from makanlah.db import filter_candidates

    assert inspect.signature(filter_candidates).parameters['limit'].default == CANDIDATE_CEILING

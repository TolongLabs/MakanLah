"""A result must cite evidence the reader can actually open (#83).

Measured against prod in UAT round 1: of 14 unique RedNote posts behind the
肉骨茶 shortlist, 11 resolved and 3 were gone. **Six of eight cards displayed a
dead link, and three of those had a live post on the same venue** -- the client
takes the first citation and the ordering was blind to whether it resolves. One
dead post backed six of the eight cards on its own.

`/ask` is affected too, and worse: its answer is a paraphrase, so the post is the
only way to confirm the copilot did not invent it.

Two rules, and the second one is the easy one to get wrong:

1. **Prefer a citation that resolves.** Reordering fixes most of this without
   touching the corpus.
2. **Unknown is not dead.** A post nobody has probed yet must rank as live.
   Treating unchecked as dead would silently hide most of the corpus the first
   time the prober falls behind, and it would look like a ranking improvement.

A venue whose every citation is known-dead is not a result. It is a ranked entry
nobody can check, which is the thing this product exists not to produce.
"""

import pytest

from makanlah.rank import prefer_live, with_live_citations


def cite(url, dead=None):
    return {'post_url': url, 'excerpt': 'testimony', 'platform': 'rednote', 'dead': dead}


class TestPreferLive:
    def test_a_live_citation_outranks_a_dead_one(self):
        out = prefer_live([cite('dead', True), cite('live', False)])
        assert [c['post_url'] for c in out] == ['live', 'dead']

    def test_unknown_liveness_ranks_as_live(self):
        # The prober has not reached this post. Hiding it would suppress most of
        # the corpus the moment the job falls behind.
        out = prefer_live([cite('dead', True), cite('unchecked', None)])
        assert out[0]['post_url'] == 'unchecked'

    def test_a_dead_citation_is_kept_not_discarded(self):
        # It is still real evidence and it is all some venues have.
        out = prefer_live([cite('dead', True)])
        assert len(out) == 1

    def test_order_is_stable_among_equals(self):
        out = prefer_live([cite('a', False), cite('b', False), cite('c', False)])
        assert [c['post_url'] for c in out] == ['a', 'b', 'c']

    def test_empty(self):
        assert prefer_live([]) == []


class TestVenuesWithNoLiveEvidence:
    """宝香绑线肉骨茶 was the true failure in the set: one citation, and it was dead."""

    def entry(self, name, cites):
        return {'venue': {'id': name, 'name': name}, 'citations': cites}

    def test_a_venue_whose_every_citation_is_dead_is_dropped(self):
        out = with_live_citations(
            [
                self.entry('checkable', [cite('live', False)]),
                self.entry('uncheckable', [cite('d1', True), cite('d2', True)]),
            ]
        )
        assert [e['venue']['name'] for e in out] == ['checkable']

    def test_one_live_citation_is_enough_to_keep_a_venue(self):
        out = with_live_citations([self.entry('mixed', [cite('d', True), cite('l', False)])])
        assert len(out) == 1
        assert out[0]['citations'][0]['post_url'] == 'l', 'the live citation must lead'

    def test_a_venue_with_only_unchecked_citations_survives(self):
        out = with_live_citations([self.entry('unchecked', [cite('u', None)])])
        assert len(out) == 1, 'unchecked is not dead; dropping it would hide the corpus'

    def test_a_venue_with_no_citations_was_never_a_result(self):
        assert with_live_citations([self.entry('bare', [])]) == []


@pytest.mark.parametrize('flag', [True, False, None])
def test_liveness_never_invents_an_excerpt(flag):
    out = prefer_live([cite('x', flag)])
    assert out[0]['excerpt'] == 'testimony'

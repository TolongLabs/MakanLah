"""Make "two independent sources" mean something (#87).

UAT round 1: 14 unique posts back 27 venue-mentions, and two posts back four
venues each. On `something not too heavy`, ranks 1, 2 and 3 were three venues
from one listicle by one author -- each card reading "Corroborated by two
independent sources."

Per card that was arguably true: a Google Maps reviewer and a RedNote author are
two people. Across the page it was not. Corroboration is the strongest claim this
product makes, so it has to survive being read as a list rather than only per
card.

Two signals, both computed from what citations already carry:

- `corroboration` counts DISTINCT posts, authors and platforms. Two mentions by
  one author on one post is one voice however many platforms carried it.
- `shared_with` names the other venues in the SAME response backed by that same
  post, which is what makes one listicle driving three picks visible instead of
  something a reader has to notice.
"""

from makanlah.rank import add_corroboration


def cite(url, author, platform='rednote', post_id=None):
    # Identity defaults to address. That is true for RedNote, where one post has one
    # URL, and it keeps every case written before #153 meaning what it meant.
    return {
        'post_id': post_id or url,
        'post_url': url,
        'author_handle': author,
        'platform': platform,
        'excerpt': 'x',
    }


def entry(vid, cites):
    return {'venue': {'id': vid, 'name': vid}, 'citations': cites}


class TestCounts:
    def test_two_authors_on_two_posts_is_corroborated(self):
        out = add_corroboration([entry('a', [cite('p1', 'ann'), cite('p2', 'ben', 'google_maps')])])
        assert out[0]['venue']['corroboration'] == {'posts': 2, 'authors': 2, 'platforms': 2}

    def test_one_author_twice_is_one_voice(self):
        # The same person posting twice is not corroboration, however many
        # platforms carried it.
        out = add_corroboration([entry('a', [cite('p1', 'ann'), cite('p2', 'ann', 'google_maps')])])
        assert out[0]['venue']['corroboration']['authors'] == 1

    def test_one_post_quoted_twice_is_one_post(self):
        out = add_corroboration([entry('a', [cite('p1', 'ann'), cite('p1', 'ann')])])
        assert out[0]['venue']['corroboration']['posts'] == 1

    def test_a_missing_author_handle_does_not_become_a_second_voice(self):
        # Absent authorship is unknown, not distinct. Counting None as a person
        # would manufacture corroboration out of missing data.
        out = add_corroboration([entry('a', [cite('p1', None), cite('p2', None, 'google_maps')])])
        assert out[0]['venue']['corroboration']['authors'] <= 1

    def test_no_citations_claims_nothing(self):
        out = add_corroboration([entry('a', [])])
        assert out[0]['venue']['corroboration'] == {'posts': 0, 'authors': 0, 'platforms': 0}


class TestSharedWith:
    def test_one_listicle_driving_three_picks_is_visible(self):
        out = add_corroboration(
            [
                entry('v1', [cite('listicle', 'ann')]),
                entry('v2', [cite('listicle', 'ann')]),
                entry('v3', [cite('listicle', 'ann')]),
            ]
        )
        assert out[0]['citations'][0]['shared_with'] == ['v2', 'v3']
        assert out[2]['citations'][0]['shared_with'] == ['v1', 'v2']

    def test_a_post_backing_one_venue_shares_nothing(self):
        out = add_corroboration([entry('v1', [cite('solo', 'ann')]), entry('v2', [cite('other', 'ben')])])
        assert out[0]['citations'][0]['shared_with'] == []

    def test_a_venue_never_shares_with_itself(self):
        out = add_corroboration([entry('v1', [cite('p', 'ann'), cite('p', 'ann')])])
        assert all(c['shared_with'] == [] for c in out[0]['citations'])

    def test_entries_and_order_are_preserved(self):
        given = [entry('a', [cite('p', 'x')]), entry('b', [cite('q', 'y')])]
        assert [e['venue']['id'] for e in add_corroboration(given)] == ['a', 'b']

    def test_empty(self):
        assert add_corroboration([]) == []


class TestADeadPostIsNotASecondSource:
    """#111. `add_corroboration` counted every citation, dead ones included.

    Measured on prod across 8 queries and 59 results: **11 carried "Corroborated
    by two independent sources" while the card could render exactly one
    testimony**, because `leadPair` correctly refuses a dead citation that the
    count had just relied on. 阿喜 read 3 posts / 2 authors / 2 platforms and had
    one openable post behind it.

    This is the claim itself and not a detail. Corroboration means a reader can go
    and check two people; an unopenable post is precisely what they cannot check,
    so counting it manufactures the confidence the signal exists to earn.
    """

    def _one(self, citations):
        e = {'venue': {'id': 'v1'}, 'citations': citations}
        return add_corroboration([e])[0]['venue']['corroboration']

    def test_the_prod_shape_that_overclaimed(self):
        # 阿喜: one live Google Maps review, two dead RedNote posts.
        c = self._one(
            [
                {'post_id': 'm1', 'post_url': 'm1', 'platform': 'google_maps', 'author_handle': None, 'dead': None},
                {'post_id': 'r1', 'post_url': 'r1', 'platform': 'rednote', 'author_handle': 'a', 'dead': True},
                {'post_id': 'r2', 'post_url': 'r2', 'platform': 'rednote', 'author_handle': 'b', 'dead': True},
            ]
        )
        assert c == {'posts': 1, 'authors': 0, 'platforms': 1}
        assert not (c['posts'] >= 2 and (c['authors'] >= 2 or c['platforms'] >= 2))

    def test_an_unchecked_post_still_counts(self):
        # `dead` is tri-state. Only `true` is measured dead; `null` is unchecked,
        # and a cooled-down re-probe resolved exactly such a row live on the venue
        # with the strongest evidence in the corpus.
        c = self._one(
            [
                {'post_id': 'm1', 'post_url': 'm1', 'platform': 'google_maps', 'author_handle': None, 'dead': None},
                {'post_id': 'r1', 'post_url': 'r1', 'platform': 'rednote', 'author_handle': 'a'},
            ]
        )
        assert c == {'posts': 2, 'authors': 1, 'platforms': 2}

    def test_shared_with_still_walks_every_citation(self):
        """One listicle driving three ranks is worth saying whether or not it still
        resolves, so the dead filter must not reach `shared_with` (#87)."""
        entries = [
            {
                'venue': {'id': 'a'},
                'citations': [{'post_id': 'p', 'post_url': 'p', 'platform': 'rednote', 'dead': True}],
            },
            {
                'venue': {'id': 'b'},
                'citations': [{'post_id': 'p', 'post_url': 'p', 'platform': 'rednote', 'dead': True}],
            },
        ]
        out = add_corroboration(entries)
        assert out[0]['citations'][0]['shared_with'] == ['b']
        assert out[1]['citations'][0]['shared_with'] == ['a']


class TestThreeReviewersCanShareOneUrl:
    """Google Maps has no per-review URL, so review_url() returns the venue page.

    Counting addresses made Upper House read `1 post` over three testimonies by three
    different people, and `independentlyBacked` needs `posts >= 2` -- so the stamp was
    withheld from a venue that had earned it. That is #87 in the mirror: there the
    stamp claimed corroboration that did not exist, here it denied corroboration that
    did. Both are the stamp saying something untrue.
    """

    def test_three_reviews_on_one_venue_page_are_three_posts(self):
        url = 'https://www.google.com/maps/search/?api=1&query=Upper%20House'
        cites = [cite(url, None, 'google_maps', post_id=f'rev{i}') for i in (1, 2, 3)]
        got = add_corroboration([entry('v1', cites)])
        assert got[0]['venue']['corroboration']['posts'] == 3

    def test_the_same_review_seen_twice_is_still_one_post(self):
        # Identity has to dedupe as well as separate, or the count inflates instead.
        url = 'https://maps.example/x'
        cites = [cite(url, None, 'google_maps', post_id='rev1') for _ in range(3)]
        assert add_corroboration([entry('v1', cites)])[0]['venue']['corroboration']['posts'] == 1

    def test_a_rednote_post_quoted_twice_is_still_one_post(self):
        # The pre-#153 behaviour that must not regress: one URL, one identity.
        cites = [cite('https://rednote/p1', 'a'), cite('https://rednote/p1', 'a')]
        assert add_corroboration([entry('v1', cites)])[0]['venue']['corroboration']['posts'] == 1

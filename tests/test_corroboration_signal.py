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


def cite(url, author, platform='rednote'):
    return {'post_url': url, 'author_handle': author, 'platform': platform, 'excerpt': 'x'}


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

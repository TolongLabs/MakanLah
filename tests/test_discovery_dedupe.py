"""#157: a discovered place must not become a second row for a venue we hold.

The dedupe order is the whole risk. #59 says the evidence-based merge on place_id
is the right rule and must not be loosened -- a wrong merge is not recoverable.
"""

from ingest.discover_gmaps import plan_queries, resolve_against_corpus


def test_place_id_wins_over_a_different_name():
    """Maps' own name for a place often differs from the one RedNote used.
    place_id is the strongest evidence we have that they are the same shop."""
    existing = {'by_place_id': {'0xabc:0x1': 'V1'}, 'by_norm': {}}
    got = resolve_against_corpus({'name': 'Village Park Restaurant', 'place_id': '0xabc:0x1'}, existing)
    assert got == ('V1', 'known')


def test_a_name_match_adopts_the_place_id_rather_than_creating_a_row():
    """The venue is already ours from RedNote and has no place_id yet. Discovery
    is where it gets one, which is what makes a later merge decidable."""
    existing = {'by_place_id': {}, 'by_norm': {'village park': 'V2'}}
    got = resolve_against_corpus({'name': 'Village Park', 'place_id': '0xdef:0x2'}, existing)
    assert got == ('V2', 'adopt_place_id')


def test_an_unknown_place_is_new():
    got = resolve_against_corpus(
        {'name': 'Some New Kopitiam', 'place_id': '0x111:0x2'}, {'by_place_id': {}, 'by_norm': {}}
    )
    assert got == (None, 'new')


def test_place_id_is_checked_before_the_name():
    """Both could match different venues. place_id is the stronger evidence and
    must decide, or discovery silently re-points a venue at the wrong shop."""
    existing = {'by_place_id': {'0xabc:0x1': 'BY_ID'}, 'by_norm': {'village park': 'BY_NAME'}}
    got = resolve_against_corpus({'name': 'Village Park', 'place_id': '0xabc:0x1'}, existing)
    assert got == ('BY_ID', 'known')


def test_a_place_with_no_place_id_never_matches_by_place_id():
    existing = {'by_place_id': {'': 'WRONG', None: 'ALSO_WRONG'}, 'by_norm': {}}
    assert resolve_against_corpus({'name': 'X', 'place_id': None}, existing) == (None, 'new')
    assert resolve_against_corpus({'name': 'X', 'place_id': ''}, existing) == (None, 'new')


def test_the_query_grid_crosses_areas_with_dishes():
    q = plan_queries(areas=['Bangsar', 'Cheras'], dishes=['nasi lemak', 'kopitiam'])
    assert len(q) == 4
    assert 'nasi lemak Bangsar Kuala Lumpur' in q
    assert 'kopitiam Cheras Kuala Lumpur' in q


def test_the_grid_is_deterministic_so_an_offset_run_resumes_where_it_stopped():
    """Every un-offset run re-capturing the same top N is #128. A grid that
    reorders between runs makes an offset meaningless."""
    a, d = ['Bangsar', 'Cheras', 'Kepong'], ['nasi lemak', 'kopitiam']
    assert plan_queries(areas=a, dishes=d) == plan_queries(areas=a, dishes=d)


def test_a_multi_word_area_is_recovered_whole():
    """Splitting the query on spaces gives 'Road' for 'Old Klang Road', which
    then lands on every venue there as its neighbourhood."""
    from ingest.discover_gmaps import area_of

    assert area_of('nasi lemak Old Klang Road Kuala Lumpur', ['Bangsar', 'Old Klang Road']) == 'Old Klang Road'
    assert area_of('nasi lemak Bangsar Kuala Lumpur', ['Bangsar', 'Old Klang Road']) == 'Bangsar'


def test_the_longest_matching_area_wins():
    """'Damansara' is a substring of nothing here, but 'SS2' vs 'SS15' and
    'Petaling Jaya' vs 'Jaya' are the shape that bites."""
    from ingest.discover_gmaps import area_of

    assert area_of('cafe SS15 Kuala Lumpur', ['SS2', 'SS15']) == 'SS15'


def test_an_area_that_is_not_in_the_list_is_none_not_a_guess():
    from ingest.discover_gmaps import area_of

    assert area_of('nasi lemak Somewhere Kuala Lumpur', ['Bangsar']) is None

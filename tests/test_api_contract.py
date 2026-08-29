"""The API contract, against fixtures.

No database, no network. docs/TRD.md is explicit that a suite hitting a live
platform fails when a session expires, and a red check that means nothing trains
everyone to ignore red checks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
import pytest

fastapi_testclient = pytest.importorskip('fastapi.testclient')
TestClient = fastapi_testclient.TestClient

from api import main as api_main  # noqa: E402
from makanlah import rank  # noqa: E402


def _ranked_result(basis='semantic', dish=None):
    r = _result()
    r.pop('score', None)
    r['rank'] = 1
    r['match'] = {'basis': basis, 'dish': dish, 'similarity': 0.61}
    return r


@pytest.fixture
def client():
    return TestClient(api_main.app)


def _result(name='Village Park', citations=None):
    return {
        'venue': {
            'id': 'v1',
            'name': name,
            'area': 'Damansara Uptown',
            'lat': 3.13,
            'lng': 101.62,
            'maps_url': 'https://www.google.com/maps/search/?api=1&query=x',
            'dishes': ['nasi lemak'],
        },
        'score': 0.7,
        'why': 'Known for its fried chicken.',
        'distance_m': 1200,
        'citations': [
            {
                'post_url': 'https://www.rednote.com/explore/a',
                'excerpt': '椰浆饭天花板',
                'platform': 'rednote',
                'author_handle': None,
                'posted_at': 'Feb 17',
            }
        ]
        if citations is None
        else citations,
    }


class TestCitationsAreLoadBearing:
    """PRD acceptance criterion A1: no response contains a result with zero
    citations. An entry that cannot be cited is dropped before the response is
    built, never returned with a caveat."""

    def test_a_result_without_citations_never_reaches_the_client(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {
                'results': [_result(citations=[]), _result('Sek Yuen')],
                'degraded': False,
                'sources_used': ['rednote'],
            },
        )
        body = client.post('/recommend', json={'query': 'nasi lemak'}).json()
        assert len(body['results']) == 1
        assert body['results'][0]['venue']['name'] == 'Sek Yuen'

    def test_every_returned_result_carries_at_least_one_citation(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {
                'results': [_result(), _result('Yut Kee')],
                'degraded': False,
                'sources_used': ['rednote'],
            },
        )
        body = client.post('/recommend', json={'query': 'x'}).json()
        assert body['results']
        assert all(r['citations'] for r in body['results'])

    def test_a_citation_carries_the_post_url_a_human_can_verify(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {
                'results': [_result()],
                'degraded': False,
                'sources_used': ['rednote'],
            },
        )
        c = client.post('/recommend', json={'query': 'x'}).json()['results'][0]['citations'][0]
        assert c['post_url'].startswith('http')
        assert c['platform']


class TestFailureIsHonest:
    """An empty, honest answer beats a 500, and an error must never be dressed
    as zero results."""

    def test_a_corpus_failure_returns_degraded_rather_than_a_500(self, client, monkeypatch):
        import psycopg

        def boom(*a, **k):
            raise psycopg.OperationalError('neon unreachable')

        monkeypatch.setattr(api_main.rank, 'recommend', boom)
        res = client.post('/recommend', json={'query': 'x'})
        assert res.status_code == 200
        body = res.json()
        assert body['results'] == []
        assert body['degraded'] is True
        assert body['error'] == 'OperationalError'

    def test_a_bug_in_our_own_code_is_not_dressed_up_as_an_outage(self, client, monkeypatch):
        """Catching every exception here hid issue #13 for the life of the project:
        a 5-placeholder/6-parameter query raised ProgrammingError on every request
        carrying a radius, and the client was told the corpus was unavailable.

        The fault used to escape the app entirely and this asserted that it did.
        Since #81 it is caught one layer inside CORSMiddleware so the 500 keeps its
        header, which means the assertion has to move from "it propagates" to "it
        arrives as a 500 that names itself and claims nothing" -- the discrimination
        #13 needs, still measured from the client where it is actually read.
        """
        import psycopg

        for exc in (psycopg.ProgrammingError('5 placeholders but 6 parameters'), TypeError('nope'), KeyError('lat')):

            def boom(*a, _e=exc, **k):
                raise _e

            monkeypatch.setattr(api_main.rank, 'recommend', boom)
            res = client.post('/recommend', json={'query': 'x'})
            assert res.status_code == 500, type(exc).__name__
            body = res.json()
            assert body['error'] == type(exc).__name__
            assert body.get('degraded') is not True
            assert body.get('results') is None

    def test_degraded_is_passed_through_not_overwritten(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {
                'results': [_result()],
                'degraded': True,
                'degraded_reasons': ['rednote failed at its last run'],
                'sources_used': ['google_maps'],
            },
        )
        body = client.post('/recommend', json={'query': 'x'}).json()
        assert body['degraded'] is True
        assert body['degraded_reasons'] == ['rednote failed at its last run']


class TestRequestValidation:
    """Scraped input is the least trustworthy data in the project, and so is a
    request body. Both are parsed at the boundary, never spread in."""

    @pytest.mark.parametrize(
        'body',
        [
            {},
            {'query': ''},
            {'query': 'x', 'limit': 0},
            {'query': 'x', 'limit': 99},
            {'query': 'x', 'radius_m': 10},
            {'query': 'x', 'radius_m': 999999},
            {'query': 'x', 'budget': 9},
        ],
    )
    def test_invalid_requests_are_rejected(self, client, body):
        assert client.post('/recommend', json=body).status_code == 422

    def test_a_mixed_script_query_is_accepted(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {
                'results': [],
                'degraded': False,
                'sources_used': [],
            },
        )
        res = client.post('/recommend', json={'query': 'Village Park 的 nasi lemak 好吃吗'})
        assert res.status_code == 200


class TestHealth:
    def test_health_never_returns_a_secret_value(self, client):
        body = client.get('/health').json()
        assert set(body['configured']) == {'database', 'extract', 'embed', 'rerank'}
        assert all(isinstance(v, bool) for v in body['configured'].values())


class TestTheShapeOfARankedEntry:
    """No test asserted this, which is why `score` could report retrieval cosine
    while the ORDER came from the re-rank -- a higher number sitting below a
    lower one, visible in every response, caught by nothing."""

    def _one(self, client, monkeypatch, result):
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {'results': [result], 'degraded': False, 'sources_used': ['rednote']},
        )
        return client.post('/recommend', json={'query': 'x'}).json()['results'][0]

    def test_an_entry_reports_its_rank_not_a_similarity_number(self, client, monkeypatch):
        r = self._one(client, monkeypatch, _ranked_result())
        assert r['rank'] == 1
        assert 'score' not in r, 'score reported retrieval cosine while ordering came from the re-rank'

    def test_an_entry_says_why_it_is_present(self, client, monkeypatch):
        r = self._one(client, monkeypatch, _ranked_result())
        assert r['match']['basis'] in ('dish', 'text', 'semantic')

    def test_a_dish_match_is_labelled_as_one(self, client, monkeypatch):
        r = self._one(client, monkeypatch, _ranked_result(basis='dish', dish='bak kut teh'))
        assert r['match']['basis'] == 'dish'
        assert r['match']['dish'] == 'bak kut teh'


class TestTheDocumentedContractMatchesTheResponse:
    """The API contract block in TRD.md is what a client types against.

    It said `match: {basis, dish_hit, lexical, vector}` while /recommend sent
    `basis, dish, similarity`, and the web client's type was written faithfully
    against the doc -- so the client was wrong about the response for as long as
    nothing read those fields. `tsc` found it only when a real response finally
    met the type. Prose cannot be trusted to stay in step with code by intention,
    so this compares them.
    """

    @staticmethod
    def _documented_match_keys():
        trd = (Path(__file__).resolve().parents[1] / 'docs' / 'TRD.md').read_text()
        line = next(ln for ln in trd.splitlines() if 'match: {' in ln)
        inside = line.split('match: {', 1)[1].split('}', 1)[0]
        return {k.strip() for k in inside.split(',') if k.strip()}

    def test_the_documented_match_keys_are_the_ones_sent(self, client, monkeypatch):
        keys = self._documented_match_keys()
        assert keys, 'no match block found in TRD.md -- the doc moved, so fix this test'
        monkeypatch.setattr(rank, 'recommend', lambda *a, **k: {'results': [_ranked_result()], 'sources_used': ['x']})
        body = client.post('/recommend', json={'query': 'laksa'}).json()
        assert set(body['results'][0]['match']) == keys

    def test_the_doc_is_not_silently_empty(self):
        # An empty set would make the comparison above pass against anything,
        # which is the failure this whole class exists to catch.
        assert self._documented_match_keys() == {'basis', 'dish', 'similarity'}


class TestHealthCountsWhatCanBeShown:
    """`venues` is printed on the landing page under "Places somebody wrote
    about". After the #42 replay nine venues have no surviving mention: they sit
    in `uncited_venue`, are unrankable, and no other surface can reach them.

    Counting them overstated the evidence on the one page whose whole argument is
    that the evidence is not overstated -- which is a smaller version of the bug
    the replay existed to fix.
    """

    def test_the_count_excludes_venues_with_nothing_to_cite(self):
        sql = _health_venue_sql()
        assert 'join mention' in sql, 'a bare count over venue counts rows nobody can see'
        assert 'excerpt is not null' in sql, 'a mention with no excerpt is not something somebody wrote'

    def test_it_is_not_a_bare_table_count(self):
        # The exact statement this replaced. Asserting its absence is what makes
        # the test above more than a restatement of whatever is currently there.
        assert 'select count(*) c from venue' not in _health_venue_sql().replace('\n', ' ')


def _health_venue_sql():
    src = (Path(__file__).resolve().parents[1] / 'api' / 'main.py').read_text()
    body = src.split("out['venues'] =", 1)[1]
    return body.split('.fetchone()', 1)[0]


class TestCompanionIsDecorationNotEvidence:
    """The one lane allowed to be generated, held to the one rule that matters.

    It exists because the wizard is nicer with a voice. It is safe because it
    never sees a corpus row and never returns a citation, so nothing it says can
    be mistaken for a result.
    """

    def test_returns_a_line_and_says_where_it_came_from(self, client, monkeypatch):
        monkeypatch.setattr(api_main.companion, 'line', lambda step, picked: {'text': 'Hi!', 'source': 'model'})
        r = client.post('/companion', json={'step': 'craving', 'picked': []})
        assert r.status_code == 200
        assert r.json() == {'text': 'Hi!', 'source': 'model'}

    def test_never_carries_a_citation_or_a_venue(self, client, monkeypatch):
        # A companion response that grew a citations key would put an uncited
        # claim on the one surface nothing checks. It has no such key, by shape.
        # The lane is stubbed so this asserts the endpoint's shape rather than a
        # workstation's .env: with a real key present it would call Gemini.
        monkeypatch.setattr(api_main.companion, 'line', lambda step, picked: {'text': 'Hi!', 'source': 'model'})
        r = client.post('/companion', json={'step': 'craving', 'picked': []})
        body = r.json()
        assert set(body) <= {'text', 'source', 'reason'}
        assert 'citations' not in body and 'venue' not in body

    def test_speaks_anyway_when_the_free_quota_is_gone(self, client, monkeypatch):
        # 200 with a scripted line, not 429. A wizard whose companion goes silent
        # mid-flow reads as broken; a slightly repetitive one does not.
        monkeypatch.setattr(api_main, '_companion_quota', lambda: False)
        r = client.post('/companion', json={'step': 'mood', 'picked': []})
        assert r.status_code == 200
        assert r.json()['source'] == 'script'
        assert r.json()['reason'] == 'quota'
        assert r.json()['text']

    def test_the_daily_cap_is_under_the_free_tier(self):
        # GEMINI_MODEL_L2D's free tier is 500 requests a day and 15 a minute.
        # Crossing a free tier starts charging rather than failing, and spending
        # real money is a thing this project stops for.
        assert api_main.COMPANION_DAILY < 500
        assert api_main.COMPANION_PER_MIN < 15

    def test_the_quota_counter_actually_stops(self, monkeypatch):
        monkeypatch.setattr(api_main, 'COMPANION_DAILY', 3)
        monkeypatch.setattr(api_main, 'COMPANION_PER_MIN', 99)
        monkeypatch.setattr(api_main, '_companion', {'day': -1.0, 'used': 0.0})
        monkeypatch.setattr(api_main, '_companion_minute', [])
        assert [api_main._companion_quota() for _ in range(5)] == [True, True, True, False, False]

    def test_a_long_pick_list_is_refused_at_the_boundary(self, client):
        r = client.post('/companion', json={'step': 'craving', 'picked': [f'x{i}' for i in range(50)]})
        assert r.status_code == 422


class TestSuggestionsAreMeteredAndCannotInvent:
    """The chips endpoint. Same free-tier counter as the companion, same rule that
    a model may reorder but never write a label."""

    def test_returns_chips_the_corpus_can_back(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.suggest,
            'chips',
            lambda **_: {
                'chips': [{'label': '肉骨茶', 'query': '肉骨茶', 'posts': 14, 'venues': 9}],
                'band': 'dinner',
                'source': 'model',
            },
        )
        r = client.get('/suggestions')
        assert r.status_code == 200
        assert r.json()['chips'][0]['posts'] == 14

    def test_shares_the_companion_free_tier_counter(self, monkeypatch):
        # /suggestions and /companion are the same Gemini lane. Two independent
        # counters would let the pair spend twice the free tier between them.
        monkeypatch.setattr(api_main, 'COMPANION_DAILY', 2)
        monkeypatch.setattr(api_main, 'COMPANION_PER_MIN', 99)
        monkeypatch.setattr(api_main, '_companion', {'day': -1.0, 'used': 0.0})
        monkeypatch.setattr(api_main, '_companion_minute', [])
        assert [api_main._companion_quota() for _ in range(3)] == [True, True, False]

    def test_degrades_to_the_corpus_rather_than_failing_when_the_quota_is_spent(self, client, monkeypatch):
        # Peer review asked for this explicitly: a dead suggestion strip is fine, a
        # stack trace on the results path is not.
        monkeypatch.setattr(api_main, '_companion_quota', lambda: False)
        seen = {}

        def chips(*, use_model=True):
            seen['use_model'] = use_model
            return {
                'chips': [{'label': 'nasi lemak', 'query': 'nasi lemak', 'posts': 9, 'venues': 5}],
                'band': 'lunch',
                'source': 'corpus',
            }

        monkeypatch.setattr(api_main.suggest, 'chips', chips)
        r = client.get('/suggestions')
        # The endpoint must ASK for the model-free path rather than having its own.
        assert seen['use_model'] is False
        assert r.status_code == 200
        assert r.json()['source'] == 'corpus'
        assert r.json()['chips'][0]['label'] == 'nasi lemak'

    def test_an_unreachable_corpus_offers_nothing_rather_than_inventing(self, client, monkeypatch):
        def boom(**_):
            raise psycopg.OperationalError('no route to host')

        monkeypatch.setattr(api_main.suggest, 'chips', boom)
        r = client.get('/suggestions')
        assert r.status_code == 200
        assert r.json()['chips'] == []
        assert r.json()['source'] == 'unavailable'

    def test_it_is_rate_limited(self):
        # Every call spends a model request. An unmetered endpoint converts
        # somebody else's bandwidth into our quota.
        assert 'suggestions' in api_main.RATE_LIMIT


class TestAServerFaultIsReportedAsAServerFault:
    """Issue #81. An unhandled exception used to escape past `CORSMiddleware`, so
    the browser saw `No 'Access-Control-Allow-Origin' header` and reported a CORS
    misconfiguration that did not exist. The CORS config was measured correct in
    the same session; only the error path skipped it.

    Both halves matter and each is asserted separately below: the header has to
    survive, AND the 500 has to stay a 500. Adding the header by turning the fault
    into a 200 would satisfy the first assertion and be a worse lie than the bug.
    """

    ORIGIN = 'https://makanlah-b5h.pages.dev'

    def _raising(self, client, monkeypatch):
        def boom(*a, **k):
            raise TypeError('a bug in our own code')

        monkeypatch.setattr(api_main.rank, 'recommend', boom)
        return client.post('/recommend', json={'query': 'x'}, headers={'Origin': self.ORIGIN})

    def test_an_unhandled_fault_keeps_its_cors_header(self, client, monkeypatch):
        res = self._raising(client, monkeypatch)
        assert res.headers.get('access-control-allow-origin') == self.ORIGIN

    def test_it_is_still_a_500(self, client, monkeypatch):
        res = self._raising(client, monkeypatch)
        assert res.status_code == 500

    def test_the_body_names_the_fault_without_leaking_its_message(self, client, monkeypatch):
        res = self._raising(client, monkeypatch)
        body = res.json()
        assert body['error'] == 'TypeError'
        # The message can carry SQL, a row, or a path. The class name is enough to
        # tell a client-side debugger this is ours and not theirs.
        assert 'a bug in our own code' not in res.text

    def test_a_fault_is_never_dressed_up_as_a_corpus_outage(self, client, monkeypatch):
        """The discrimination #13 cost us: an OperationalError is an outage and
        degrades to 200; a ProgrammingError is our bug and must not borrow that
        costume."""
        res = self._raising(client, monkeypatch)
        assert res.json().get('degraded') is not True

    def test_a_preflight_is_untouched(self, client):
        res = client.options(
            '/recommend',
            headers={
                'Origin': self.ORIGIN,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            },
        )
        assert res.status_code == 200
        assert res.headers.get('access-control-allow-origin') == self.ORIGIN

    def test_a_hostile_origin_is_still_refused_on_a_fault(self, client, monkeypatch):
        """The fix must not become a CORS bypass: the handler adds the header the
        middleware would have added, and the middleware adds none for an origin it
        does not know."""

        def boom(*a, **k):
            raise TypeError('a bug in our own code')

        monkeypatch.setattr(api_main.rank, 'recommend', boom)
        res = client.post('/recommend', json={'query': 'x'}, headers={'Origin': 'https://evil.example'})
        assert res.headers.get('access-control-allow-origin') is None


class TestTheMatchBlockDoesNotClaimADishItDidNotMatch:
    """`match.dish` was set from the QUERY while `match.basis` was set per row.

    Measured on prod: `roti canai` returned `basis: 'semantic', dish: 'roti canai'`
    on five venues that have nothing to do with it. The two that do carry it, Devi's
    Corner and Kapitan, were dropped by `with_live_citations` -- both have a single
    RedNote citation and both are dead -- so the lane resolved the dish correctly and
    no row that reached the client had matched it.

    Nothing renders `match.dish` today, which is why it was free to be wrong. A
    payload field that is untrue becomes untrue UI the moment somebody binds to it.
    """

    def _match(self, client, monkeypatch, basis):
        r = _ranked_result(basis=basis, dish='roti canai')
        monkeypatch.setattr(
            api_main.rank,
            'recommend',
            lambda *a, **k: {'results': [r], 'degraded': False, 'degraded_reasons': [], 'sources_used': ['rednote']},
        )
        return client.post('/recommend', json={'query': 'roti canai'}).json()['results'][0]['match']

    def test_a_dish_row_still_names_its_dish(self, client, monkeypatch):
        m = self._match(client, monkeypatch, 'dish')
        assert m['basis'] == 'dish'
        assert m['dish'] == 'roti canai'

    def test_the_field_survives_the_contract(self, client, monkeypatch):
        # `dish` stays in the block whatever its value -- a client typing against
        # {basis, dish, similarity} must not find the key missing on a semantic row.
        assert set(self._match(client, monkeypatch, 'semantic')) == {'basis', 'dish', 'similarity'}

    # The two above mock `rank.recommend` wholesale, so they assert the endpoint
    # passes the block through and NOTHING about the rule that builds it. The rule
    # itself is `rank.match_block`, tested directly below.

    def test_a_row_the_lexical_lane_did_not_reach_claims_no_dish(self):
        m = api_main.rank.match_block('v9', lexical_set={'v1'}, dish='roti canai', scores={'v9': 0.51})
        assert m['basis'] == 'semantic'
        assert m['dish'] is None, 'a semantic row must not name the dish the query resolved to'

    def test_a_row_the_lexical_lane_reached_names_it(self):
        m = api_main.rank.match_block('v1', lexical_set={'v1'}, dish='roti canai', scores={'v1': 0.62})
        assert m == {'basis': 'dish', 'dish': 'roti canai', 'similarity': 0.62}

    def test_a_venue_the_vector_lane_never_scored_reports_zero_not_a_crash(self):
        # Lexical hits are prepended to the retrieval order, so a venue can be in
        # the list with no cosine at all. Measured on prod: 春记大埔面 came back
        # `basis: dish, similarity: 0.0`.
        assert api_main.rank.match_block('v1', lexical_set={'v1'}, dish='char siew', scores={})['similarity'] == 0.0

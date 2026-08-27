"""The API contract, against fixtures.

No database, no network. docs/TRD.md is explicit that a suite hitting a live
platform fails when a session expires, and a red check that means nothing trains
everyone to ignore red checks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

fastapi_testclient = pytest.importorskip('fastapi.testclient')
TestClient = fastapi_testclient.TestClient

from api import main as api_main  # noqa: E402


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
        def boom(*a, **k):
            raise RuntimeError('neon unreachable')

        monkeypatch.setattr(api_main.rank, 'recommend', boom)
        res = client.post('/recommend', json={'query': 'x'})
        assert res.status_code == 200
        body = res.json()
        assert body['results'] == []
        assert body['degraded'] is True
        assert body['error'] == 'RuntimeError'

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

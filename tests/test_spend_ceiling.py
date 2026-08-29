"""The ceiling that bounds the bill.

Per-IP rate limits bound one host, not spend: a hundred hosts at nineteen
requests a minute each are all individually polite and collectively expensive.
`/recommend` costs two model calls and `/ask` costs one, so an unbounded public
endpoint converts someone else's bandwidth into our invoice.

Measured on 2026-08-29: one /recommend is ~2,150 input and ~200 output tokens on
qwen3.8-flash, $0.15/M and $0.47/M on the Singapore endpoint, so $0.00042 a call.
The default 2000-call budget is about $0.42 a day.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

fastapi_testclient = pytest.importorskip('fastapi.testclient')
TestClient = fastapi_testclient.TestClient

from api import main as api_main  # noqa: E402


@pytest.fixture(autouse=True)
def reset_counters(monkeypatch):
    """Every test starts from a clean window and a clean budget."""
    api_main._attempts.clear()
    api_main._spend.update({'day': -1, 'calls': 0})
    monkeypatch.setattr(api_main.rank, 'recommend', lambda *a, **k: {'results': [], 'sources_used': []})
    yield
    api_main._attempts.clear()
    api_main._spend.update({'day': -1, 'calls': 0})


@pytest.fixture
def client():
    return TestClient(api_main.app)


class TestBudget:
    def test_a_request_is_charged_before_the_work(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 100)
        client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend['calls'] == 2, 'a recommend is one embedding plus one re-rank'

    def test_serving_stops_when_the_budget_is_gone(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 2)
        first = client.post('/recommend', json={'query': 'laksa'}).json()
        assert first.get('degraded_reasons') != ['daily model budget reached'], 'the first one is affordable'
        body = client.post('/recommend', json={'query': 'satay'}).json()
        assert body['degraded'] is True
        assert body['degraded_reasons'] == ['daily model budget reached']
        assert body['results'] == []

    def test_a_spent_budget_never_calls_the_model(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 0)
        called = []
        monkeypatch.setattr(api_main.rank, 'recommend', lambda *a, **k: called.append(1) or {'results': []})
        client.post('/recommend', json={'query': 'laksa'})
        assert called == [], 'the whole point is that no call is made'

    def test_the_budget_resets_on_a_new_day(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 2)
        client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend_left() == 0
        api_main._spend['day'] -= 1  # yesterday
        assert api_main._spend_left() == 2

    def test_ask_stops_honestly_rather_than_erroring(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 0)
        r = client.post('/ask', json={'venue_id': '00000000-0000-0000-0000-000000000000', 'question': 'halal?'})
        assert r.status_code == 200
        body = r.json()
        assert body['covered'] is False
        assert body['citations'] == [], 'never a citation without a post behind it, even when resting'


class TestRateLimit:
    def test_recommend_is_capped_per_ip(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 10_000)
        limit, _ = api_main.RATE_LIMIT['recommend']
        codes = [client.post('/recommend', json={'query': 'laksa'}).status_code for _ in range(limit + 1)]
        assert codes[-1] == 429
        assert codes.count(429) == 1, 'exactly the one over the line'

    def test_a_rejected_request_is_not_charged(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_CALL_BUDGET', 10_000)
        limit, _ = api_main.RATE_LIMIT['recommend']
        for _ in range(limit + 3):
            client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend['calls'] == limit * 2, 'a 429 costs nothing, so it must not draw down the budget'


class TestDocsAreOff:
    def test_the_endpoint_map_is_not_served_by_default(self, client):
        assert client.get('/openapi.json').status_code == 404
        assert client.get('/docs').status_code == 404

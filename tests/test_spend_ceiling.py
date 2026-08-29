"""The ceiling that bounds the bill, and the share that keeps one troll from taking it.

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
    api_main._spend.update({'day': -1.0, 'myr': 0.0})
    api_main._ip_spend.clear()
    monkeypatch.setattr(api_main.rank, 'recommend', lambda *a, **k: {'results': [], 'sources_used': []})
    yield
    api_main._attempts.clear()
    api_main._spend.update({'day': -1.0, 'myr': 0.0})
    api_main._ip_spend.clear()


@pytest.fixture
def client():
    return TestClient(api_main.app)


class TestBudget:
    def test_a_request_is_charged_before_the_work(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 100.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)
        client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend['myr'] == 2.0, 'a recommend is one embedding plus one re-rank'

    def test_serving_stops_when_the_budget_is_gone(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 2.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)
        first = client.post('/recommend', json={'query': 'laksa'}).json()
        assert first.get('degraded_reasons') != ['daily model budget reached'], 'the first one is affordable'
        body = client.post('/recommend', json={'query': 'satay'}).json()
        assert body['degraded'] is True
        assert body['degraded_reasons'] == ['daily model budget reached']
        assert body['results'] == []

    def test_a_spent_budget_never_calls_the_model(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 0.0)
        called = []
        monkeypatch.setattr(api_main.rank, 'recommend', lambda *a, **k: called.append(1) or {'results': []})
        client.post('/recommend', json={'query': 'laksa'})
        assert called == [], 'the whole point is that no call is made'

    def test_the_budget_resets_on_a_new_day(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 2.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)
        client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend_left() == 0
        # Advance the clock rather than poking _spend['day']. The day now lives in
        # the ledger, so mutating the in-memory mirror changes nothing -- and a
        # test that reaches past the real seam stops testing the real behaviour.
        import time as _time

        real_time = _time.time
        monkeypatch.setattr(_time, 'time', lambda: real_time() + 86400)
        assert api_main._spend_left() == 2

    def test_ask_stops_honestly_rather_than_erroring(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 0.0)
        r = client.post('/ask', json={'venue_id': '00000000-0000-0000-0000-000000000000', 'question': 'halal?'})
        assert r.status_code == 200
        body = r.json()
        assert body['covered'] is False
        assert body['citations'] == [], 'never a citation without a post behind it, even when resting'


class TestFairShare:
    """One visitor burning their slice must not cost the next visitor anything.
    This is the difference between a budget and a bigger bucket to drain."""

    def test_one_ip_cannot_take_the_whole_day(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 100.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 0.1)  # RM10 of RM100
        monkeypatch.setitem(api_main.RATE_LIMIT, 'recommend', (10_000, 60))
        blocked = 0
        for _ in range(10):
            body = client.post('/recommend', json={'query': 'laksa'}).json()
            if body.get('degraded_reasons') == ['daily model budget reached']:
                blocked += 1
        assert blocked > 0, 'the greedy visitor must be cut off'
        assert api_main._spend['myr'] <= 10.0, 'and cut off at their share, not the whole budget'
        assert api_main._spend_left() >= 90.0, 'the rest of the day survives for everyone else'

    def test_a_second_visitor_still_gets_served(self, client, monkeypatch):
        # The budget is deliberately small enough that the troll's ten requests
        # would drain it outright without a share. If this test can pass with the
        # share removed it is not guarding anything.
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 10.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 0.2)  # RM2 -- one request each
        monkeypatch.setattr(api_main, 'TRUST_PROXY_HEADER', True)
        monkeypatch.setitem(api_main.RATE_LIMIT, 'recommend', (10_000, 60))
        troll = {'cf-connecting-ip': '10.0.0.1'}
        for _ in range(10):
            client.post('/recommend', json={'query': 'laksa'}, headers=troll)
        assert api_main._spend['myr'] <= 2.0, 'the troll is held to their share'
        visitor = client.post('/recommend', json={'query': 'satay'}, headers={'cf-connecting-ip': '10.0.0.2'}).json()
        assert visitor.get('degraded_reasons') != ['daily model budget reached'], (
            'a second visitor must be unaffected by the first one being greedy'
        )

    def test_the_real_visitor_is_read_from_the_edge_header(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'TRUST_PROXY_HEADER', True)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 100.0)
        client.post('/recommend', json={'query': 'laksa'}, headers={'cf-connecting-ip': '203.0.113.9'})
        assert '203.0.113.9' in api_main._ip_spend

    def test_the_edge_header_is_ignored_when_not_behind_a_proxy(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'TRUST_PROXY_HEADER', False)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 100.0)
        client.post('/recommend', json={'query': 'laksa'}, headers={'cf-connecting-ip': '203.0.113.9'})
        assert '203.0.113.9' not in api_main._ip_spend, 'a spoofed header must not buy a fresh allowance'


class TestRateLimit:
    def test_recommend_is_capped_per_ip(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 10_000.0)
        limit, _ = api_main.RATE_LIMIT['recommend']
        codes = [client.post('/recommend', json={'query': 'laksa'}).status_code for _ in range(limit + 1)]
        assert codes[-1] == 429
        assert codes.count(429) == 1, 'exactly the one over the line'

    def test_a_rejected_request_is_not_charged(self, client, monkeypatch):
        monkeypatch.setattr(api_main, 'DAILY_BUDGET_MYR', 10_000.0)
        monkeypatch.setattr(api_main, 'MYR_PER_CALL', 1.0)
        monkeypatch.setattr(api_main, 'IP_DAILY_SHARE', 1.0)
        limit, _ = api_main.RATE_LIMIT['recommend']
        for _ in range(limit + 3):
            client.post('/recommend', json={'query': 'laksa'})
        assert api_main._spend['myr'] == limit * 2.0, 'a 429 costs nothing, so it must not draw down the budget'


class TestDocsAreOff:
    def test_the_endpoint_map_is_not_served_by_default(self, client):
        assert client.get('/openapi.json').status_code == 404
        assert client.get('/docs').status_code == 404

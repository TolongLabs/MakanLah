"""The auth endpoints, against fakes.

No database: docs/TRD.md rules a live dependency out of CI. The db module is
replaced wholesale, so these assert the CONTRACT -- status codes, what is
returned, and what must never be returned.
"""

import contextlib
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

fastapi_testclient = pytest.importorskip('fastapi.testclient')
TestClient = fastapi_testclient.TestClient

from api import main as api_main  # noqa: E402
from makanlah import auth  # noqa: E402

REAL_PW = 'a-real-password'
USER = {'id': uuid.uuid4(), 'email': 'diner@example.com', 'is_guest': False}
GUEST = {'id': uuid.uuid4(), 'email': 'guest@makanlah.local', 'is_guest': True}


class FakeDb:
    """Only what the endpoints touch."""

    SESSION_DAYS = 30
    GUEST_SESSION_HOURS = 12

    def __init__(self):
        self.users = {USER['email']: {**USER, 'password_hash': auth.hash_password(REAL_PW)}}
        self.sessions = {}
        self.prefs = {}

    @contextlib.contextmanager
    def connect(self, direct=False):
        yield self

    def commit(self):
        pass

    def create_user(self, con, *, email, password_hash):
        email = email.strip().lower()
        if email in self.users:
            return None
        row = {'id': uuid.uuid4(), 'email': email, 'is_guest': False, 'password_hash': password_hash}
        self.users[email] = row
        return row

    def user_by_email(self, con, email):
        return self.users.get(email.strip().lower())

    def guest_user(self, con):
        return dict(GUEST)

    def open_session(self, con, user_id, *, hours):
        token = auth.new_token()
        self.sessions[auth.token_fingerprint(token)] = user_id
        return token

    def user_for_token(self, con, token):
        uid = self.sessions.get(auth.token_fingerprint(token or ''))
        if uid is None:
            return None
        for u in self.users.values():
            if u['id'] == uid:
                return {k: u[k] for k in ('id', 'email', 'is_guest')}
        return dict(GUEST) if uid == GUEST['id'] else None

    def close_session(self, con, token):
        self.sessions.pop(auth.token_fingerprint(token or ''), None)

    def get_prefs(self, con, user_id):
        return self.prefs.get(user_id, {})

    def set_prefs(self, con, user_id, prefs):
        self.prefs[user_id] = prefs
        return prefs


@pytest.fixture
def fake(monkeypatch):
    f = FakeDb()
    monkeypatch.setattr(api_main, 'db', f)
    api_main._attempts.clear()
    return f


@pytest.fixture
def client(fake):
    return TestClient(api_main.app)


class TestSearchIsNeverGated:
    """The product promises a decision in under two minutes. A login wall in
    front of search breaks that, so this is an invariant, not a preference."""

    def test_recommend_works_with_no_authorization_header(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank, 'recommend', lambda *a, **k: {'results': [], 'degraded': False, 'sources_used': []}
        )
        assert client.post('/recommend', json={'query': 'bak kut teh'}).status_code == 200

    def test_recommend_works_with_a_junk_authorization_header(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main.rank, 'recommend', lambda *a, **k: {'results': [], 'degraded': False, 'sources_used': []}
        )
        res = client.post('/recommend', json={'query': 'x'}, headers={'Authorization': 'Bearer nonsense'})
        assert res.status_code == 200


class TestSignup:
    def test_a_new_account_is_created_and_signed_in(self, client):
        res = client.post('/auth/signup', json={'email': 'new@example.com', 'password': 'long-enough-pw'})
        assert res.status_code == 200
        body = res.json()
        assert body['token']
        assert body['user']['email'] == 'new@example.com'
        assert body['user']['is_guest'] is False
        assert body['user']['shared'] is False

    def test_a_duplicate_address_is_rejected(self, client):
        assert (
            client.post('/auth/signup', json={'email': USER['email'], 'password': 'long-enough-pw'}).status_code == 409
        )

    @pytest.mark.parametrize('bad', ['nope', 'a@b', 'a b@c.com', ''])
    def test_an_implausible_address_is_rejected(self, client, bad):
        assert client.post('/auth/signup', json={'email': bad, 'password': 'long-enough-pw'}).status_code == 422

    def test_a_short_password_is_rejected(self, client):
        assert client.post('/auth/signup', json={'email': 'x@y.com', 'password': 'short'}).status_code == 422

    def test_the_response_never_carries_the_password_or_its_hash(self, client):
        res = client.post('/auth/signup', json={'email': 'new@example.com', 'password': 'long-enough-pw'})
        raw = res.text
        assert 'long-enough-pw' not in raw
        assert 'scrypt$' not in raw
        assert 'password' not in res.json()['user']


class TestLogin:
    def test_correct_credentials_return_a_token(self, client):
        res = client.post('/auth/login', json={'email': USER['email'], 'password': REAL_PW})
        assert res.status_code == 200 and res.json()['token']

    def test_a_wrong_password_is_401(self, client):
        assert (
            client.post('/auth/login', json={'email': USER['email'], 'password': 'wrong-password'}).status_code == 401
        )

    def test_an_unknown_address_is_401_with_the_same_message(self, client):
        wrong = client.post('/auth/login', json={'email': USER['email'], 'password': 'wrong-password'})
        unknown = client.post('/auth/login', json={'email': 'nobody@example.com', 'password': 'wrong-password'})
        assert unknown.status_code == 401
        assert unknown.json()['detail'] == wrong.json()['detail'], 'the response distinguishes account existence'

    def test_the_guest_cannot_be_logged_into_with_a_password(self, client, fake):
        """It has no password_hash, so the password path must never authenticate it."""
        fake.users[GUEST['email']] = {**GUEST, 'password_hash': None}
        assert (
            client.post('/auth/login', json={'email': GUEST['email'], 'password': 'anything-at-all'}).status_code == 401
        )


class TestGuest:
    def test_guest_sign_in_reports_that_the_account_is_shared(self, client):
        """The client must be able to disclose this BEFORE the click."""
        body = client.post('/auth/guest').json()
        assert body['user']['is_guest'] is True
        assert body['user']['shared'] is True
        assert body['token']

    def test_every_guest_lands_on_the_same_account(self, client):
        a = client.post('/auth/guest').json()['user']['id']
        b = client.post('/auth/guest').json()['user']['id']
        assert a == b


class TestSessions:
    def test_me_requires_a_token(self, client):
        assert client.get('/auth/me').status_code == 401

    def test_me_rejects_an_unknown_token(self, client):
        assert client.get('/auth/me', headers={'Authorization': 'Bearer nope'}).status_code == 401

    def test_me_returns_the_signed_in_user_and_prefs(self, client):
        token = client.post('/auth/login', json={'email': USER['email'], 'password': REAL_PW}).json()['token']
        body = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
        assert body['user']['email'] == USER['email']
        assert body['prefs'] == {}

    def test_logout_ends_the_session(self, client):
        token = client.post('/auth/login', json={'email': USER['email'], 'password': REAL_PW}).json()['token']
        auth_header = {'Authorization': f'Bearer {token}'}
        assert client.get('/auth/me', headers=auth_header).status_code == 200
        client.post('/auth/logout', headers=auth_header)
        assert client.get('/auth/me', headers=auth_header).status_code == 401

    def test_prefs_round_trip(self, client):
        token = client.post('/auth/login', json={'email': USER['email'], 'password': REAL_PW}).json()['token']
        h = {'Authorization': f'Bearer {token}'}
        prefs = {'craving': ['soupy'], 'company': 'solo', 'range_m': 3000, 'mood': 'comfort'}
        assert client.put('/auth/prefs', json={'prefs': prefs}, headers=h).json()['prefs'] == prefs
        assert client.get('/auth/me', headers=h).json()['prefs'] == prefs

    def test_prefs_require_a_token(self, client):
        assert client.put('/auth/prefs', json={'prefs': {}}).status_code == 401


class TestRateLimiting:
    def test_repeated_failed_logins_are_throttled(self, client):
        limit = api_main.RATE_LIMIT['login'][0]
        codes = [
            client.post('/auth/login', json={'email': USER['email'], 'password': 'wrong-password'}).status_code
            for _ in range(limit + 3)
        ]
        assert 429 in codes, 'credential stuffing from one host is not throttled'
        assert codes[0] == 401

    def test_guest_sign_in_is_throttled(self, client):
        """The guest credential is effectively public, so it is the cheapest
        endpoint to abuse."""
        limit = api_main.RATE_LIMIT['guest'][0]
        codes = [client.post('/auth/guest').status_code for _ in range(limit + 3)]
        assert 429 in codes

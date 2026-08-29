"""The interactive runtime. Latency-sensitive, and it never scrapes.

Separate process and separate host from ingest/ (docs/TRD.md). It shares the
makanlah/ library and shares nothing at runtime.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from makanlah import auth, config, copilot, db, rank

# An outage is a connection that cannot be made. A ProgrammingError, a TypeError
# or a KeyError is our own bug and must not be dressed up as one.
CORPUS_UNREACHABLE = (psycopg.OperationalError, psycopg.InterfaceError)

# /docs and /openapi.json hand a reader the full endpoint map, including the auth
# routes. There is no third-party developer audience for this API, so they are on
# only when explicitly asked for.
_DOCS = os.environ.get('ENABLE_DOCS', '').lower() in ('1', 'true', 'yes')

app = FastAPI(
    title='MakanLah API',
    version='0.1.0',
    docs_url='/docs' if _DOCS else None,
    redoc_url=None,
    openapi_url='/openapi.json' if _DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.settings().cors_origins),
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)


class RecommendRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = Field(default=None, ge=100, le=50000)
    budget: int | None = Field(default=None, ge=1, le=4)
    cuisine: str | None = None
    limit: int = Field(default=10, ge=1, le=20)


@app.get('/health')
def health():
    """Reports corpus state, and key presence by name only — never a value."""
    out = {'ok': True, 'corpus_size': 0, 'venues': 0, 'oldest_capture': None, 'newest_capture': None}
    try:
        with db.connect() as con:
            r = con.execute('select count(*) c, min(captured_at) lo, max(captured_at) hi from source_post').fetchone()
            out['corpus_size'] = r['c']
            out['oldest_capture'] = r['lo'].isoformat() if r['lo'] else None
            out['newest_capture'] = r['hi'].isoformat() if r['hi'] else None
            out['venues'] = con.execute('select count(*) c from venue').fetchone()['c']
    except Exception as e:
        out['ok'] = False
        out['error'] = type(e).__name__
    out['configured'] = config.describe()
    return out


@app.post('/recommend')
def recommend(req: RecommendRequest, request: Request):
    """Every entry cites a real post. An entry that cannot be cited is dropped
    before the response is built, never returned with a caveat."""
    _rate_limit('recommend', request)
    # Two calls: one embedding, one re-rank. Charged before the work, so a
    # request that fails halfway still counts what it spent.
    if _spend_left() < 2:
        return {
            'results': [],
            'degraded': True,
            'degraded_reasons': ['daily model budget reached'],
            'sources_used': [],
        }
    _charge(2)
    try:
        out = rank.recommend(req.query, lat=req.lat, lng=req.lng, radius_m=req.radius_m, limit=req.limit)
    except CORPUS_UNREACHABLE as e:
        # An empty, honest answer beats a 500 when the corpus is genuinely away.
        # Only for that: catching everything here reported a 5-placeholder/6-parameter
        # bug as `degraded` for the life of the project, so the entire distance
        # filter was dead in the client while the UI blamed the corpus (issue #13).
        # A code fault raises, and CI and the logs get to see it.
        return {'results': [], 'degraded': True, 'sources_used': [], 'error': type(e).__name__}

    # The invariant, asserted at the boundary rather than trusted upstream.
    out['results'] = [r for r in out['results'] if r.get('citations')]
    return out


# --- Auth --------------------------------------------------------------------
#
# Auth persists preferences. It never gates /recommend: the product promises a
# decision in under two minutes, and a login wall in front of search breaks that.

# The auth buckets exist to stop credential stuffing. `recommend` and `ask` exist
# for a different reason: each one spends a model call, so an unbounded endpoint
# converts someone else's spare bandwidth into our bill.
RATE_LIMIT = {
    'login': (10, 300),
    'guest': (20, 300),
    'signup': (5, 3600),
    'recommend': (20, 60),
    'ask': (10, 60),
}
_attempts: dict[tuple[str, str], list[float]] = {}

# The ceiling that actually bounds the bill.
#
# Per-IP limits do not bound spend: they bound one host. A hundred hosts at
# nineteen requests a minute each are all individually polite. This counts every
# model call the process makes, against a budget stated in calls per day, and
# stops serving when it is gone.
#
# Deliberately a hard stop rather than a throttle. Degrading is what this product
# already does when the corpus is unreachable, and the client already renders it
# honestly. An unexpected invoice has no such affordance.
DAILY_CALL_BUDGET = int(os.environ.get('DAILY_CALL_BUDGET', '2000'))
_spend: dict[str, int] = {'day': -1, 'calls': 0}


def _budget_day() -> int:
    return int(time.time() // 86400)


def _spend_left() -> int:
    if _spend['day'] != _budget_day():
        _spend['day'], _spend['calls'] = _budget_day(), 0
    return DAILY_CALL_BUDGET - _spend['calls']


def _charge(calls: int = 1) -> None:
    _spend_left()
    _spend['calls'] += calls


def _rate_limit(bucket: str, request: Request) -> None:
    """In-process, per-IP, sliding window.

    Deliberately not durable: one API process today, and a limiter that needs
    Redis to exist is a limiter nobody turns on. It stops credential stuffing
    from one host, not a distributed attack -- say so rather than imply more.
    """
    limit, window = RATE_LIMIT[bucket]
    now = time.time()
    key = (bucket, request.client.host if request.client else 'unknown')
    hits = [t for t in _attempts.get(key, []) if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail='Too many attempts, try again shortly.')
    hits.append(now)
    _attempts[key] = hits


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=auth.MIN_PASSWORD, max_length=auth.MAX_PASSWORD)


class Prefs(BaseModel):
    prefs: dict = Field(default_factory=dict)


def _shape(user, *, token=None):
    out = {
        'user': {
            'id': str(user['id']),
            'email': user['email'],
            'is_guest': user['is_guest'],
            # The guest is ONE row shared by everyone who signs in as it, so the
            # client can and must say so before the click, not after.
            'shared': bool(user['is_guest']),
        }
    }
    if token:
        out['token'] = token
    return out


def current_user(authorization: str | None = Header(default=None)):
    """None when absent, unknown or expired. Callers that require a user raise 401."""
    if not authorization or not authorization.lower().startswith('bearer '):
        return None
    with db.connect() as con:
        return db.user_for_token(con, authorization.split(' ', 1)[1].strip())


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(status_code=401, detail='Sign in to continue.')
    return user


@app.post('/auth/signup')
def signup(body: Credentials, request: Request):
    _rate_limit('signup', request)
    if not auth.looks_like_email(body.email):
        raise HTTPException(status_code=422, detail='That does not look like an email address.')
    try:
        pw_hash = auth.hash_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    with db.connect() as con:
        user = db.create_user(con, email=body.email, password_hash=pw_hash)
        if not user:
            # Same shape as a successful call would NOT be: an address either is
            # or is not free, and a signup form reveals that either way.
            raise HTTPException(status_code=409, detail='That email is already registered.')
        token = db.open_session(con, user['id'], hours=db.SESSION_DAYS * 24)
        con.commit()
    return _shape(user, token=token)


@app.post('/auth/login')
def login(body: Credentials, request: Request):
    _rate_limit('login', request)
    with db.connect() as con:
        user = db.user_by_email(con, body.email)
        # Verify against a throwaway hash when the address is unknown, so the
        # response time does not separate "no such account" from "wrong password".
        stored = (user or {}).get('password_hash') or auth.hash_password('x' * auth.MIN_PASSWORD)
        if not user or not user['password_hash'] or not auth.verify_password(body.password, stored):
            raise HTTPException(status_code=401, detail='Email or password is incorrect.')
        token = db.open_session(con, user['id'], hours=db.SESSION_DAYS * 24)
        con.commit()
    return _shape(user, token=token)


@app.post('/auth/guest')
def guest(request: Request):
    """ONE shared account. Everything done under it is visible to every other
    guest, which is why `shared` is true and the session is short."""
    _rate_limit('guest', request)
    with db.connect() as con:
        user = db.guest_user(con)
        if not user:
            raise HTTPException(status_code=503, detail='Guest access is unavailable.')
        token = db.open_session(con, user['id'], hours=db.GUEST_SESSION_HOURS)
        con.commit()
    return _shape(user, token=token)


@app.post('/auth/logout')
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith('bearer '):
        with db.connect() as con:
            db.close_session(con, authorization.split(' ', 1)[1].strip())
            con.commit()
    return {'ok': True}


@app.get('/auth/me')
def me(user=Depends(require_user)):
    with db.connect() as con:
        prefs = db.get_prefs(con, user['id'])
    return {**_shape(user), 'prefs': prefs}


@app.put('/auth/prefs')
def put_prefs(body: Prefs, user=Depends(require_user)):
    with db.connect() as con:
        prefs = db.set_prefs(con, user['id'], body.prefs)
        con.commit()
    return {'prefs': prefs}


# --- Copilot -----------------------------------------------------------------


class AskRequest(BaseModel):
    venue_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=300)


@app.post('/ask')
def ask(req: AskRequest, request: Request):
    """One question about one venue, answered from the corpus or not at all.

    `covered: false` is a correct answer, not an error -- saying the posts do not
    cover something is the honesty the citation trail exists to support. Like
    /recommend, this is not gated by auth.
    """
    _rate_limit('ask', request)
    if _spend_left() < 1:
        return {'covered': False, 'answer': 'The assistant is resting for today.', 'citations': []}
    _charge(1)
    try:
        out = copilot.ask(req.venue_id, req.question)
    except CORPUS_UNREACHABLE as e:
        return {'covered': False, 'answer': 'The corpus is unavailable.', 'citations': [], 'error': type(e).__name__}
    except ValueError:
        raise HTTPException(status_code=422, detail='That venue id is not valid.') from None

    # The invariant, asserted at the boundary rather than trusted upstream: a
    # covered answer carries evidence, or it is not covered.
    if out['covered'] and not out['citations']:
        out['covered'] = False
    return out


@app.get('/venue/{venue_id}')
def venue(venue_id: str, lat: float | None = None, lng: float | None = None):
    """One venue and its citation trail. Not gated by auth.

    404 rather than an empty entry when the venue has no citations: an entry
    that cannot be cited is not a result, and the deep link should say so.
    """
    try:
        out = rank.one(venue_id, lat=lat, lng=lng)
    except CORPUS_UNREACHABLE as e:
        return {'venue': None, 'degraded': True, 'error': type(e).__name__}
    except ValueError:
        raise HTTPException(status_code=422, detail='That venue id is not valid.') from None
    if not out:
        raise HTTPException(status_code=404, detail='We have no posts for that place.')
    return out

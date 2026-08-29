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

from makanlah import auth, companion, config, copilot, db, rank, suggest

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

_cors = config.settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_cors.cors_origins),
    # An explicit CORS_ORIGINS list wins; otherwise the project's own Pages hosts
    # and localhost. `allow_credentials` stays off, so this is a spend control
    # rather than a session one -- and it does nothing to curl, which is why the
    # daily budget above is the real answer.
    allow_origin_regex=None if _cors.cors_origins else _cors.cors_origin_regex,
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
            # Venues the product can actually show, not rows in the table. The
            # landing page prints this under "Places somebody wrote about", and
            # after the #42 replay nine venues have no surviving mention -- they
            # are in `uncited_venue`, unrankable, and invisible to every other
            # surface. Counting them overstates the evidence on the one page
            # whose argument is that the evidence is not overstated.
            out['venues'] = con.execute(
                """select count(*) c from (
                     select v.id from venue v
                     join mention m on m.venue_id = v.id
                     where m.excerpt is not null
                     group by v.id
                   ) t"""
            ).fetchone()['c']
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
    if not _affordable(request, 2):
        return {
            'results': [],
            'degraded': True,
            'degraded_reasons': ['daily model budget reached'],
            'sources_used': [],
        }
    _charge(request, 2)
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
    # The wizard is four steps, so a person legitimately hits this four or five
    # times in a minute. Above that it is a loop, not a user.
    'companion': (12, 60),
    # One call per page load, plus a refresh or two. Above that it is a loop.
    'suggestions': (10, 60),
}
_attempts: dict[tuple[str, str], list[float]] = {}

# The ceiling that actually bounds the bill, stated in the currency the owner
# thinks in rather than in calls.
#
# Per-IP limits do not bound spend: they bound one host. A hundred hosts at
# nineteen requests a minute each are all individually polite and collectively
# expensive. This meters money.
#
# MYR_PER_CALL is measured, not guessed. One /recommend is ~2,150 input and ~200
# output tokens and spends two calls, one embedding and one re-rank. On
# qwen3.7-flash-2026-07-15 at the Singapore 0-32K tier, $0.030/M and $0.130/M,
# that is USD 0.00009 a request, about RM 0.0004, so RM 0.0002 a call.
#
# It is an average across the two calls rather than a per-lane price: the
# embedding is 2-6 tokens and costs effectively nothing, the re-rank is the whole
# bill. Splitting them would be more precise and would not change a decision.
#
# RE-MEASURE WHEN A LANE IS RE-PINNED. The previous lane cost 4.6x this, and
# nothing in the code would have noticed.
DAILY_BUDGET_MYR = float(os.environ.get('DAILY_BUDGET_MYR', '10'))
MYR_PER_CALL = float(os.environ.get('MYR_PER_CALL', '0.0002'))

# No single visitor may take more than this share of the day. The point is not to
# be fair, it is that one troll with a loop should cost the other visitors
# nothing: they burn their slice, get 429 for the rest of the day, and everybody
# else still gets answers. Without it a budget is just a bigger bucket to drain.
IP_DAILY_SHARE = float(os.environ.get('IP_DAILY_SHARE', '0.1'))

_spend: dict[str, float] = {'day': -1.0, 'myr': 0.0}
_ip_spend: dict[str, float] = {}

# The companion lane is metered in requests, not ringgit, because it is on a free
# tier rather than a paid one: 500 requests a day, 15 a minute. Counting it in
# MYR would report a bill that does not exist and, worse, would let the paid
# budget's headroom authorise a call the free quota has already refused.
#
# The cap is under the quota, not at it. Crossing a free tier does not fail, it
# starts charging, and spending real money is a thing this project stops for.
COMPANION_DAILY = int(os.environ.get('COMPANION_DAILY', '400'))
COMPANION_PER_MIN = int(os.environ.get('COMPANION_PER_MIN', '12'))
_companion: dict[str, float] = {'day': -1.0, 'used': 0.0}
_companion_minute: list[float] = []


def _budget_day() -> int:
    return int(time.time() // 86400)


def _roll_day() -> None:
    if _spend['day'] != _budget_day():
        _spend['day'], _spend['myr'] = float(_budget_day()), 0.0
        _ip_spend.clear()


def _spend_left() -> float:
    """Ringgit left in the day."""
    _roll_day()
    return DAILY_BUDGET_MYR - _spend['myr']


def _ip_left(ip: str) -> float:
    """Ringgit left for one visitor today."""
    _roll_day()
    return (DAILY_BUDGET_MYR * IP_DAILY_SHARE) - _ip_spend.get(ip, 0.0)


def _companion_quota() -> bool:
    """True if the free Gemini tier has room for one more line, right now."""
    if _companion['day'] != _budget_day():
        _companion['day'], _companion['used'] = float(_budget_day()), 0.0
        _companion_minute.clear()
    now = time.time()
    _companion_minute[:] = [t for t in _companion_minute if now - t < 60]
    if _companion['used'] >= COMPANION_DAILY or len(_companion_minute) >= COMPANION_PER_MIN:
        return False
    _companion['used'] += 1
    _companion_minute.append(now)
    return True


def _affordable(request: Request, calls: int) -> bool:
    cost = calls * MYR_PER_CALL
    return _spend_left() >= cost and _ip_left(_client_ip(request)) >= cost


def _charge(request: Request, calls: int = 1) -> None:
    _roll_day()
    cost = calls * MYR_PER_CALL
    _spend['myr'] += cost
    ip = _client_ip(request)
    _ip_spend[ip] = _ip_spend.get(ip, 0.0) + cost


def _client_ip(request: Request) -> str:
    """Behind Cloudflare the socket peer is Cloudflare, so the real visitor is in
    CF-Connecting-IP. Trusted only because nothing but our own edge terminates
    TLS in front of this; a direct deployment must not trust it."""
    if TRUST_PROXY_HEADER:
        fwd = request.headers.get('cf-connecting-ip') or request.headers.get('x-forwarded-for')
        if fwd:
            return fwd.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


TRUST_PROXY_HEADER = os.environ.get('TRUST_PROXY_HEADER', '').lower() in ('1', 'true', 'yes')


def _rate_limit(bucket: str, request: Request) -> None:
    """In-process, per-IP, sliding window.

    Deliberately not durable: one API process today, and a limiter that needs
    Redis to exist is a limiter nobody turns on. It stops credential stuffing
    from one host, not a distributed attack -- say so rather than imply more.
    """
    limit, window = RATE_LIMIT[bucket]
    now = time.time()
    key = (bucket, _client_ip(request))
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
    if not _affordable(request, 1):
        return {'covered': False, 'answer': 'The assistant is resting for today.', 'citations': []}
    _charge(request, 1)
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


class CompanionRequest(BaseModel):
    step: str = Field(min_length=1, max_length=20)
    # The labels the user just tapped, and nothing else. Never a corpus row.
    picked: list[str] = Field(default_factory=list, max_length=6)


@app.post('/companion')
def companion_line(req: CompanionRequest, request: Request):
    """One cheerful sentence for the onboarding wizard. Not gated by auth.

    Decoration, deliberately: it sees no corpus row, names no venue and makes no
    claim, which is what makes it safe to let a model write. `source` says
    whether the model or the script produced it -- the client renders both the
    same way, so without this field a dead lane looks identical to a live one.

    A refusal here is not an error. Out of quota returns the scripted line with
    200, because a wizard whose companion goes silent on a rate limit is a worse
    outcome than a slightly repetitive companion.
    """
    _rate_limit('companion', request)
    if not _companion_quota():
        return {'text': companion.scripted(req.step), 'source': 'script', 'reason': 'quota'}
    return companion.line(req.step, req.picked)


@app.get('/suggestions')
def suggestions(request: Request):
    """Search chips for /discover, chosen by a model and written by the corpus.

    Every label is a dish string read out of the database, so a chip cannot lead
    to an empty result page. The model only reorders: it is handed a numbered
    list and returns indices, and an index it invents is out of range and
    dropped. `source` says whether it answered.

    Not gated by auth, and it shares the companion's free-tier counter because it
    is the same lane. Out of quota returns the corpus order, which is a perfectly
    good set of chips.
    """
    _rate_limit('suggestions', request)
    try:
        if not _companion_quota():
            with db.connect() as con:
                pool = suggest._candidates(con)
            return {
                'chips': [
                    {'label': r['dish'], 'query': r['dish'], 'posts': r['posts'], 'venues': r['venues']}
                    for r in pool[: suggest.CHIPS]
                ],
                'band': suggest._band(suggest.datetime.now(suggest.MYT).hour),
                'source': 'corpus',
            }
        return suggest.chips()
    except CORPUS_UNREACHABLE as e:
        # No corpus, no honest chips. An empty list renders as no chips at all,
        # which is correct: inventing six would be inventing six dead ends.
        return {'chips': [], 'band': '', 'source': 'unavailable', 'error': type(e).__name__}


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

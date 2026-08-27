"""The interactive runtime. Latency-sensitive, and it never scrapes.

Separate process and separate host from ingest/ (docs/TRD.md). It shares the
makanlah/ library and shares nothing at runtime.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from makanlah import config, db, rank

app = FastAPI(title='MakanLah API', version='0.1.0')

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
def recommend(req: RecommendRequest):
    """Every entry cites a real post. An entry that cannot be cited is dropped
    before the response is built, never returned with a caveat."""
    try:
        out = rank.recommend(req.query, lat=req.lat, lng=req.lng, radius_m=req.radius_m, limit=req.limit)
    except Exception as e:
        # An empty, honest answer beats a 500. The UI says the corpus is unavailable.
        return {'results': [], 'degraded': True, 'sources_used': [], 'error': type(e).__name__}

    # The invariant, asserted at the boundary rather than trusted upstream.
    out['results'] = [r for r in out['results'] if r.get('citations')]
    return out

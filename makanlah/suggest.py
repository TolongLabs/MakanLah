"""Suggestion chips for the search box, chosen by a model, written by the corpus.

**The model returns indices, never text.** It is handed a numbered list of dishes
that are already in the database and asked which ones suit the hour; whatever it
sends back is used to look up strings we already had. A model that hallucinates a
dish produces an out-of-range index, which is dropped. A model that is unreachable
produces nothing, and the corpus order stands.

That is the whole design, and it is deliberately stricter than `companion.py`. A
companion line is small talk and a bad one is merely odd. A chip is a promise that
tapping it returns something, so a chip naming a dish nobody wrote about is a dead
end with the product's own name on it.

Every chip therefore carries the post count behind it. `肉骨茶` is offered because
fourteen people wrote about it, and the UI can say so.
"""

import json
import unicodedata
from datetime import datetime, timedelta, timezone

from makanlah import config, db, models

# MYT. Fixed offset, no DST, and pulling in a tz database for one number is not
# worth the dependency.
MYT = timezone(timedelta(hours=8))

CHIPS = 6
CANDIDATES = 24


def _band(hour: int) -> str:
    if 5 <= hour < 11:
        return 'breakfast'
    if 11 <= hour < 16:
        return 'lunch'
    if 16 <= hour < 22:
        return 'dinner'
    return 'late night supper'


def _key(dish: str) -> str:
    """Fold the variants the corpus stores separately.

    `nasi lemak`, `Nasi Lemak` and a NFKC-different copy of either are one dish to
    a person reading chips. This does NOT fold `椰浆饭` into `nasi lemak` -- that is
    a translation, the corpus deliberately keeps both, and issue #59 owns it.
    """
    return unicodedata.normalize('NFKC', dish).casefold().strip()


# Terms that name pork in so many words. NOT a dietary filter and NOT a halal
# safeguard -- the `soup` chip, which stays, returns three bak kut teh houses in
# its top six with `pork` on the cards. What this changes is that the app does
# not OFFER pork before the user has said anything; what it cannot change is that
# a user may still meet it. Claiming otherwise would overclaim exactly where
# rank.py says overclaiming is unforgivable.
#
# Deliberately a spelling list, not a cuisine one. `bak kut teh`, `char siew` and
# `siu yuk` all stay offerable: excluding them would be the hand-written
# non-halal list this refuses to build -- three such heuristics over food terms
# failed in a single day on 2026-08-28 -- and it would take the most iconic dish
# in this corpus away from the audience it belongs to.
#
# Search, ranking and every dish tag are untouched. This is the default pool only.
DEFAULT_POOL_EXCLUDED = frozenset({'pork', 'babi', '猪肉', '豬肉'})


def offerable(dish) -> bool:
    """Whether this dish may appear in the six unprompted chips."""
    if not isinstance(dish, str):
        return False
    return bool(dish.strip()) and _key(dish) not in DEFAULT_POOL_EXCLUDED


def _candidates(con) -> list[dict]:
    seen: dict[str, dict] = {}
    for row in db.popular_dishes(con, CANDIDATES * 2):
        if not offerable(row['dish']):
            continue
        k = _key(row['dish'])
        keep = seen.get(k)
        # Keep the spelling with the most posts behind it, not the first seen.
        if keep is None or row['posts'] > keep['posts']:
            seen[k] = row
    ranked = sorted(seen.values(), key=lambda r: (-r['posts'], -r['venues']))
    return ranked[:CANDIDATES]


SYSTEM = """You choose which dishes to offer someone opening a Malaysian restaurant app.

You are given a numbered list of dishes and the current meal time in Kuala Lumpur.

Return ONLY a json object: {"pick": [<numbers>]}

Rules:
  - Pick exactly the number of items asked for, by NUMBER, from the list given.
  - Never write a dish name. Never invent a number that is not in the list.
  - Favour dishes a person would actually want at that meal time.
  - Mix it up: not all noodles, not all western, not all the same cuisine.
  - Order them best first."""


def chips(*, now: datetime | None = None, con=None, use_model: bool = True) -> dict:
    """`{'chips': [{label, query, posts, venues}], 'band': str, 'source': str}`.

    `use_model=False` is the out-of-quota path. It is a parameter rather than a
    second code path in the caller so that the database connection has exactly
    one home -- the endpoint used to open its own and CI, which has no
    DATABASE_URL, was the thing that noticed.
    """
    close = con is None
    ctx = db.connect() if close else None
    con = ctx.__enter__() if close else con
    try:
        pool = _candidates(con)
    finally:
        if close:
            ctx.__exit__(None, None, None)

    band = _band((now or datetime.now(MYT)).astimezone(MYT).hour)
    if not pool:
        return {'chips': [], 'band': band, 'source': 'corpus'}

    order = list(range(len(pool)))
    source = 'corpus'

    s = config.settings()
    if use_model and s.companion_api_key:
        listing = '\n'.join(f'{i}. {r["dish"]} ({r["posts"]} posts)' for i, r in enumerate(pool))
        payload = {
            'model': s.companion_model,
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': f'Meal time: {band}. Pick {CHIPS}.\n\nDishes:\n{listing}'},
            ],
            'temperature': 0.8,
            'response_format': {'type': 'json_object'},
        }
        try:
            body = models._post(
                f'{s.companion_base_url}/chat/completions', payload, s.companion_api_key, timeout=s.companion_timeout
            )
            got = models._json_object(models._content(body))
            picked = [n for n in (got.get('pick') or []) if isinstance(n, int) and 0 <= n < len(pool)]
            # Duplicates are the one thing a model reliably does here.
            seen: set[int] = set()
            picked = [n for n in picked if not (n in seen or seen.add(n))]
            if picked:
                # Its choices first, then the corpus order fills any shortfall, so a
                # model that returns two usable indices still yields six chips.
                order = picked + [i for i in order if i not in seen]
                source = 'model'
        except Exception:
            pass

    out = [
        {'label': pool[i]['dish'], 'query': pool[i]['dish'], 'posts': pool[i]['posts'], 'venues': pool[i]['venues']}
        for i in order[:CHIPS]
    ]
    return {'chips': out, 'band': band, 'source': source}


def json_dumps(x):
    return json.dumps(x, ensure_ascii=False)

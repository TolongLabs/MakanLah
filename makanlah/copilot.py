"""The interactive copilot: questions answered from the corpus, or not at all.

**The copilot never introduces a fact.** It routes, quotes, and admits gaps.
Every answer either quotes an excerpt already in the database or says the posts
do not cover the question -- and that second case is the feature, not a
shortfall. Google Maps cannot say "nobody wrote about that" because it has no
evidence trail to be honest about.

Citations are attached from the database after the model answers, never parsed
out of what it said. A model asked for a URL produces a plausible one.
"""

import json

from makanlah import config, db, models

MAX_EXCERPTS = 14
EXCERPT_CHARS = 320

SYSTEM = """You answer one question about one restaurant, using ONLY the numbered excerpts given.

Return ONLY a json object:
  {"covered": true|false, "answer": "<at most 40 words>", "used": [<excerpt numbers>]}

Rules, in order of importance:
  - If the excerpts do not answer the question, set covered false, leave "used"
    empty, and say plainly that the posts do not cover it. Do NOT guess, infer
    from the restaurant's name or cuisine, or fall back on general knowledge.
  - Never state a fact that is not in an excerpt. No prices, hours, addresses or
    dietary claims unless an excerpt says so.
  - "used" lists the excerpt numbers your answer rests on. If covered is true it
    must not be empty.
  - Never output a URL or a citation. Those are attached afterwards.
  - Answer in the language the QUESTION was asked in."""


def _shape(rows):
    out = []
    for i, r in enumerate(rows[:MAX_EXCERPTS]):
        out.append(
            {
                'n': i,
                'excerpt': (r['excerpt'] or '')[:EXCERPT_CHARS],
                'platform': r['platform'],
                'post_url': r['post_url'],
                'author_handle': r['author_handle'],
                'posted_at': r['posted_at_raw'],
                'dishes': list(r['dishes'] or []),
                'sentiment': r['sentiment'],
            }
        )
    return out


def ask(venue_id, question, *, con=None):
    """Answer from this venue's evidence, or report that it is not covered.

    `covered: false` is a correct outcome, not an error. The caller renders it.
    """
    close = con is None
    ctx = db.connect() if close else None
    con = ctx.__enter__() if close else con
    try:
        venue = db.venue_by_id(con, venue_id)
        if not venue:
            return {'covered': False, 'answer': 'That place is not in the corpus.', 'citations': [], 'venue': None}
        rows = _shape(db.venue_evidence(con, venue_id))
    finally:
        if close:
            ctx.__exit__(None, None, None)

    venue_out = {'id': str(venue['id']), 'name': venue['name'], 'area': venue['area']}
    if not rows:
        return {
            'covered': False,
            'answer': 'No posts about this place have been collected yet.',
            'citations': [],
            'venue': venue_out,
        }

    s = config.settings()
    if not s.copilot_api_key:
        # No model lane. An earlier version returned the raw excerpts here, which
        # broke the contract the rest of the module enforces: `covered: false`
        # carries NO citations, so a client can render the two states without
        # inspecting both. CI caught it -- CI has no key, so this was the only
        # branch it ever ran.
        return {
            'covered': False,
            'answer': 'The copilot is unavailable.',
            'citations': [],
            'venue': venue_out,
        }

    listing = '\n'.join(f'[{r["n"]}] ({r["platform"]}) {r["excerpt"]}' for r in rows)
    payload = {
        'model': s.copilot_model,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': f'Restaurant: {venue["name"]}\nQuestion: {question}\n\nExcerpts:\n{listing}'},
        ],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    if not s.copilot_thinking:
        payload['enable_thinking'] = False

    try:
        body = models._post(f'{s.copilot_base_url}/chat/completions', payload, s.copilot_api_key, timeout=45)
        got = models._json_object(models._content(body))
    except Exception:
        return {
            'covered': False,
            'answer': 'The copilot could not answer just now.',
            'citations': [],
            'venue': venue_out,
        }

    covered = bool(got.get('covered'))
    answer = str(got.get('answer') or '').strip()[:400]
    used = [n for n in (got.get('used') or []) if isinstance(n, int) and 0 <= n < len(rows)]

    # The invariant, enforced here rather than trusted: a claim to be covered
    # that rests on no excerpt is not covered. The model does not get to assert
    # grounding it did not use.
    if covered and not used:
        covered = False
        answer = answer or 'The posts do not cover that.'

    citations = _cite([rows[n] for n in used]) if covered else []
    return {'covered': covered, 'answer': answer, 'citations': citations, 'venue': venue_out}


def _cite(rows):
    """Built from database rows, never from model output."""
    return [
        {
            'post_url': r['post_url'],
            'excerpt': r['excerpt'],
            'platform': r['platform'],
            'author_handle': r['author_handle'],
            'posted_at': r['posted_at'],
        }
        for r in rows
    ]


def json_dumps(x):
    return json.dumps(x, ensure_ascii=False)

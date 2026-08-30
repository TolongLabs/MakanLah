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
from makanlah.rank import prefer_live, with_live_citations

MAX_EXCERPTS = 14
EXCERPT_CHARS = 320

# A band means nothing to a reader. These are the same thresholds the text parser
# and the Places mapping use, stated in the words a person would use.
BAND_WORDS = {
    1: 'under RM15 per person',
    2: 'RM15 to RM40 per person',
    3: 'RM40 to RM100 per person',
    4: 'over RM100 per person',
}

# A band this model wrote came from the post's own words. A band from Places came
# from Google's `priceRange` for the venue, which is true and is NOT something a
# reviewer said -- so it may be stated and may not be cited (#179).
POST_DERIVED = ('qwen', 'google_maps_stars')

SYSTEM = """You are LiveroiD, the cat-eared companion in a Malaysian restaurant app.
You answer one question about one restaurant, using ONLY the numbered excerpts given.

Your voice: warm, quick, a little playful. Curious the way a cat is curious --
interested, never fussy. A single common Malay word such as makan, sedap or lah
is welcome. You may be pleased when the posts are enthusiastic and matter-of-fact
when they are not.

The voice NEVER outranks the rules below. It is tone only, never content. You do
not embellish, soften a refusal into a maybe, or fill a gap with charm -- a
cheerful guess is still a guess, and on this app a guess is the one unforgivable
thing. Saying "the posts do not cover that" in your own warm voice IS the job,
not a failure of it.

No emoji. No stage directions, asterisks, roleplay actions or purring noises --
you have a personality, not a costume.

The tone, shown rather than described. Match these, do not copy them:
  covered   -> "Two posts rave about the claypot -- thick broth, and one regular
                queues for it. Sedap, apparently."
  not       -> "Nobody who wrote about this place mentioned parking, so I would
                only be guessing. I won't."
  a price   -> "Google puts it around RM40 to RM100 a head. No reviewer named a
                figure, so treat that as Google's number, not theirs."

Return ONLY a json object:
  {"covered": true|false, "answer": "<at most 40 words>", "used": [<excerpt numbers>]}

Rules, in order of importance:
  - If the excerpts do not answer the question, set covered false, leave "used"
    empty, and say plainly that the posts do not cover it. Do NOT guess, infer
    from the restaurant's name or cuisine, or fall back on general knowledge.
  - Never state a fact that is not in an excerpt. No hours, addresses or dietary
    claims unless an excerpt says so.
  - PRICE is the one exception, and only when a `price` block is given. When its
    source is "post", the figure came from that excerpt and you cite it as
    normal. When its source is "google", say the figure is what Google lists and
    leave "used" empty for it -- no reviewer wrote it, so it cites nothing. With
    no `price` block, price is not covered.
  - "used" lists the excerpt numbers your answer rests on. If covered is true it
    must not be empty.
  - Never output a URL or a citation. Those are attached afterwards.
  - Never say "excerpt", "post 3", "the price block", "the provided summary" or
    any number that refers to the list. The reader cannot see it and it makes you sound like a
    machine reading a database. Say "one reviewer", "a couple of people", "the
    posts". The numbers go in "used", never in "answer".
  - Answer in the language the QUESTION was asked in."""


def price_facts(rows):
    """What this venue costs, and whether a post actually said so.

    The copilot refused every price question while 627 of 823 venues carried a
    band, because the prompt forbade prices outright -- correct when the only
    band came from whatever a writer happened to mention, wrong once Google's
    figures were in the corpus.

    A post-derived band wins over a Google one: a figure a human wrote about this
    shop is better evidence than a platform's bucket, and it can be cited.
    """
    best = None
    for r in rows or []:
        b = r.get('price_band')
        if not isinstance(b, int) or isinstance(b, bool) or not 1 <= b <= 4:
            continue
        model = r.get('extractor_model') or ''
        from_post = any(model.startswith(x) for x in POST_DERIVED)
        cand = {
            'band': b,
            'source': 'post' if from_post else 'google',
            'from_excerpt': r.get('n') if from_post else None,
        }
        if best is None or (cand['source'] == 'post' and best['source'] == 'google'):
            best = cand
        if best['source'] == 'post':
            break
    return best


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
                'price_band': r.get('price_band'),
                'extractor_model': r.get('extractor_model'),
                'dead': r.get('dead'),
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
        raw = db.venue_evidence(con, venue_id)
    finally:
        if close:
            ctx.__exit__(None, None, None)

    venue_out = {'id': str(venue['id']), 'name': venue['name'], 'area': venue['area']}
    kept = with_live_citations([{'citations': raw}])
    # Ground the answer in evidence a reader can open. with_live_citations
    # orders live first but keeps dead rows, so the model could still quote a
    # post that no longer resolves -- and an /ask answer is a paraphrase, which
    # makes the post the only way to confirm it was not invented. Where a venue
    # has any live evidence, offer only that. Where it has none, offer what
    # there is: an honest quote behind a dead link beats refusing to answer.
    if kept:
        live_only = [c for c in kept[0]['citations'] if not c.get('dead')]
        if live_only:
            kept = [{'citations': live_only}]
    if not kept:
        return {
            'covered': False,
            'answer': 'No posts about this place have been collected yet.',
            'citations': [],
            'venue': venue_out,
        }
    rows = _shape(kept[0]['citations'])

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
    # The price block, when there is one. Without it every "how much" question got
    # "the posts do not cover the price" while the card beside it rendered a band.
    price = price_facts(rows)
    price_line = ''
    if price:
        where = f'excerpt {price["from_excerpt"]}' if price['source'] == 'post' else 'Google, not a post'
        price_line = f'\n\nprice: {BAND_WORDS[price["band"]]} (source: {price["source"]}, from {where})'
    payload = {
        'model': s.copilot_model,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {
                'role': 'user',
                'content': f'Restaurant: {venue["name"]}\nQuestion: {question}{price_line}\n\nExcerpts:\n{listing}',
            },
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
    kept = with_live_citations([{'citations': citations}]) if covered else []
    if covered and not kept:
        covered = False
        answer = answer or 'The posts do not cover that.'
        citations = []
    elif covered:
        citations = kept[0]['citations']

    return {'covered': covered, 'answer': answer, 'citations': citations, 'venue': venue_out}


def _cite(rows):
    """Built from database rows, never from model output."""
    return prefer_live(
        [
            {
                'post_url': r['post_url'],
                'excerpt': r['excerpt'],
                'platform': r['platform'],
                'author_handle': r['author_handle'],
                'posted_at': r['posted_at'],
                'dead': r.get('dead'),
            }
            for r in rows
        ]
    )


def json_dumps(x):
    return json.dumps(x, ensure_ascii=False)

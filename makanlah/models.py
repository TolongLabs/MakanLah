"""Model clients for the three jobs, split along the same seam as the runtimes.

  extract  batch, high volume, nobody waiting     -> DashScope (Qwen), Singapore
  embed    batch at ingestion, once per venue     -> DashScope text-embedding-v3
  rerank   interactive, a user is waiting          -> the low-latency lane

All three speak the OpenAI-compatible shape, so only the base URL, key and model
differ between them.
"""

import json
import re
import time
import urllib.error
import urllib.request

from makanlah import config

# DashScope rejects an embedding batch larger than 10 for text-embedding-v3 with
# a bare HTTP 400 and no explanatory body. This is correctness, not throughput.
EMBED_BATCH = 10

EXTRACT_SYSTEM = """You extract restaurant recommendations from social posts about Malaysian food.

Posts mix English, Malay and Chinese, often inside one sentence. Handle all three
identically. Never translate a name or a dish into English — record what the
writer wrote, in the script they wrote it in.

Return ONLY a JSON object: {"venues": [...]}. Each venue:
  name        the venue name exactly as written in the post
  aliases     other names for the SAME venue given in the post (e.g. the Chinese
              name alongside the Latin one). [] if none.
  area        neighbourhood/district if the post says one (Bangsar, SS15,
              Bukit Bintang, Damansara). null if not stated. Never guess.
  dishes      dishes named for this venue, as written. [] if none.
  sentiment   -1.0..1.0. The writer's attitude to THIS venue, not the post overall.
  price_band  1..4 if the post indicates price, else null.
  excerpt     a VERBATIM span copied from the post: the span where the writer
              says something ABOUT this venue -- what they ate, what it was
              like, why to go. Never paraphrase, never translate. This is shown
              to users as the evidence for the recommendation.
              A LOCATION LINE IS NOT AN EXCERPT. These posts open with a pin
              line ("📍店名：香港楼") and put the opinion underneath; take
              the opinion. Fall back to a location line ONLY if the post
              genuinely says nothing else about this venue.
  confidence  0.0..1.0 that this is a real, orderable venue.

Rules:
- A listicle naming nine restaurants yields nine venues.
- Skip cities, malls, and countries. A mall is only a venue if the post treats it
  as the place you eat at, not the place a restaurant is inside.
- If the post names no venue, return {"venues": []}. An empty result is correct
  and is better than an invented one.
- excerpt MUST be a substring of the post text."""

# The word "json" must appear literally: DashScope rejects response_format
# json_object without it, with InternalError.Algo.InvalidParameter. Because
# rerank() falls back to retrieval order on any error, the failure was silent --
# re-ranking simply never happened on that lane and the shortlist still looked
# plausible.
RERANK_SYSTEM = """You re-rank candidate restaurants against what a user asked for.

You are given the user's request and numbered candidates, each with its name,
area, dishes and excerpts from real posts. Return ONLY a json object:
  {"results": [{"index": <candidate number>, "why": "<at most 12 words>"}]}

Order best first. Include at most the number asked for; fewer is fine.

"why" is one line in a list someone is skimming while hungry. Twelve words is a
ceiling, not a target. No preamble, no restating the request.

  - "why" must be grounded in the candidate's own excerpts and dishes. Never
    invent a detail that is not there.
  - NEVER output a URL, a link, or a citation. Those are attached from the
    database afterwards. A model asked for a URL produces a plausible one.
  - Judge fit to the request, not general fame.
  - The request may be in English, Malay or Chinese. Treat all three alike.
  - WRITE "why" IN THE SAME LANGUAGE THE REQUEST WAS WRITTEN IN. An English
    question gets an English answer even when every excerpt is Chinese. Venue
    names and dish names stay in their original script and are never translated.
  - Two entries for the same restaurant is a bug. If two candidates are the same
    place written differently, keep only the better-evidenced one."""


def _post(url, payload, key, timeout=120):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _content(body):
    """GLM and some others return empty choices on failure; a harness reading only
    the content field records that as a success (docs/SWARM.md section 7)."""
    if body.get('error'):
        raise RuntimeError(f'api error: {body["error"]}')
    choices = body.get('choices') or []
    if not choices:
        raise RuntimeError(f'empty choices: {str(body)[:200]}')
    return choices[0].get('message', {}).get('content') or ''


def _json_object(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        raise RuntimeError('no JSON object in response')
    return json.loads(m.group(0))


def extract(post_text, retries=2):
    s = config.settings()
    if not s.extract_api_key:
        raise RuntimeError('no extraction key configured')
    payload = {
        'model': s.extract_model,
        'messages': [{'role': 'system', 'content': EXTRACT_SYSTEM}, {'role': 'user', 'content': post_text}],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    last = None
    for _ in range(retries + 1):
        try:
            body = _post(f'{s.extract_base_url}/chat/completions', payload, s.extract_api_key)
            return _json_object(_content(body)).get('venues', []), s.extract_model
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}: {e.read()[:200].decode(errors="replace")}'
        except Exception as e:
            last = str(e)[:200]
    raise RuntimeError(f'extraction failed: {last}')


def embed(texts):
    s = config.settings()
    if not s.embed_api_key:
        raise RuntimeError('no embedding key configured')
    out = []
    for i in range(0, len(texts), EMBED_BATCH):
        body = _post(
            f'{s.embed_base_url}/embeddings',
            {'model': s.embed_model, 'input': texts[i : i + EMBED_BATCH], 'encoding_format': 'float'},
            s.embed_api_key,
        )
        out.extend(d['embedding'] for d in sorted(body['data'], key=lambda d: d['index']))
    return out


CJK_RE = re.compile(r'[\u4e00-\u9fff]')
# Function words and words with no English reading. Deliberately excludes
# "best" (English too), "jalan" (appears in English text as a street name) and
# dish words like "nasi" and "ayam", which English speakers in KL use verbatim.
# Misrouting an English question to Malay is worse than missing a Malay one:
# the fallback is English, which every user here can read.
MS_RE = re.compile(
    r'\b(yang|nak|mana|dekat|paling|murah|sedap|enak|kedai|makan|sini|boleh|tempat|cari|berdekatan)\b', re.I
)


def answer_language(query):
    """Which language the user asked in, so the answer comes back in it.

    Chinese first: a query with any CJK is a Chinese query even when it also
    contains a Latin venue name, which is the normal case here.
    """
    if CJK_RE.search(query or ''):
        return 'Chinese'
    if MS_RE.search(query or ''):
        return 'Malay'
    return 'English'


# How much of the retrieved set the re-rank actually sees. Measured: 48
# candidates with three long excerpts each took 9.0s, which misses the 3s target
# in docs/PRD.md by a factor of three. The re-rank is 96% of request latency and
# scales with prompt size, so this is the knob that matters.
RERANK_CANDIDATES = 16
RERANK_EXCERPT_CHARS = 260
RERANK_EXCERPTS_PER_VENUE = 2


def rerank(query, candidates, limit=10, retries=1):
    """Returns [(candidate_index, why)]. Never returns a citation: stage 4 attaches those."""
    s = config.settings()
    if not s.rerank_api_key:
        return [(i, '') for i in range(min(limit, len(candidates)))]
    candidates = candidates[:RERANK_CANDIDATES]
    lines = []
    for i, c in enumerate(candidates):
        dishes = ', '.join((c.get('dishes') or [])[:4]) or '-'
        excerpts = ' / '.join(
            x['excerpt'] for x in c.get('citations', [])[:RERANK_EXCERPTS_PER_VENUE] if x.get('excerpt')
        )[:RERANK_EXCERPT_CHARS]
        lines.append(
            f'[{i}] {c["name"]} - {c.get("area") or c.get("city") or ""}\n'
            f'    dishes: {dishes}\n    posts: {excerpts or "-"}'
        )
    # Naming the language in the system prompt is not enough: the model anchors on
    # the language of the excerpts, so an English question came back answered in
    # Chinese because every cited post was Chinese. Detecting it here and stating
    # it as an instruction makes it deterministic.
    want = answer_language(query)
    payload = {
        'model': s.rerank_model,
        'messages': [
            {'role': 'system', 'content': RERANK_SYSTEM},
            {
                'role': 'user',
                'content': (
                    f'Request: {query}\n'
                    f'Write every "why" in {want}. The excerpts below may be in another '
                    f'language; that does not change the language you answer in.\n'
                    f'Return at most {limit}.\n\n' + '\n'.join(lines)
                ),
            },
        ],
        'temperature': 0.2,
        'response_format': {'type': 'json_object'},
    }
    # Only sent when it is being turned OFF: a model with no thinking mode rejects
    # the field outright, and the default for every non-qwen3 lane is already off.
    if not s.rerank_thinking:
        payload['enable_thinking'] = False
    deadline = time.monotonic() + s.rerank_timeout
    for _ in range(retries + 1):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        try:
            body = _post(f'{s.rerank_base_url}/chat/completions', payload, s.rerank_api_key, timeout=left)
            got = _json_object(_content(body)).get('results', [])
            picked = []
            for r in got:
                idx = r.get('index')
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    picked.append((idx, str(r.get('why') or '')[:200]))
            if picked:
                return picked[:limit]
        except Exception:
            # The budget covers the retry too. Retrying against a fresh full
            # timeout is how a "4 second" bound becomes eight.
            continue
    # Re-ranking is an enhancement, not a gate. Retrieval order is a valid answer.
    return [(i, '') for i in range(min(limit, len(candidates)))]


def repair_excerpt(excerpt, name, aliases, post_text, window=220):
    """An excerpt that is not a substring of the post is a fabricated quote.

    Measured in the spike: the extractor stitched non-contiguous lines into text
    that read correctly and was not in the post. Returns (excerpt, origin).
    """
    if excerpt and excerpt in post_text:
        return excerpt, 'model'
    for needle in [name, *(aliases or [])]:
        if not needle:
            continue
        i = post_text.find(needle)
        if i < 0:
            continue
        start = post_text.rfind('\n', 0, i) + 1
        return post_text[start : start + window].strip(), 'repaired'
    return None, 'dropped'

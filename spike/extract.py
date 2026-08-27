"""Post text -> structured venue mentions.

One prompt for all three languages. A per-language path would silently bias the
corpus toward whichever language the pipeline handles best, which is risk #3 in
docs/PRODUCT.md and looks like success from the outside.

Lane order: DashScope (Qwen, Singapore) if a key exists, else Qwen via
OpenRouter. Both are OpenAI-compatible, so only the base URL and model change.
"""

import json
import os
import re
import urllib.error
import urllib.request

import env

env.load()

SYSTEM = """You extract restaurant recommendations from social posts about Malaysian food.

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
  excerpt     a VERBATIM span copied from the post, the span the extraction came
              from. Never paraphrase, never translate. This is shown to users.
  confidence  0.0..1.0 that this is a real, orderable venue.

Rules:
- A listicle naming nine restaurants yields nine venues.
- Skip cities, malls, and countries. A mall is only a venue if the post treats it
  as the place you eat at, not the place a restaurant is inside.
- If the post names no venue, return {"venues": []}. An empty result is correct
  and is better than an invented one.
- excerpt MUST be a substring of the post text."""


def _lane():
    if os.environ.get('DASHSCOPE_API_KEY'):
        return (
            'dashscope',
            os.environ.get('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'),
            os.environ['DASHSCOPE_API_KEY'],
            os.environ.get('DASHSCOPE_MODEL_EXTRACT', 'qwen-plus'),
        )
    if os.environ.get('OPENROUTER_API_KEY'):
        return (
            'openrouter',
            'https://openrouter.ai/api/v1',
            os.environ['OPENROUTER_API_KEY'],
            os.environ.get('OPENROUTER_MODEL_EXTRACT', 'qwen/qwen3-235b-a22b-2507'),
        )
    return (None, None, None, None)


def lane_name():
    lane, _, _, model = _lane()
    return f'{lane}:{model}' if lane else 'none'


def _post_json(url, payload, key, timeout=120):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _parse(content):
    """GLM and friends return empty choices on failure; a bare .content read
    records that as success. Parse defensively (docs/SWARM.md section 7)."""
    if not content:
        return None
    m = re.search(r'\{.*\}', content, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def extract(post_text, retries=2):
    lane, base, key, model = _lane()
    if not lane:
        raise RuntimeError('no extraction lane: set DASHSCOPE_API_KEY or OPENROUTER_API_KEY')
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': post_text}],
        'temperature': 0.1,
        'response_format': {'type': 'json_object'},
    }
    last = None
    for _ in range(retries + 1):
        try:
            body = _post_json(f'{base}/chat/completions', payload, key)
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}: {e.read()[:300].decode(errors="replace")}'
            continue
        except Exception as e:
            last = str(e)
            continue
        if body.get('error'):
            last = f'api error: {body["error"]}'
            continue
        choices = body.get('choices') or []
        if not choices:
            last = f'empty choices: {str(body)[:300]}'
            continue
        parsed = _parse(choices[0].get('message', {}).get('content'))
        if parsed is None:
            last = 'unparseable content'
            continue
        return parsed.get('venues', []), model
    raise RuntimeError(f'extraction failed after retries: {last}')


def repair_excerpt(excerpt, name, aliases, post_text, window=220):
    """An excerpt that is not a substring of the post is a fabricated quote.

    Observed in the spike: the model stitches non-contiguous lines (dropping an
    opening-hours line) into one excerpt. That reads fine and is not what the
    writer wrote, so it can never reach the UI. Recover a real contiguous span
    anchored on the venue name; if even that fails, return None and let the
    citation fall back to the post link.
    """
    if excerpt and excerpt in post_text:
        return excerpt, False
    for needle in [name, *(aliases or [])]:
        if not needle:
            continue
        i = post_text.find(needle)
        if i < 0:
            continue
        start = post_text.rfind('\n', 0, i) + 1
        return post_text[start : start + window].strip(), True
    return None, True

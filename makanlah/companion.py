"""The companion's voice: one short spoken line per onboarding step.

**This is decoration and it is allowed to be.** Every other model lane in this
project is bound to the citation trail; this one is bound the opposite way. The
companion never names a venue, never claims anything about food, and never sees
a corpus row. It is told the step and the labels the user just tapped, nothing
else, so there is no evidence for it to get wrong. That is what makes it safe to
let a model write it at all.

Which is also why `_safe()` exists below. A model asked to be cute will
occasionally recommend a restaurant anyway, and a spoken sentence naming a place
with no post behind it is precisely the hallucination-with-a-rating that
docs/PRODUCT.md forbids. Anything that looks like a claim is dropped and the
scripted line is spoken instead.

The scripted lines are not a degraded mode. They are the product; the model is a
variation on top. With no key, no quota or no network the wizard still talks.
"""

import random
import re

from makanlah import config, models

# The four wizard steps, keyed as the client keys them.
STEPS = ('craving', 'company', 'range', 'mood')

# Spoken by a browser speech synthesiser, so: English, short, no CJK, no
# punctuation that a synthesiser reads aloud as a word. A Malay word a Malaysian
# speech voice will pronounce sensibly is fine and is the whole point of the
# register; a Chinese glyph in an English voice is not, and gets skipped or
# spelled out.
SCRIPT: dict[str, tuple[str, ...]] = {
    'craving': (
        'Okay, tell me. What are you craving right now?',
        'Hungry already? Pick whatever sounds good, as many as you like.',
        'So, what are we eating today? Go on, pick a few.',
    ),
    'company': (
        'Nice choice! Now, who is eating with you?',
        'Ooh, good pick. Is anyone coming along?',
        'Lovely. Are you going alone, or bringing people?',
    ),
    'range': (
        'How far would you go for this? Be honest.',
        'Walking distance, or are we driving?',
        'Okay, how far are you willing to travel?',
    ),
    'mood': (
        'Last one, I promise. What kind of meal are you after?',
        'Almost done! Comfort food, or something new?',
        'One more. What sort of meal are we in the mood for?',
    ),
    'done': (
        'Got it. Let me go and read what people actually wrote.',
        'Perfect. Finding you somebody who has already eaten there.',
        'On it. Every pick comes with the post behind it, promise.',
    ),
}

SYSTEM = """You are the voice of a small, cheerful cartoon companion in a Malaysian
restaurant app. You are asking the user one onboarding question out loud.

Write ONE spoken sentence, at most 16 words, warm and a little playful.

Hard rules:
  - NEVER name a restaurant, a place, a street, an area or a brand.
  - NEVER recommend, rate or describe any food as good, best, famous or worth trying.
  - NEVER state a fact, a price, a distance or an opening time.
  - No emoji, no hashtags, no URLs, no quotation marks, no stage directions.
  - Plain English. A single common Malay word such as makan or lah is welcome.
    No Chinese characters: this is read aloud by an English speech voice.

You are making conversation while the user answers a form. That is all."""

_PROMPT = {
    'craving': 'Ask what the user feels like eating. Use the word craving or hungry.',
    'company': 'Ask WHO the user is eating with -- alone, a partner, family, friends. Do not mention food.',
    'range': 'Ask HOW FAR the user will travel -- walking, driving, across town. Do not mention food.',
    'mood': (
        'Ask what KIND of meal they want: something familiar and comforting, or something new. '
        'Do not ask what they are craving, that was the first question.'
    ),
    'done': 'Say you are going off to read what people wrote. Do not ask a question.',
}

MAX_WORDS = 18
MAX_CHARS = 120

# A model told not to recommend still sometimes recommends. Each of these means
# the line has drifted from small talk into a claim, and a claim with no post
# behind it is the one thing this product does not ship.
_BANNED = re.compile(
    r'https?://|www\.'  # a URL
    r'|[一-鿿぀-ヿ]'  # CJK, which the speech voice cannot read
    r'|\b(?:rm|myr)\s*\d'  # a price
    r'|\b(?:best|famous|must[- ]try|highly rated|top rated|recommend\w*|delicious|authentic)\b'
    r'|\b(?:jalan|lorong|taman|bukit|kampung)\b',  # a street or area name
    re.I,
)


def _safe(text: str) -> str | None:
    """Return the line if it is small talk, or None if it has become a claim."""
    line = ' '.join((text or '').split()).strip().strip('"').strip("'")
    if not line or len(line) > MAX_CHARS or len(line.split()) > MAX_WORDS:
        return None
    if _BANNED.search(line):
        return None
    return line


def scripted(step: str, seed: int | None = None) -> str:
    """The line that is always available. Deterministic when given a seed."""
    pool = SCRIPT.get(step) or SCRIPT['craving']
    if seed is None:
        return random.choice(pool)
    return pool[seed % len(pool)]


def line(step: str, picked: list[str] | None = None, *, seed: int | None = None) -> dict:
    """One spoken line for one step.

    Returns `{'text', 'source'}` where source is 'model' or 'script'. The caller
    renders both identically; the field exists so a failure is visible in logs
    and in a test rather than silently indistinguishable from a success.
    """
    if step not in _PROMPT:
        step = 'craving'
    fallback = {'text': scripted(step, seed), 'source': 'script'}

    s = config.settings()
    if not s.companion_api_key:
        return fallback

    # Only the user's own tapped labels are sent, capped, and never corpus text.
    context = ', '.join(str(p)[:60] for p in (picked or [])[:6])
    ask = _PROMPT[step]
    if context:
        ask = f'{ask} They have just chosen: {context}. You may react to that in half a clause, warmly.'

    payload = {
        'model': s.companion_model,
        'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': ask}],
        'temperature': 1.0,
        'max_tokens': 60,
    }
    try:
        body = models._post(
            f'{s.companion_base_url}/chat/completions',
            payload,
            s.companion_api_key,
            timeout=s.companion_timeout,
        )
        got = _safe(models._content(body))
    except Exception:
        return fallback
    if got is None:
        return fallback
    return {'text': got, 'source': 'model'}

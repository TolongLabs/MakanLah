"""What makes a span of a post worth showing as testimony.

Shared by the extraction repair path and the backfill that strips pin lines, so
"is this an excerpt or a location" has one definition rather than two that drift.

The corpus makes the case. RedNote posts are listicles -- a pin line, then the
opinion -- and excerpts there average 55.9 characters against Google Maps' 196.8,
with 103 of 317 address-shaped against 5 of 1388 (#25).
"""

import re

# A line that locates rather than argues: a pin, a listicle number heading its
# own line, or a street/postcode line.
PIN_LINE = re.compile(r'^\s*(📍|\d+\s*[.、]\s*\S|No\.?\s*\d)|^\s*\S.*\b\d{5}\b')

# Everything a post carries that is not somebody's opinion. Pin lines are one
# kind; a row of hashtags and an opening-hours line are the same thing wearing
# different clothes, and the repair path surfaced both the moment pin lines
# stopped winning. Chrome is not testimony no matter which shape it arrives in.
HASHTAGS_ONLY = re.compile(r'^\s*(#\S+\s*)+$')
HOURS_ONLY = re.compile(
    r'^\s*[⏰🕙🕐]?\s*\d{1,2}\s*[:.]?\d{0,2}\s*(am|pm)?\s*[-–~]\s*\d{1,2}\s*[:.]?\d{0,2}\s*(am|pm)?\s*$', re.I
)


def is_chrome(line):
    """A line that locates, tags or schedules, rather than saying anything."""
    if not line.strip():
        return True
    return bool(PIN_LINE.match(line) or HASHTAGS_ONLY.match(line) or HOURS_ONLY.match(line))


# What must survive for a strip to be worth doing, and the floor for a fragment
# to count as testimony.
#
# Weighted, not counted. A CJK character carries roughly a word, so 30 of them is
# a paragraph while 30 Latin characters is half a sentence -- a plain len() sets
# a bar Chinese testimony clears trivially and English testimony cannot, which is
# the silent language bias AGENTS.md warns about.
MIN_REMAINDER = 30

# A far lower bar than MIN_REMAINDER, because it answers a different question.
# MIN_REMAINDER asks whether enough survives to be worth rewriting a stored
# excerpt. This asks whether a span says anything at all, and in Chinese six
# characters can be a whole verdict -- 椰浆饭天花板, "the nasi lemak ceiling".
MIN_TESTIMONY = 12
CJK = re.compile(r'[　-〿㐀-䶿一-鿿豈-﫿＀-￯]')


def weight(text):
    return len(text) + sum(1 for ch in text if CJK.match(ch))


def strip_pins(excerpt):
    """The excerpt with leading locating lines removed, or None to leave it alone."""
    if not excerpt:
        return None
    lines = excerpt.split('\n')
    i = 0
    while i < len(lines) and (not lines[i].strip() or PIN_LINE.match(lines[i])):
        i += 1
    if i == 0:
        return None
    rest = '\n'.join(lines[i:]).strip()
    if weight(rest) < MIN_REMAINDER:
        return None
    return rest


def argues(text, names=()):
    """Does this span say something, or is it only chrome?

    `names` are the venue's own name and aliases. A line that is nothing but the
    name is a label, not a verdict -- and because the repair path anchors on the
    name, that line is always the first one in view.
    """
    if not text:
        return False
    labels = {n.strip().casefold() for n in names if n and n.strip()}
    said = [ln for ln in text.split('\n') if not is_chrome(ln) and ln.strip().casefold() not in labels]
    return bool(said) and weight('\n'.join(said)) >= MIN_TESTIMONY

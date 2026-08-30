"""Per-person price bands read out of post text.

Bands follow Google Maps' four levels, per person in RM: 1 = under 15, 2 = 15-40, 3 = 40-100, 4 = above 100.
The hard constraint is honesty, not coverage: a post that names no figure yields None, never a guess from
cuisine, area or tone. A number is only money when a currency marker (RM, 马币, 令吉, 块, 人均) is attached
to it, so clock times, durations, ratings, review counts and street numbers never become prices.
"""

import re

_NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
_HAN = r'[零一二两三四五六七八九十百千]+'
_SEP = r'\s*(?:-|–|—|~|～|到|to)\s*'

# 'rm' must not sit inside a word -- 'warm 80' is not RM80 -- so the lookbehind rejects a preceding letter.
_MARK = r'(?<![a-z])(?:rm|马币|令吉|人均)\s*'

# 'RM20-30' takes its midpoint; the second figure may or may not carry its own marker.
_RANGE = re.compile(_MARK + '(' + _NUM + ')' + _SEP + r'(?:rm|马币|令吉|人均)?\s*(' + _NUM + ')', re.IGNORECASE)
# The marker can also trail the range: '80-100块'.
_RANGE_TAIL = re.compile('(' + _NUM + ')' + _SEP + '(' + _NUM + r')\s*(?:令吉|块)')

_SINGLE = re.compile(
    r'(?<![a-z])rm\s*(' + _NUM + r')'
    r'|马币\s*(' + _NUM + '|' + _HAN + r')'
    r'|(' + _NUM + '|' + _HAN + r')\s*令吉'
    r'|(' + _NUM + '|' + _HAN + r')\s*块'
    r'|人均\s*(' + _NUM + '|' + _HAN + ')',
    re.IGNORECASE,
)

_HAN_HEAD = '零一二两三四五六七八九十百千'
_HAN_DIGITS = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
_HAN_UNITS = {'十': 10, '百': 100, '千': 1000}


def _han_to_value(text):
    total, current = 0, 0
    for ch in text:
        if ch in _HAN_DIGITS:
            current = _HAN_DIGITS[ch]
        else:
            total += max(current, 1) * _HAN_UNITS[ch]
            current = 0
    return total + current


def _to_value(raw):
    if raw[0] in _HAN_HEAD:
        return float(_han_to_value(raw))
    return float(raw.replace(',', ''))


# 100 lands in band 4 because the range test pins the RM80-120 midpoint (100) to 4; band 3 is [40, 100).
def _band(value):
    if value < 15:
        return 1
    if value < 40:
        return 2
    if value < 100:
        return 3
    return 4


def price_band_from_text(text):
    """Read the per-person RM band a post states, or None when it states none.

    A range takes its midpoint. Several separate figures average into one band.
    """
    if not isinstance(text, str):
        return None
    ranges = [m for m in (_RANGE.search(text), _RANGE_TAIL.search(text)) if m]
    if ranges:
        first = min(ranges, key=lambda m: m.start())
        low, high = (_to_value(g) for g in first.groups())
        return _band((low + high) / 2)
    values = [_to_value(next(g for g in m.groups() if g is not None)) for m in _SINGLE.finditer(text)]
    if not values:
        return None
    return _band(sum(values) / len(values))

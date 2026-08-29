"""Dish aliases across EN / MS / ZH.

The corpus stores whatever the post said, so one dish arrives as `nasi lemak`,
`Nasi Lemak` and `椰浆饭` -- three rows, one dish. An embedding blurs these
together with every other Malaysian dish; an exact match on the wrong casing
misses them entirely. Grouping them is what makes a lexical lane possible.

Kept deliberately small and hand-checked. Used by evals/ as ground truth and by
rank.py as the lexical lane.

The lane earned its place by measurement, not argument. `curry mee` scored p@5
0.00: 何九茶室 carries 咖喱干拌面 and never surfaced, while the vector lane
returned 东京咖喱油拌面 -- Tokyo curry oil noodles, which is curry and noodles
but is not the Malaysian dish. An exact tag match finds the first; no embedding
distinguishes the second.
"""

import difflib
import unicodedata

DISH_ALIASES = {
    'bak kut teh': ['bak kut teh', 'bakuteh', 'bkt', '肉骨茶', 'sup tulang babi'],
    'nasi lemak': ['nasi lemak', '椰浆饭', '椰漿飯', 'coconut rice'],
    'char kway teow': ['char kway teow', 'char koay teow', 'ckt', '炒粿条', '炒粿條', '炒河粉'],
    'kaya toast': ['kaya toast', '咖央多士', '咖椰吐司', 'roti bakar kaya'],
    'laksa': ['laksa', '叻沙', 'curry laksa', 'asam laksa', '咖喱叻沙'],
    'dim sum': ['dim sum', '点心', '點心'],
    'roti canai': ['roti canai', 'roti canai', '印度煎饼', 'roti prata'],
    'satay': ['satay', 'sate', '沙爹'],
    'chicken rice': ['chicken rice', 'hainanese chicken rice', '鸡饭', '海南鸡饭', 'nasi ayam'],
    'pasta': ['pasta', 'carbonara', 'aglio olio', 'spaghetti', '意面', '意大利面'],
    'tiramisu': ['tiramisu', '提拉米苏'],
    'matcha': ['matcha', '抹茶', 'matcha latte'],
    'pizza': ['pizza', '披萨', '比萨'],
    'steak': ['steak', '牛排', '西冷牛排'],
    'curry mee': ['curry mee', '咖喱面', '咖喱面条', '咖喱干拌面'],
    # Both added from #85's measurements rather than from imagination. The corpus
    # tags 叉烧杨家家来 with 叉烧 and Oh Yeah Kopitiam with `Char Siew`, and nothing
    # joined them; `egg tart` found nothing while 蛋挞 found two venues.
    #
    # Deliberately no `bbq pork` or `roast pork` here. `canonical()` matches on
    # substring in BOTH directions, so a short form swallows every string that
    # contains it -- `pork` alone would fold `roast pork`, `pork noodles` and
    # `braised pork rice` into char siew. Short forms are a trap in this table.
    'char siew': ['char siew', 'char siu', 'charsiew', '叉烧', '叉燒'],
    'egg tart': ['egg tart', 'portuguese egg tart', '蛋挞', '蛋撻', '葡挞'],
}

# Cuisines that never overlap. A venue tagged only from one group is a
# high-confidence negative for a query from another.
WESTERN = {'pasta', 'tiramisu', 'pizza', 'steak', 'matcha'}
MALAYSIAN = {'bak kut teh', 'nasi lemak', 'char kway teow', 'kaya toast', 'laksa', 'roti canai', 'satay', 'curry mee'}


def canonical(dish):
    """Map a raw corpus dish string onto a canonical key, or None."""
    d = (dish or '').strip().lower()
    if not d:
        return None
    for key, forms in DISH_ALIASES.items():
        for f in forms:
            if f in d or d in f:
                return key
    return None


def match_forms(dish_key):
    """Every stored form of a canonical dish, for a lexical lookup."""
    return DISH_ALIASES.get(dish_key, [])


def canonical_for_query(query):
    """The dish a query is asking for, or None.

    Whole-query only: `bak kut teh` resolves, `somewhere nice for dinner` does
    not, and neither does a sentence that merely mentions a dish in passing.
    A vague query must stay on the semantic lane, which is what it is for.
    """
    q = (query or '').strip().lower()
    if not q or len(q) > 40:
        return None
    for key, forms in DISH_ALIASES.items():
        if q == key or q in [f.lower() for f in forms]:
            return key
    return None


def fold(dish):
    """One spelling key. NFKC so a full-width copy folds onto its ASCII twin."""
    return unicodedata.normalize('NFKC', dish or '').casefold().strip()


# Measured against the 810-key corpus vocabulary. At 0.80, `halal food` matches
# `local food`, which is a lexical lane firing on a query about religious dietary
# law and answering it with somebody's word for cheap. At 0.85 that goes and every
# wanted case survives: `cha siew` -> `char siew`, `nasi lemat` -> `nasi lemak`.
NEAR = 0.85

# Below this, a near match is noise. `pork` and `rice` are in the vocabulary and
# resolve exactly; it is three-letter fragments that should not be guessed at.
MIN_NEAR_LEN = 4


def named_in(query, vocabulary):
    """Which stored dish strings a query names: `(folded_keys, label)`.

    The hand table in this module knows fifteen dishes. The corpus carries 838
    distinct dish strings, so `canonical_for_query` alone recognised **12.3% of
    them and 18.1% of dish-mentions, and none of the ten mixed-script strings**.
    `蛋挞` is written about by two venues and was invisible to the lexical lane;
    so were `char siew` (6 venues), `coffee` (7) and `ayam gepuk` (4).

    So the vocabulary is the corpus, and DISH_ALIASES keeps the one job it is
    actually good at -- grouping `肉骨茶` with `bak kut teh` across languages,
    which no amount of string folding will ever do.

    Three lanes, and the result is their UNION rather than the first that hits:

    1. **The alias table**, so a query in one language reaches venues tagged in
       another
    2. **An exact fold**, which is the 8x
    3. **A near match**, for the corpus's own spelling -- `cha seiw`, `rosated
       chicken` and `buratta` are all real rows, and so is `noodle` beside
       `noodles`

    The union rather than a first-hit is measured, not assumed. Across the whole
    810-key vocabulary there are **29 near-pairs at 0.85, no key has more than two
    neighbours, and every pair is the same dish twice**: plurals (`taco`/`tacos`),
    spellings (`chili`/`chilli`), phrasing (`fish & seafood` / `fish and seafood`)
    and Han variants (`干肉骨茶`/`肉骨茶`). There were no false pairs to trade
    against, so stopping at the first lane only lost venues.

    Whole-query only, as before. `something not too heavy` names no dish and
    matches nothing in any lane at any cutoff, which is what keeps a mood query on
    the semantic lane where it belongs.
    """
    q = fold(query)
    if not q or len(q) > 40:
        return frozenset(), None

    found: set[str] = set()
    label = None

    key = canonical_for_query(query)
    if key:
        found |= {v for v in vocabulary if canonical(v) == key}
        if found:
            label = key

    if q in vocabulary:
        found.add(q)
        label = label or q

    if len(q) >= MIN_NEAR_LEN:
        near = difflib.get_close_matches(q, list(vocabulary), n=3, cutoff=NEAR)
        found |= set(near)
        if near:
            label = label or near[0]

    return frozenset(found), label

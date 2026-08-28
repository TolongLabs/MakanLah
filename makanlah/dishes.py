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

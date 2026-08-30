"""What the taste wizard asked for, and what the ranker can honestly do with it.

The wizard collects five answers and the page says "Filtered by your answers"
naming all five. Two of them -- craving and range -- were always real: they become
the query string and `radius_m`. The other three reached an API model that had no
field for them, so Pydantic dropped them silently and the sentence was false for
three fifths of what it named (#170).

Naming a filter that did not run is the same defect as inferring halal from a
venue name: a claim the evidence does not support. So this module answers two
questions separately -- what can shape the ranking, and what may be CLAIMED to
have shaped it -- because a preference that changed nothing must never be claimed.
"""

# Closed vocabularies. An unrecognised value is dropped rather than passed
# through: a client updated ahead of the API would otherwise put arbitrary text
# into a model prompt, and `prefs` arrives from the browser.
MOODS = {
    'adventurous': 'somewhere adventurous, unusual or worth a detour',
    'comfort': 'somewhere comforting and familiar',
}
COMPANY = {
    'solo': 'eating alone, so counter seating and a quick single portion suit',
    'couple': 'a meal for two',
    'family': 'a family meal, so shareable dishes and room for children matter',
    'group': 'a larger group, so shareable dishes and big tables matter',
}
BUDGETS = {'cheap': (1, 2), 'mid': (2, 3), 'splurge': (3, 4)}


def _clean(prefs):
    return prefs if isinstance(prefs, dict) else {}


def preference_hint(prefs):
    """One sentence for the re-rank, or ''. Never the raw value from the client."""
    p = _clean(prefs)
    parts = [COMPANY.get(p.get('company')), MOODS.get(p.get('mood'))]
    parts = [x for x in parts if x]
    if not parts:
        return ''
    return 'The person is looking for ' + ', and '.join(parts) + '.'


def applied_names(prefs, price_coverage=0):
    """Which preferences actually shaped this response, for the client to name.

    `craving` and `range_m` are excluded deliberately: they are already the query
    and the radius, so naming them here would count one filter twice.

    `budget` is named only when the corpus can act on it. 0 of 121 reachable
    venues carried a price when #170 was filed, so a budget filter would either
    empty the results or change nothing -- and claiming it filtered is false in
    both cases.
    """
    p = _clean(prefs)
    out = []
    if p.get('company') in COMPANY:
        out.append('company')
    if p.get('mood') in MOODS:
        out.append('mood')
    if p.get('budget') in BUDGETS and price_coverage > 0:
        out.append('budget')
    return sorted(out)


def budget_bands(prefs):
    """The price bands a budget answer permits, or None when it cannot be applied."""
    return BUDGETS.get(_clean(prefs).get('budget'))


def within_budget(venue, prefs):
    """Whether a candidate survives the budget answer.

    An unpriced venue always survives. 82% of the corpus carries no price, and
    silence about cost is not evidence of expense -- excluding those would answer
    a budget question with a near-empty page and call it a filter.
    """
    bands = budget_bands(prefs)
    if not bands:
        return True
    b = venue.get('price_band') if isinstance(venue, dict) else None
    if not isinstance(b, int) or isinstance(b, bool):
        return True
    return bands[0] <= b <= bands[1]

"""The four ranking stages from docs/TRD.md. Only stage 3 calls a model.

  filter    distance, budget, cuisine -> candidate venues     SQL, cheap
  retrieve  pgvector cosine -> top ~50                        one index scan
  re-rank   model sees query + summaries + excerpts -> top 10 one call
  attach    join citations back on, from the database         SQL

Filter runs before retrieve. A vector search over every KL venue then filtered by
distance wastes the index and returns a great match forty minutes away.
"""

import math

from makanlah import config, db, models
from makanlah.dishes import canonical, canonical_for_query
from makanlah.text import fold_variants, normalize


def _distance_m(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)))


def _format_distance(d):
    if d < 1000:
        return f'{d} m away'
    return f'{d / 1000:.1f} km away'


def disambiguate(entries):
    """Label or flag results whose names collide under fold_variants.

    A label is only ever taken from data the corpus holds: area, or a formatted
    distance when area is missing. If no usable differentiator exists, the pair
    is flagged as ambiguous rather than invented.
    """
    groups = {}
    for e in entries:
        key = fold_variants(e['venue']['name'])
        groups.setdefault(key, []).append(e)

    for group in groups.values():
        if len(group) < 2:
            for e in group:
                e['venue']['disambiguator'] = None
            continue

        candidates = []
        for e in group:
            area = e['venue'].get('area')
            if area:
                candidates.append(area)
            elif e.get('distance_m') is not None:
                candidates.append(_format_distance(e['distance_m']))
            else:
                candidates.append(None)

        if None in candidates or len(set(candidates)) != len(candidates):
            for e in group:
                e['venue']['disambiguator'] = None
                e['venue']['ambiguous_with_sibling'] = True
        else:
            for e, label in zip(group, candidates, strict=True):
                e['venue']['disambiguator'] = label
                e['venue']['ambiguous_with_sibling'] = False

    return entries


def dedupe(candidates):
    """Collapse near-duplicate venues at presentation time, not in the corpus.

    "Village Park" and "Village Park Nasi Lemak" are one restaurant written two
    ways, and both reaching a shortlist wastes a slot and reads like a bug. This
    is deliberately NOT a corpus merge: docs/TRD.md keeps ambiguity as separate
    rows because merging later is safe and a wrong merge is not recoverable.
    Collapsing for one response is reversible by definition.

    Containment only — "Village Park" inside "Village Park Nasi Lemak". Two names
    that merely share a word are left alone.

    Matching folds Han script variants, because normalize() cannot see that 强记炖汤
    and 強记炖汤 are the same three characters and so left one shop on the shortlist
    twice (#59).

    **A distinct place_id outranks any name match.** Measured on the live corpus:
    of six groups that fold to one name, 兴记肉骨茶 has two place_ids 914m apart and
    华阳 has two 11,970m apart — Oriental Kopi is a chain, not one kopitiam. Those
    are different businesses and collapsing them would hide one of them. Only rows
    with nothing contradicting the name match are folded together.
    """
    kept = []
    for c in candidates:
        norm = fold_variants(c['name'])
        if not norm:
            continue
        dup_of = None
        for i, k in enumerate(kept):
            kn = fold_variants(k['name'])
            if not (norm == kn or norm.startswith(kn + ' ') or kn.startswith(norm + ' ')):
                continue
            a, b = k.get('place_id'), c.get('place_id')
            if a and b and a != b:
                continue
            dup_of = i
            break
        if dup_of is None:
            kept.append(c)
            continue
        # Keep whichever carries more evidence; fold the other's citations in.
        winner, loser = kept[dup_of], c
        if len(loser['citations']) > len(winner['citations']):
            winner, loser = loser, winner
        seen = {x['post_url'] for x in winner['citations']}
        winner['citations'].extend(x for x in loser['citations'] if x['post_url'] not in seen)
        for d in loser.get('dishes', []):
            if d not in winner['dishes']:
                winner['dishes'].append(d)
        kept[dup_of] = winner
    return kept


def maps_url(venue):
    """Built server-side. No maps SDK, no key, no billing.

    With a place_id it disambiguates a chain with twenty branches.
    """
    from urllib.parse import quote

    q = quote(f'{venue["name"]} {venue.get("area") or ""} {venue.get("city") or "Kuala Lumpur"}'.strip())
    if venue.get('place_id'):
        return f'https://www.google.com/maps/search/?api=1&query={q}&query_place_id={venue["place_id"]}'
    return f'https://www.google.com/maps/search/?api=1&query={q}'


def recommend(query, *, lat=None, lng=None, radius_m=None, limit=10, retrieve_k=50):
    s = config.settings()
    with db.connect() as con:
        degraded, _, reasons = db.source_health(con)
        candidate_ids = db.filter_candidates(con, lat=lat, lng=lng, radius_m=radius_m)
        if not candidate_ids:
            return {'results': [], 'degraded': degraded, 'degraded_reasons': reasons, 'sources_used': []}

        # The lexical lane. It fires only when the WHOLE query names a dish, so
        # a mood query stays on the semantic lane, which is what that lane is for.
        #
        # Measured justification: `curry mee` scored p@5 0.00 because 何九茶室
        # carries 咖喱干拌面 and the vector lane never surfaced it, returning
        # 东京咖喱油拌面 instead -- curry, and noodles, and not the dish asked
        # for. An exact tag match finds the first; no embedding separates the second.
        dish = canonical_for_query(query)
        lexical = []
        if dish:
            tags = db.venue_dishes(con, candidate_ids)
            lexical = [vid for vid, ds in tags.items() if any(canonical(d) == dish for d in ds)]

        try:
            qvec = models.embed([query])[0]
            hits = db.retrieve(con, qvec, candidate_ids, s.embed_model, k=retrieve_k)
            scores = {h['venue_id']: h['score'] for h in hits}
            ordered = [h['venue_id'] for h in hits]
        except Exception:
            # Embedding or pgvector is unavailable. Fall back to the filtered set
            # and let the re-rank do the ordering: worse ranking, but every entry
            # is still cited, which is the thing the product actually promises.
            ordered, scores = candidate_ids[:retrieve_k], {}

        # A venue that literally serves the dish goes in front of the vector hits
        # rather than replacing them: the re-rank still judges fit, and a venue
        # tagged with a dish is not automatically the best place to eat it.
        lexical_set = set(lexical)
        if lexical_set:
            ordered = lexical + [v for v in ordered if v not in lexical_set]

        enriched = db.venues_with_citations(con, ordered)

    # The invariant, enforced before a response is built: an entry that cannot be
    # cited is dropped, never returned with a caveat.
    candidates = dedupe([enriched[v] for v in ordered if v in enriched and enriched[v]['citations']])
    if not candidates:
        return {'results': [], 'degraded': degraded, 'degraded_reasons': reasons, 'sources_used': []}

    picked = models.rerank(query, candidates, limit=limit)

    results = []
    for position, (idx, why) in enumerate(picked, start=1):
        v = candidates[idx]
        results.append(
            {
                'venue': {
                    'id': str(v['id']),
                    'name': v['name'],
                    'area': v['area'],
                    'lat': v['lat'],
                    'lng': v['lng'],
                    'maps_url': maps_url(v),
                    'dishes': v['dishes'][:6],
                },
                # `rank` is the position the re-rank assigned. It replaces `score`,
                # which reported retrieval cosine while the ORDER came from the
                # re-rank, so a higher number could sit below a lower one.
                'rank': position,
                'match': {
                    'basis': 'dish' if v['id'] in lexical_set else 'semantic',
                    'dish': dish,
                    'similarity': round(float(scores.get(v['id'], 0.0)), 4),
                },
                'why': why,
                'distance_m': _distance_m(lat, lng, v['lat'], v['lng']),
                'citations': v['citations'],
            }
        )

    results = disambiguate(results)

    sources = sorted({c['platform'] for r in results for c in r['citations']})
    return {'results': results, 'degraded': degraded, 'degraded_reasons': reasons, 'sources_used': sources}


def one(venue_id, *, lat=None, lng=None):
    """A single venue with its citation trail, for a deep link.

    The venue page is the page the whole product points at, and it must not
    depend on a search having happened in the same tab. Same entry shape as a
    /recommend result so the client renders one component.

    `rank`, `why` and `match.basis` are null here by construction: nothing was
    ranked and nothing was matched. Reporting them as null is honest; inventing
    a rank of 1 for a direct lookup would not be.
    """
    with db.connect() as con:
        v = db.venue_by_id(con, venue_id)
        if not v:
            return None
        enriched = db.venues_with_citations(con, [v['id']])
    entry = enriched.get(v['id'])
    if not entry or not entry['citations']:
        return None
    return {
        'venue': {
            'id': str(entry['id']),
            'name': entry['name'],
            'area': entry['area'],
            'lat': entry['lat'],
            'lng': entry['lng'],
            'maps_url': maps_url(entry),
            'dishes': entry['dishes'][:6],
        },
        'rank': None,
        'match': {'basis': None, 'dish': None, 'similarity': None},
        'why': None,
        'distance_m': _distance_m(lat, lng, entry['lat'], entry['lng']),
        'citations': entry['citations'],
    }

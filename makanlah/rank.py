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


def _distance_m(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)))


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
        candidate_ids = db.filter_candidates(con, lat=lat, lng=lng, radius_m=radius_m)
        if not candidate_ids:
            return {'results': [], 'degraded': False, 'sources_used': []}

        try:
            qvec = models.embed([query])[0]
            hits = db.retrieve(con, qvec, candidate_ids, s.embed_model, k=retrieve_k)
            scores = {h['venue_id']: h['score'] for h in hits}
            ordered = [h['venue_id'] for h in hits]
        except Exception:
            # Retrieval degrades to the filtered set rather than failing the request.
            # A shortlist ranked only by the re-rank is worse than nothing? No — it is
            # still cited, which is what the user is promised.
            ordered, scores = candidate_ids[:retrieve_k], {}

        enriched = db.venues_with_citations(con, ordered)

    # The invariant, enforced before a response is built: an entry that cannot be
    # cited is dropped, never returned with a caveat.
    candidates = [enriched[v] for v in ordered if v in enriched and enriched[v]['citations']]
    if not candidates:
        return {'results': [], 'degraded': False, 'sources_used': []}

    picked = models.rerank(query, candidates, limit=limit)

    results = []
    for idx, why in picked:
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
                'score': round(float(scores.get(v['id'], 0.0)), 4),
                'why': why,
                'distance_m': _distance_m(lat, lng, v['lat'], v['lng']),
                'citations': v['citations'],
            }
        )

    sources = sorted({c['platform'] for r in results for c in r['citations']})
    return {'results': results, 'degraded': False, 'sources_used': sources}

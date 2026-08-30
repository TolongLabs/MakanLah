"""The four ranking stages from docs/TRD.md. Only stage 3 calls a model.

  filter    distance, budget, cuisine -> candidate venues     SQL, cheap
  retrieve  pgvector cosine -> top ~50                        one index scan
  re-rank   model sees query + summaries + excerpts -> top 10 one call
  attach    join citations back on, from the database         SQL

Filter runs before retrieve. A vector search over every KL venue then filtered by
distance wastes the index and returns a great match forty minutes away.
"""

import math
import re

from makanlah import config, db, dishes, models
from makanlah.text import fold_variants


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


def prefer_live(citations):
    """Return the same citations reordered so resolving ones lead.

    A citation carries an optional 'dead' key: True = known dead, False = known
    live, None/absent = not yet checked. Unknown is treated as live, and the
    sort is stable so ties keep their original order. Nothing is dropped and no
    citation dict is modified.
    """
    return sorted(citations, key=lambda c: c.get('dead') is True)


def with_live_citations(entries):
    """Reorder each entry's citations and drop the ones nobody can check.

    Drops entries with no citations and entries whose every citation is known
    dead. Entries with only unchecked citations survive: unknown is not dead.
    """
    out = []
    for entry in entries:
        if not entry.get('citations'):
            continue
        citations = prefer_live(entry['citations'])
        if all(c.get('dead') is True for c in citations):
            continue
        out.append({**entry, 'citations': citations})
    return out


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


# A dietary constraint the corpus cannot speak to. Posts rarely state
# certification, and inferring it from a venue name or cuisine is the confident
# wrong answer this product exists to avoid -- getting it wrong is not a ranking
# miss, it is somebody eating what they hold themselves not to.
#
# Matched as a standalone word so "Restoran Halal Corner" -- a name, not a
# request -- does not put a disclaimer on a search that never asked for one.
# Latin needs word boundaries so "Halal Corner" is not a request. CJK cannot
# have them -- Python's \\w matches Han, so 清真餐厅 would be rejected by its own
# following character. Two patterns rather than one clever one.
_HALAL = re.compile(r'(?<![A-Za-z])halal(?![A-Za-z])', re.I)
# 清真寺 is a mosque, and 清真 is a prefix of it. A substring match reads a venue
# described as near a mosque as a halal claim -- confidently mislabelling it on
# the strength of a landmark. Being wrong about halal is the one error a
# Malaysian user will not forgive, so the exclusion is explicit and tested.
_HALAL_CJK = re.compile(r'清真(?!寺)')
_HALAL_NAME = re.compile(r'\b(restoran|restaurant|kedai|corner|cafe)\b', re.I)


def coverage_gaps(query):
    """Name what the corpus cannot answer about this query.

    Returns gap keys, not prose: the caller owns the wording, and /ask already
    has a voice for this -- "The provided excerpts do not mention whether ...".
    A ranked list had no equivalent, so a halal query came back as an unmarked
    list that reads as an answer.
    """
    if not query:
        return []
    gaps = []
    if _HALAL_CJK.search(query) or (_HALAL.search(query) and not _HALAL_NAME.search(query)):
        gaps.append('halal')
    return gaps


# A halal claim may not rest on a fragment. UAT found 鱼你 flagged on a Google
# Maps excerpt reading "...Yonny is the 'halal' counterpart, and that distinction
# is the" -- it stops mid-sentence, and the clause that would say what the
# distinction means is exactly what #15 truncated away. The word is also in scare
# quotes in the original, which usually means the writer is holding it at arm's
# length.
#
# Being wrong about halal is the one error a Malaysian user will not forgive, so
# a cut-off sentence is not evidence for it. Other excerpts stay usable; they are
# simply not allowed to carry this claim.
_ENDS_MID_SENTENCE = re.compile(r'[\w,;:\'"’”，、]\s*$')

# Negation does not appear in the corpus today -- nine phrasings were searched
# for and none is present -- so this is a latent risk rather than a live one. It
# becomes live the moment a re-scrape adds one post saying a place is not halal,
# and the failure mode is the worst available: telling Nabilah a venue speaks to
# her constraint when the post says the opposite.
_NEGATED = re.compile(
    r'\b(not|non|bukan|tidak|tak)\s*[- ]?\s*halal\b|\bno\s+halal\b|非清真',
    re.I,
)


def _supports_gap(text, gap):
    """Whether this excerpt can carry the claim, not merely mention the word."""
    if not text:
        return False
    if _ENDS_MID_SENTENCE.search(text):
        return False
    if gap == 'halal':
        if _NEGATED.search(text):
            return False
        return bool(_HALAL_CJK.search(text) or _HALAL.search(text))
    return False


def mark_gap_coverage(entries, gaps):
    """Say per venue whether its own posts speak to the gap.

    A blanket "we have no halal information" is false and a reader can disprove
    it: the corpus contains 清真友好 -- halal-friendly, written by a person --
    behind a venue we already show. Claiming silence over real testimony is the
    same failure as claiming knowledge we do not have, pointed the other way.

    So the claim is per result and checkable: this venue's posts mention it, or
    they do not. Quoting someone who wrote it is not inference; it is the core
    loop. Deciding halal from a name or a cuisine would be, and is not done here.
    """
    if not gaps:
        return entries
    for e in entries:
        cites = e.get('citations') or []
        mentions = []
        for gap in gaps:
            hit = any(_supports_gap(c.get('excerpt'), gap) for c in cites)
            if hit:
                mentions.append(gap)
        e['venue']['gap_mentions'] = mentions
    return entries


# A summary is prose a model wrote. It is not a citation, and it must not be able
# to assert something the citation layer has already refused to support.
_GAP_CLAIM = {
    'halal': re.compile(r'halal|muslim|清真|masjid|mosque|mesra\s+muslim', re.I),
}

# "Halal-friendly" and "halal" are different claims in Malaysia, and the gap between
# them is the whole question. Halal implies certification; muslim-friendly or
# pork-free is weaker, and is the strongest claim many Chinese-Malaysian eateries
# can honestly make.
_FRIENDLY_DEGREE = re.compile(r'清真友好|halal[\s-]*friendly|muslim[\s-]*friendly|mesra\s+muslim', re.I)
_STATUS_ASSERTION = re.compile(
    r'dinyatakan\s+halal|disahkan\s+halal|sah\s+halal|certified\s+halal|halal[\s-]*certified|清真认证', re.I
)


def _only_friendly_evidence(citations):
    """True when every halal token in the excerpts sits inside a 'friendly' remark.

    Strips the friendly phrases and asks whether any halal token survives outside
    them. 清真友好 leaves nothing; 清真认证 or a bare halal statement does.
    """
    saw = False
    for c in citations:
        text = c.get('excerpt') or ''
        if not _supports_gap(text, 'halal'):
            continue
        saw = True
        if _supports_gap(_FRIENDLY_DEGREE.sub('', text), 'halal'):
            return False
    return saw


def withhold_unsupported_gap_claims(entries, gaps):
    """Drop every `why` in a response whose query raised a coverage gap.

    Structural, not textual, and deliberately blunt. `why` is regenerated per
    request by a model, so a filter matching its OUTPUT is only as good as the
    phrasing it anticipated. Measured over 12 identical calls at 1696ba1: 5
    non-empty lines, 4 of them asserting halal -- `Nasional halal, dekat Masjid
    Jamek`, `Tempat sarapan halal dan mesra Muslim` -- while the same query
    returned an empty `why` on other calls. Withdrawal held on most requests and
    leaked on some. **A safeguard that is probabilistic on halal is not a
    safeguard**, and single-sample verification cannot tell the two apart.

    So no summary survives a gap query, including one that would have been fine.
    It costs a defensible line -- 清真友好，国民老店 quotes the poster and infers
    nothing -- and buys a guarantee that does not depend on what a model said this
    time. The evidence itself is untouched: `gap_mentions` still marks the venues
    whose own posts speak to the topic, and the citation is still on the card for
    the reader to judge.
    """
    if not gaps:
        return entries
    for e in entries:
        e['why'] = None
    return entries


def add_corroboration(entries):
    """Attach the signals that make "independent sources" checkable (#87).

    Two mentions are corroboration when two different people wrote two different
    posts. Counting platforms alone said "two independent sources" for one author
    quoted twice, and counting citations alone said it for one post quoted twice.

    `shared_with` names the other venues in THIS response backed by the same post.
    UAT found one listicle driving ranks 1, 2 and 3 while each card claimed
    independent corroboration -- true per card, false read as a page. The client
    cannot see that without being told, because it only ever holds one card.

    A missing author_handle is unknown, not a second person. Counting absent
    authorship as distinct would manufacture corroboration out of missing data,
    which is the failure this whole signal exists to prevent.
    """
    backers = {}
    for e in entries:
        vid = e['venue']['id']
        for c in e.get('citations') or []:
            backers.setdefault(c['post_url'], set()).add(vid)

    order = [e['venue']['id'] for e in entries]
    for e in entries:
        vid = e['venue']['id']
        cites = e.get('citations') or []
        # A post nobody can open is not a second source (#111). Counting dead ones
        # put "Corroborated by two independent sources" on 11 of 59 results whose
        # card could only render ONE testimony, because leadPair correctly refuses
        # the dead citation the count had just relied on. 阿喜 read 3 posts / 2
        # authors / 2 platforms and had exactly one openable post behind it.
        #
        # This is the whole claim, not a detail: corroboration means a reader can
        # go and check two people. An unopenable post is precisely what they cannot
        # check, so counting it manufactures the confidence the signal exists to
        # earn. `shared_with` below still walks every citation -- one listicle
        # driving three ranks is worth saying whether or not it still resolves.
        live = [c for c in cites if c.get('dead') is not True]
        e['venue']['corroboration'] = {
            # Identity, not address. Google Maps has no per-review URL, so three
            # reviewers of Upper House shared one post_url and the count read 1 --
            # denying the stamp to a venue that had earned it, which is #87 in the
            # mirror. The card prints "3 posts" and links to the page holding them:
            # counting voices and pointing at where they live are compatible jobs,
            # just not one integer doing both (#153).
            'posts': len({c['post_id'] for c in live}),
            'authors': len({c['author_handle'] for c in live if c.get('author_handle')}),
            'platforms': len({c['platform'] for c in live if c.get('platform')}),
        }
        for c in cites:
            others = backers.get(c['post_url'], set()) - {vid}
            c['shared_with'] = [v for v in order if v in others]
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


GAP_VENUES = 5


def evidence_gap(named, dish, lexical, enriched, candidates):
    """The corpus knows this dish and cannot show anybody writing about it.

    Measured on prod: `roti canai` returned Mon Beef Roti, RAYs @ B.LAND, Potato
    Corner, kaiia kanteen and Menya Aburi. The lexical lane had resolved the dish
    correctly and found **exactly the two venues carrying it**, Devi's Corner and
    Kapitan; both were dropped by `with_live_citations` because each has a single
    RedNote citation and both are dead. Every step behaved as designed and a person
    searching for roti canai was shown a potato shop.

    **This is the app at its most misleading where it knows most.** `ayam goreng
    berempah` is the corpus never having heard of a dish, and is harder -- telling
    that from a mood query needs a signal #85 measured and did not find. This case
    needs no such signal: the corpus holds the answer and is declining to say it.

    Returning `results: []` rather than the substitutes is not severity for its own
    sake. docs/TRD.md: returning a venue that does not match, with prose conceding
    it does not match, is worse than returning nothing.

    Naming the venues rather than counting them, because the two claims are not
    equally checkable. That a post said X is unverifiable once the post is gone;
    that the RESTAURANT exists is verifiable in ten seconds from its place_id. A
    bare number gives a hungry person nothing and is no more provable.

    Fires only when all three hold, and each rules out a different false positive:

      - the query named something the corpus carries -- a mood query names nothing
        in any lane at any cutoff, so it never reaches here
      - venues in range actually carry it
      - NONE of them survived to the response

    `enriched` inner-joins mentions, so a venue with no citation at all never
    appears in it and is never named here. Everything this returns had readable
    testimony that has since stopped resolving, which is what lets the copy say so.
    """
    if not named or not lexical:
        return None
    if any(dishes.fold(d) in named for c in candidates for d in (c['dishes'] or [])):
        return None
    lost = [enriched[v] for v in lexical if v in enriched and enriched[v]['citations']]
    if not lost:
        return None
    return {
        'term': dish,
        'venues': [{'name': e['name'], 'area': e['area'], 'maps_url': maps_url(e)} for e in lost[:GAP_VENUES]],
        'total': len(lost),
    }


def match_block(venue_id, *, lexical_set, dish, scores):
    """Why this ROW is here: `{basis, dish, similarity}` per docs/TRD.md.

    `dish` is per-row and not per-query, and the difference was visible on prod.
    `roti canai` came back as `basis: 'semantic', dish: 'roti canai'` on five
    venues that have nothing to do with it: the lane resolved the dish correctly
    and found exactly two venues carrying it, Devi's Corner and Kapitan, and both
    were dropped by `with_live_citations` because each has a single RedNote
    citation and both are dead. So no row that reached the client had matched the
    dish, and every one of them said it had.

    Nothing renders this field today, which is exactly why it was free to be
    wrong. A payload that says a row matched a dish it did not match becomes
    untrue UI the moment somebody binds to it.

    Extracted from `recommend` so it can be tested without a database. Inline, the
    only check available was one that mocked `recommend` and therefore asserted
    nothing about this rule at all.
    """
    hit = venue_id in lexical_set
    return {
        'basis': 'dish' if hit else 'semantic',
        'dish': dish if hit else None,
        'similarity': round(float(scores.get(venue_id, 0.0)), 4),
    }


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
        #
        # The vocabulary is the CORPUS, not the fifteen-dish table in dishes.py.
        # That table recognised 12.3% of the 838 dish strings the corpus carries
        # and none of the ten mixed-script ones, so `蛋挞` -- written about by two
        # venues -- had no lexical lane and fell to the vector lane, which returned
        # a Korean BBQ and a venue whose only tie to the query is an author handle
        # spelled 蛋挞. See #85 for the numbers. `venue_dishes` costs 75ms on 247
        # candidates and is now paid on every query rather than only on the fifteen.
        tags = db.venue_dishes(con, candidate_ids)
        vocabulary = frozenset(dishes.fold(d) for ds in tags.values() for d in ds if dishes.fold(d))
        named, dish = dishes.named_in(query, vocabulary)
        lexical = [vid for vid, ds in tags.items() if any(dishes.fold(d) in named for d in ds)] if named else []

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
    candidates = with_live_citations(candidates)

    gap = evidence_gap(named, dish, lexical, enriched, candidates)
    if gap:
        # `results: []` is the point, not a side effect. docs/TRD.md is explicit that
        # returning a venue that does not match, with prose conceding it does not
        # match, is worse than returning nothing -- and five semantically-close
        # venues under a note saying we meant something else is exactly that.
        return {
            'results': [],
            'evidence_gap': gap,
            'degraded': degraded,
            'degraded_reasons': reasons,
            'sources_used': [],
        }

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
                    # Counts rather than an average: 88% of multi-mention venues
                    # span more than one bucket, so disagreement is the common
                    # case and it is the part worth a reader's attention. A mean
                    # of this distribution reads "excellent" almost everywhere.
                    'sentiment': v.get('sentiment') or {'positive': 0, 'mixed': 0, 'negative': 0},
                    'lat': v['lat'],
                    'lng': v['lng'],
                    'maps_url': maps_url(v),
                    'dishes': v['dishes'][:6],
                },
                # `rank` is the position the re-rank assigned. It replaces `score`,
                # which reported retrieval cosine while the ORDER came from the
                # re-rank, so a higher number could sit below a lower one.
                'rank': position,
                'match': match_block(v['id'], lexical_set=lexical_set, dish=dish, scores=scores),
                'why': why,
                'distance_m': _distance_m(lat, lng, v['lat'], v['lng']),
                'citations': v['citations'],
            }
        )

    results = disambiguate(results)
    results = add_corroboration(results)
    gaps = coverage_gaps(query)
    results = mark_gap_coverage(results, gaps)
    results = withhold_unsupported_gap_claims(results, gaps)

    sources = sorted({c['platform'] for r in results for c in r['citations']})
    return {
        'results': results,
        'degraded': degraded,
        'degraded_reasons': reasons,
        'sources_used': sources,
        # What the corpus cannot speak to for this query. Results still come
        # back; they come back with the gap named rather than reading as an
        # answer to a question nobody can answer from these posts.
        'coverage_gaps': gaps,
    }


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
    kept = with_live_citations([entry])
    if not kept:
        return None
    entry = kept[0]
    return {
        'venue': {
            'id': str(entry['id']),
            'name': entry['name'],
            'area': entry['area'],
            'sentiment': entry.get('sentiment') or {'positive': 0, 'mixed': 0, 'negative': 0},
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

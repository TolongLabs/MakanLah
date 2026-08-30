"""Google Places API (New) as the ingestion path, in place of driving a browser.

The CDP path works and is what proved the corpus, but it is the wrong tool now
that a key exists. Measured against it on the same venue:

| | CDP over Chrome | Places API |
| --- | --- | --- |
| Per venue | ~25s | ~1s |
| Review text | 1,008 of 1,388 truncated by Google's own "… More" (#15) | whole |
| Price | parsed out of prose, 3% of mentions | `priceRange` in MYR, from Google |
| Failure mode | Chrome died mid-run and the loop kept going | an HTTP status |

No evasion, no session, no scraping: this is the platform's own documented
interface, which is also the durable answer AGENTS.md asks for.

Cost. Two SKUs matter, and the field mask decides which one a call lands in:
`reviews`, `priceLevel`, `priceRange` and `rating` are Place Details ENTERPRISE
($25/1000, 1,000 free a month); a Text Search asking only for id, name and
location is PRO ($32/1000, 5,000 free a month). Asking for a field you do not
need moves the whole call up a tier, so the field masks here are deliberately
narrow.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = 'https://places.googleapis.com/v1'

# Keep this narrow. Adding `priceLevel` or `rating` here would move every search
# from the Pro SKU to Enterprise and cut the free monthly allowance from 5,000
# to 1,000 -- for fields the details call already returns.
SEARCH_MASK = 'places.id,places.displayName,places.location,nextPageToken'

# Enterprise, and worth it: this one call carries the evidence AND the price.
DETAILS_MASK = 'id,displayName,location,formattedAddress,priceLevel,priceRange,rating,userRatingCount,reviews'

LEVELS = {
    'PRICE_LEVEL_INEXPENSIVE': 1,
    'PRICE_LEVEL_MODERATE': 2,
    'PRICE_LEVEL_EXPENSIVE': 3,
    'PRICE_LEVEL_VERY_EXPENSIVE': 4,
}

# Same thresholds the text parser uses, so a band means one thing corpus-wide.
BANDS = ((15, 1), (40, 2), (100, 3))


# The CDP path stored the `!1s0x...:0x...` pair lifted out of a Maps URL. That is
# a CID and the API rejects it with 400 INVALID_ARGUMENT. 809 of 821 stored ids
# are that shape, so trusting the column cost one bad request per venue -- 505 in
# one run before it was caught.
# Any 0x-prefixed id is a CID, whole pair or not. A real place ID is base64-ish
# and never starts with 0x, so the prefix alone is the safe discriminator.
CID = re.compile(r'^0x', re.I)


def is_api_place_id(pid):
    """Whether this stored id can be handed to the Places API at all."""
    return isinstance(pid, str) and bool(pid.strip()) and not CID.match(pid.strip())


def api_key():
    key = os.environ.get('GOOGLE_PLACES_API_KEY')
    if not key:
        raise RuntimeError('GOOGLE_PLACES_API_KEY is not set')
    return key


def price_band_from_level(level):
    """Google's enum onto our 1..4. Unspecified and FREE are not bands."""
    return LEVELS.get(level) if isinstance(level, str) else None


def price_band_from_range(rng):
    """`priceRange` in MYR onto our 1..4, by midpoint.

    Refused for any other currency: we hold no exchange rate, and inventing one
    turns a real figure into a wrong band, which is worse than no band at all.
    """
    if not isinstance(rng, dict):
        return None
    lo, hi = rng.get('startPrice') or {}, rng.get('endPrice') or {}
    if not isinstance(lo, dict) or not isinstance(hi, dict):
        return None
    if {lo.get('currencyCode'), hi.get('currencyCode')} - {'MYR', None} or lo.get('currencyCode') != 'MYR':
        return None
    try:
        a, b = float(lo.get('units', 0)), float(hi.get('units', 0))
    except (TypeError, ValueError):
        return None
    if a <= 0 and b <= 0:
        return None
    mid = (a + b) / 2 if b else a
    for ceiling, band in BANDS:
        if mid < ceiling:
            return band
    return 4


def place_price_band(place):
    """Prefer the ringgit figures over the symbol; fall back to the enum."""
    return price_band_from_range(place.get('priceRange')) or price_band_from_level(place.get('priceLevel'))


def review_url(place_id):
    """Where a human verifies the citation. Google publishes no per-review URL,
    so this is the place page, which is where the review lives."""
    return f'https://www.google.com/maps/place/?q=place_id:{place_id}'


def review_to_post(review, place_id, venue_name):
    """One review -> the source_post shape, or None when it cites nothing.

    The star rating IS the writer's judgement stated numerically, so it becomes
    the sentiment directly. Asking a model to infer it from the prose would be
    less accurate and cost a call per review.
    """
    if not isinstance(review, dict):
        return None
    text = ((review.get('text') or {}).get('text') or '').strip()
    if not text:
        text = ((review.get('originalText') or {}).get('text') or '').strip()
    if not text:
        return None
    stars = review.get('rating')
    sentiment = round((int(stars) - 3) / 2, 2) if isinstance(stars, int) and 1 <= stars <= 5 else None
    return {
        # Google's own review resource name. It is what makes two reviews of one
        # venue distinct -- deduping on the URL collapsed three reviewers into a
        # single citation and denied venues the corroboration they had earned (#153).
        'platform_post_id': review.get('name') or f'{place_id}:{hash(text) & 0xFFFFFFFF:08x}',
        'url': review_url(place_id),
        'raw_text': text,
        'sentiment': sentiment,
        'posted_at_raw': review.get('relativePublishTimeDescription') or None,
        'author_handle': (review.get('authorAttribution') or {}).get('displayName') or None,
        'venue_name': venue_name,
    }


def _post(url, body, key, mask, timeout=30):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key, 'X-Goog-FieldMask': mask},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get(url, key, mask, timeout=30):
    req = urllib.request.Request(url, headers={'X-Goog-Api-Key': key, 'X-Goog-FieldMask': mask})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def search(query, key=None, pages=1, language='en'):
    """Text Search. Returns [{id, name, lat, lng}]. Pro SKU -- see the module note.

    Each page is a separate billable call, so `pages` is the cost dial: one page
    is 20 places, three is the API's maximum of 60.
    """
    key = key or api_key()
    out, token = [], None
    for _ in range(max(1, pages)):
        body = {'textQuery': query, 'maxResultCount': 20, 'languageCode': language}
        if token:
            body['pageToken'] = token
        try:
            d = _post(f'{BASE}/places:searchText', body, key, SEARCH_MASK)
        except urllib.error.HTTPError as e:
            print(f'  search failed {query!r}: {e.code} {e.read()[:120].decode(errors="replace")}', flush=True)
            break
        for p in d.get('places', []):
            loc = p.get('location') or {}
            if p.get('id') and loc.get('latitude') is not None:
                out.append(
                    {
                        'place_id': p['id'],
                        'name': (p.get('displayName') or {}).get('text') or '',
                        'lat': loc['latitude'],
                        'lng': loc['longitude'],
                    }
                )
        token = d.get('nextPageToken')
        if not token:
            break
        # The API rejects a page token used too quickly after it is issued.
        time.sleep(2)
    return [x for x in out if x['name']]


def details(place_id, key=None, language='en'):
    """Place Details with reviews and price. Enterprise SKU -- one call per venue."""
    key = key or api_key()
    try:
        return _get(f'{BASE}/places/{place_id}?languageCode={language}', key, DETAILS_MASK)
    except urllib.error.HTTPError as e:
        print(f'  details failed {place_id}: {e.code} {e.read()[:120].decode(errors="replace")}', flush=True)
        return None

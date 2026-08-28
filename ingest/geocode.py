"""Nominatim geocoding. Ingestion-time only, never on the request path.

Its usage policy requires a real contact address in the User-Agent and at most
one request per second. Both are honoured. Geocoding once per venue with nobody
waiting is exactly why a free 1-req/sec service is adequate.
"""

import json
import time
import urllib.parse
import urllib.request

from makanlah import config

# Klang Valley. Nominatim will happily match a bare Chinese restaurant name to
# somewhere in China, and a wrong coordinate is worse than a null one.
BBOX = (2.6, 3.6, 101.2, 102.1)
_last = [0.0]


def _throttle():
    gap = time.time() - _last[0]
    if gap < 1.1:
        time.sleep(1.1 - gap)
    _last[0] = time.time()


def geocode(name, area=None, city='Kuala Lumpur', country='Malaysia'):
    """Return (lat, lng, display_name, confidence) or None."""
    s = config.settings()
    q = ', '.join(x for x in [name, area, city, country] if x)
    url = f'{s.nominatim_base_url}/search?' + urllib.parse.urlencode(
        {'q': q, 'format': 'json', 'limit': 1, 'addressdetails': 1}
    )
    _throttle()
    req = urllib.request.Request(url, headers={'User-Agent': s.nominatim_user_agent})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            hits = json.loads(r.read())
    except Exception:
        return None
    if not hits:
        return None
    h = hits[0]
    try:
        lat, lng = float(h['lat']), float(h['lon'])
    except (KeyError, ValueError):
        return None
    lo_lat, hi_lat, lo_lng, hi_lng = BBOX
    if not (lo_lat <= lat <= hi_lat and lo_lng <= lng <= hi_lng):
        return None
    return lat, lng, h.get('display_name'), float(h.get('importance') or 0.0)

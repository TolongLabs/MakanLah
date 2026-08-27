"""Nominatim geocoding. Ingestion-time only, never on the request path.

Its usage policy requires a real contact address in the User-Agent and at most
one request per second. Both are honoured here.
"""

import json
import os
import time
import urllib.parse
import urllib.request

import env

env.load()

BASE = os.environ.get('NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org')
UA = os.environ.get('NOMINATIM_USER_AGENT', 'MakanLah/0.1')
_last = [0.0]


def _throttle():
    gap = time.time() - _last[0]
    if gap < 1.1:
        time.sleep(1.1 - gap)
    _last[0] = time.time()


def geocode(name, area=None, city='Kuala Lumpur', country='Malaysia'):
    """Return (lat, lng, display_name, confidence) or None."""
    q = ', '.join(x for x in [name, area, city, country] if x)
    url = f'{BASE}/search?' + urllib.parse.urlencode({'q': q, 'format': 'json', 'limit': 1, 'addressdetails': 1})
    _throttle()
    req = urllib.request.Request(url, headers={'User-Agent': UA})
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
    # Klang Valley bounding box. A hit outside it matched the wrong continent,
    # which Nominatim does readily for a bare Chinese restaurant name.
    if not (2.6 <= lat <= 3.6 and 101.2 <= lng <= 102.1):
        return None
    return lat, lng, h.get('display_name'), float(h.get('importance') or 0.0)

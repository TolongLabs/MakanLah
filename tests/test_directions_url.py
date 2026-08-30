"""A Directions link, and a place_id that is only trusted when it is one.

`maps_url` passes `query_place_id={place_id}` unconditionally. 306 of 821 venues
still carry the `0x...:0x...` CID the CDP scraper lifted out of a Maps URL, which
is not a Places API place ID -- the same confusion that sent 505 bad requests
during the Places migration. An invalid place id in a Maps link cannot be
verified with curl, because Google returns its SPA shell with HTTP 200 either
way, so the safe reading is that it may resolve to nothing.

A name-and-area search always resolves to something sensible. So the place_id is
an enhancement applied only when it is genuinely a place ID, never a gamble.

`directions_url` is the All Sources modal's missing CTA. Built from the same
parts server-side: no key, no billing, no request-path fetch.
"""

from makanlah.rank import directions_url, maps_url

API_ID = 'ChIJIfYLMzFJzDERPG9vHZ7DqiE'
CID = '0x31cc49e5fd3b1b39:0x5876916611066eab'


def test_directions_uses_the_documented_dir_endpoint():
    u = directions_url({'name': 'Village Park', 'area': 'Damansara', 'place_id': API_ID})
    assert u.startswith('https://www.google.com/maps/dir/?api=1')
    assert 'destination=' in u


def test_a_real_place_id_disambiguates_a_chain():
    u = directions_url({'name': 'Village Park', 'area': None, 'place_id': API_ID})
    assert f'destination_place_id={API_ID}' in u


def test_a_legacy_cid_is_not_passed_as_a_place_id():
    """The 306-venue case. Better a name search that resolves than a place id
    that may not."""
    u = directions_url({'name': 'Village Park', 'area': 'Damansara', 'place_id': CID})
    assert 'destination_place_id' not in u
    assert 'Village+Park' in u or 'Village%20Park' in u


def test_maps_url_applies_the_same_rule():
    assert 'query_place_id' not in maps_url({'name': 'X', 'area': None, 'place_id': CID})
    assert f'query_place_id={API_ID}' in maps_url({'name': 'X', 'area': None, 'place_id': API_ID})


def test_no_place_id_still_produces_a_usable_link():
    u = directions_url({'name': 'Kedai Kopi', 'area': 'Cheras', 'place_id': None})
    assert u.startswith('https://www.google.com/maps/dir/?api=1')
    assert 'Cheras' in u
    assert 'destination_place_id' not in u


def test_the_city_is_included_so_a_common_name_lands_in_kl():
    u = directions_url({'name': 'Restoran Ali', 'area': None, 'place_id': None})
    assert 'Kuala+Lumpur' in u or 'Kuala%20Lumpur' in u

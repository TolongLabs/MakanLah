"""Ranking behaviour that does not need a database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from makanlah.rank import _distance_m, maps_url


class TestDistance:
    def test_known_kl_distance_is_about_right(self):
        # KLCC to Mid Valley is roughly 6 km.
        d = _distance_m(3.1578, 101.7117, 3.1177, 101.6770)
        assert 5000 < d < 7000

    def test_a_missing_coordinate_yields_none_rather_than_zero(self):
        assert _distance_m(3.1, 101.7, None, 101.7) is None
        assert _distance_m(None, None, 3.1, 101.7) is None

    def test_identical_points_are_zero(self):
        assert _distance_m(3.1, 101.7, 3.1, 101.7) == 0


class TestMapsUrl:
    """No maps SDK, no key, no billing."""

    def test_url_contains_the_venue_and_needs_no_key(self):
        u = maps_url({'name': 'Village Park', 'area': 'Damansara Uptown', 'city': 'Petaling Jaya'})
        assert u.startswith('https://www.google.com/maps/search/?api=1&query=')
        assert 'Village' in u
        assert 'key=' not in u

    def test_place_id_is_used_to_disambiguate_a_chain(self):
        u = maps_url({'name': 'Oriental Kopi', 'area': None, 'city': 'Kuala Lumpur', 'place_id': 'ChIJabc'})
        assert 'query_place_id=ChIJabc' in u

    def test_a_chinese_name_is_escaped_not_dropped(self):
        u = maps_url({'name': '兴记肉骨茶', 'area': None, 'city': 'Kuala Lumpur'})
        assert '%' in u.split('query=')[1]

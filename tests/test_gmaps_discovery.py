"""#157: Google Maps must be able to introduce a restaurant, not only annotate one.

`enrich_gmaps.pending_venues` iterates `venue where exists (mention)`. Maps carries
84% of the evidence and cannot create a single venue, so every venue in the corpus
entered through ~20 RedNote keywords. That is the ceiling the tester hit.

The DOM half is verified against a live browser, not here. What is testable here is
the parse: which anchors become venues and which are thrown away.
"""

from ingest.gmaps import parse_feed

KL = '!1s0x31cc49c701a5e5ab:0x1c0b0c1a2b3c4d5e!8m2!3d3.1468!4d101.7125'
KL2 = '!1s0x31cc49c701a5e5ac:0x2c0b0c1a2b3c4d5f!8m2!3d3.1302!4d101.6709'


def a(name, href):
    return {'name': name, 'href': href}


def test_reads_name_coords_and_place_id_from_a_results_anchor():
    out = parse_feed([a('Village Park', f'/maps/place/x/data={KL}')])
    assert out == [
        {'name': 'Village Park', 'place_id': '0x31cc49c701a5e5ab:0x1c0b0c1a2b3c4d5e', 'lat': 3.1468, 'lng': 101.7125}
    ]


def test_dedupes_on_place_id_because_maps_repeats_an_anchor_per_card():
    """The feed renders the same place as both a link and a thumbnail link."""
    out = parse_feed([a('Village Park', f'/maps/place/x/data={KL}'), a('Village Park', f'/maps/place/y/data={KL}')])
    assert len(out) == 1


def test_drops_an_anchor_with_no_coordinates():
    """A place with no !3d/!4d cannot be placed on the map, and a venue without
    coordinates never reaches a distance-bounded query."""
    assert parse_feed([a('Nowhere', '/maps/place/x/data=!1s0x31cc:0x1c0b')]) == []


def test_drops_an_anchor_with_no_place_id():
    """place_id is the dedupe key and the merge key for #59. Without it the row
    cannot be reconciled against anything."""
    assert parse_feed([a('Nowhere', '/maps/place/x/data=!8m2!3d3.1468!4d101.7125')]) == []


def test_drops_a_hit_outside_the_klang_valley():
    """resolve() uses the same bound. A hit outside it matched the wrong place,
    and a wrong coordinate is worse than a null one."""
    penang = '!1s0x304ac3:0x1c0b!8m2!3d5.4141!4d100.3288'
    assert parse_feed([a('Penang Road', f'/maps/place/x/data={penang}')]) == []


def test_drops_an_anchor_with_no_name():
    assert parse_feed([a('', f'/maps/place/x/data={KL}'), a('   ', f'/maps/place/y/data={KL2}')]) == []


def test_honours_the_limit():
    items = []
    for i in range(9):
        items.append(a(f'V{i}', f'/maps/place/x/data=!1s0x31cc49c701a5e5{i:02x}:0x{i}!8m2!3d3.14{i}0!4d101.71{i}0'))
    assert len(parse_feed(items, limit=4)) == 4


def test_a_malformed_entry_is_skipped_not_raised():
    """AGENTS.md: scraped input is the least trustworthy data in the project."""
    out = parse_feed([{'name': None, 'href': None}, {}, a('Real', f'/maps/place/x/data={KL}')])
    assert [r['name'] for r in out] == ['Real']

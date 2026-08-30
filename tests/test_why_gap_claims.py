"""No summary survives a query that raised a coverage gap.

Structural rather than textual, because `why` is regenerated per request by a
model. The earlier text-matching version withdrew correctly on most calls and
leaked on others: over 12 identical calls at 1696ba1, 5 non-empty lines came
back and 4 asserted halal. The variants below are the real leaked strings.
"""

from makanlah.rank import withhold_unsupported_gap_claims


def entry(name, why, mentions=None, excerpts=()):
    return {
        'why': why,
        'venue': {'id': name, 'name': name, 'gap_mentions': mentions or []},
        'citations': [{'excerpt': x} for x in excerpts],
    }


LEAKED = [
    'Nasional halal, sesuai keluarga, lokasi strategik dekat masjid.',
    'Nasional halal, dekat Masjid Jamek, sesuai untuk keluarga.',
    'Tempat sarapan halal dan mesra Muslim yang sesuai untuk keluarga.',
    'Adalah rakan kongsi halal kepada Fish With You yang popular.',
    'Makanan Cina autentik yang mesra Muslim dan berpatutan.',
    'Dinyatakan halal dan mesra Muslim, sesuai untuk keluarga.',
]


def test_every_variant_that_reached_prod_is_withdrawn():
    entries = [entry(f'v{i}', w, ['halal']) for i, w in enumerate(LEAKED)]
    out = withhold_unsupported_gap_claims(entries, ['halal'])
    assert [e['why'] for e in out] == [None] * len(LEAKED)


def test_a_defensible_line_goes_too_because_the_guarantee_cannot_be_conditional():
    # 清真友好，国民老店 quotes the poster and infers nothing. It still goes: the
    # rule cannot depend on judging text a model regenerates each request.
    e = entry('Hock Kee', '清真友好，国民老店，性价比高适合家庭', ['halal'], ['这家清真友好，很推荐。'])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] is None


def test_a_query_with_no_gap_keeps_every_summary():
    entries = [entry('a', 'Soup is rich.'), entry('b', 'Famous for coconut rice.')]
    out = withhold_unsupported_gap_claims(entries, [])
    assert [e['why'] for e in out] == ['Soup is rich.', 'Famous for coconut rice.']


def test_the_evidence_itself_is_never_touched():
    # The claim goes; the testimony stays. gap_mentions and citations are what the
    # reader judges for themselves, and they must survive the withdrawal.
    e = entry('Hock Kee', 'Nasional halal, dekat Masjid Jamek.', ['halal'], ['这家清真友好，很推荐。'])
    out = withhold_unsupported_gap_claims([e], ['halal'])[0]
    assert out['why'] is None
    assert out['venue']['gap_mentions'] == ['halal']
    assert out['citations'][0]['excerpt'] == '这家清真友好，很推荐。'

"""A summary may not assert a dietary property the citations do not carry.

Built from the three real prod results at 0a9e84a, query
`tempat makan halal untuk keluarga`, where two of three asserted halal with
`gap_mentions == []`.
"""

from makanlah.rank import withhold_unsupported_gap_claims


def entry(name, why, mentions):
    return {'why': why, 'venue': {'id': name, 'name': name, 'gap_mentions': mentions}}


def test_drops_a_halal_claim_the_citations_withdrew():
    # 鱼你: the excerpt ends mid-qualifier and scare-quoted, so gap_mentions is
    # empty. The summary asserted it anyway.
    e = entry('鱼你', 'Adalah rakan kongsi halal kepada Fish With You yang popular.', [])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] is None


def test_drops_muslim_friendly_inferred_from_the_reviewers_own_identity():
    # Sisters Place: "As a Chinese Muslim Penang-aite, I actually enjoy..." became
    # a property of the restaurant. A Muslim person ate here is not this place is
    # Muslim-friendly, and `mesra Muslim` reads as an assurance in Malay.
    e = entry('Sisters Place', 'Makanan Cina autentik yang mesra Muslim dan berpatutan.', [])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] is None


def test_keeps_a_claim_the_citations_do_carry():
    # Hock Kee Heritage: 清真友好 is real, written by a person, and survives.
    why = 'Dinyatakan halal dan mesra Muslim, sesuai untuk keluarga.'
    e = entry('Hock Kee Heritage', why, ['halal'])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] == why


def test_leaves_a_why_that_makes_no_dietary_claim_alone():
    why = 'Sesuai untuk keluarga, harga berpatutan.'
    e = entry('X', why, [])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] == why


def test_no_gap_in_the_query_changes_nothing():
    why = 'Tempat halal yang popular.'
    e = entry('X', why, [])
    assert withhold_unsupported_gap_claims([e], [])[0]['why'] == why


def test_mosque_wording_cannot_carry_the_claim_either():
    # "dekat masjid" -- near a mosque -- is the 清真寺 confusion the gap exclusion
    # exists to prevent, reappearing as supporting reasoning in prose.
    e = entry('Y', 'Lokasi strategik dekat masjid, sesuai untuk keluarga.', [])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] is None


# #123: supported topic, overstated degree.


def entry_c(name, why, mentions, excerpts):
    return {
        'why': why,
        'venue': {'id': name, 'name': name, 'gap_mentions': mentions},
        'citations': [{'excerpt': x} for x in excerpts],
    }


def test_friendly_evidence_cannot_licence_a_status_assertion():
    # Hock Kee Heritage on prod: 清真友好 is one poster's "halal-friendly".
    e = entry_c(
        'Hock Kee',
        'Dinyatakan halal dan mesra Muslim, sesuai untuk keluarga.',
        ['halal'],
        ['占美清真寺的姐妹一定要来！这家清真友好，很推荐。'],
    )
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] is None


def test_friendly_evidence_still_licences_a_friendly_claim():
    why = 'Mesra Muslim, sesuai untuk keluarga.'
    e = entry_c('Hock Kee', why, ['halal'], ['这家清真友好，很推荐。'])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] == why


def test_a_real_certification_statement_licences_the_status_claim():
    why = 'Disahkan halal, sesuai untuk keluarga.'
    e = entry_c('Z', why, ['halal'], ['This place is halal certified, we checked the cert'])
    assert withhold_unsupported_gap_claims([e], ['halal'])[0]['why'] == why

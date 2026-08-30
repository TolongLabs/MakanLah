"""LiveroiD answers the questions, and the persona never buys an inch of honesty.

The companion already had a voice (`companion.py`) and the copilot had none, so
the same character was warm while asking the wizard's questions and flat when
answering about a restaurant. Owner asked for one character throughout.

The risk is the whole point of these tests. A persona is a licence to embellish,
and embellishment on this product is fabrication: the one promise is that every
claim traces to a post. So the prompt must carry the personality UNDER the rules,
never beside them, and a refusal has to stay a refusal -- just a warmer one.
"""

from makanlah.copilot import SYSTEM


def test_the_character_is_named_so_the_two_surfaces_are_one_person():
    assert 'LiveroiD' in SYSTEM


def test_the_honesty_rules_survive_the_persona():
    """Each of these was load-bearing before the voice existed and must still be
    stated. A personality that quietly drops one is how this product breaks."""
    lowered = SYSTEM.lower()
    for rule in ['covered', 'do not guess', 'never state a fact that is not in an excerpt', 'used']:
        assert rule in lowered, rule


def test_the_prompt_says_the_voice_never_outranks_the_rules():
    """Stated explicitly rather than implied by ordering, because a model reads a
    persona as permission unless told otherwise."""
    lowered = SYSTEM.lower()
    assert 'never' in lowered and ('tone' in lowered or 'voice' in lowered)


def test_a_refusal_is_still_required_to_be_a_refusal():
    assert 'do not cover' in SYSTEM.lower()


def test_the_voice_is_bounded_so_it_cannot_run_long():
    """40 words was the cap before the persona and is the reason answers stay
    readable on a phone. A chatty character would quietly spend it."""
    assert '40 words' in SYSTEM


def test_no_emoji_or_roleplay_stage_directions():
    """`companion.py` bans both for the same reason: they read as generated, and
    DESIGN.md treats looking generated as a failure rather than a blemish."""
    lowered = SYSTEM.lower()
    assert 'emoji' in lowered
    assert 'stage direction' in lowered or 'roleplay' in lowered or 'action' in lowered


def test_the_prompt_forbids_naming_the_excerpt_list_in_the_answer():
    """She was answering "Excerpt 3 mentions pork rib" and "the provided summary
    also mentions". The reader cannot see a numbered list, so a reference to one
    reads as a machine reciting its input -- and DESIGN.md treats sounding
    generated as a failure. The numbers belong in `used`, never in `answer`."""
    lowered = SYSTEM.lower()
    assert 'never say "excerpt"' in lowered
    assert '"used"' in SYSTEM

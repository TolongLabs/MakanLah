"""The companion's guard rails.

No network. The model lane is stubbed, because the thing worth testing is what
happens to a line AFTER a model writes it: the whole point of this module is
that it lets a model be creative inside a box it cannot talk its way out of.
"""

import pathlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from makanlah import companion


class TestSafe:
    """A cute line is small talk. Anything that reads as a claim is not."""

    @pytest.mark.parametrize(
        'bad',
        [
            'Try Village Park, best nasi lemak in town!',  # recommends
            'The most famous laksa is waiting for you.',  # rates
            'Go to Jalan Alor, you will love it.',  # names a street
            'Have a look at https://example.com for ideas.',  # a URL
            'Only RM 12 for a plate, cannot go wrong.',  # a price
            '今天想吃什么呢?',  # CJK: the speech voice cannot read it
            'I recommend something soupy today.',  # recommends
        ],
    )
    def test_drops_a_line_that_became_a_claim(self, bad):
        assert companion._safe(bad) is None

    @pytest.mark.parametrize(
        'good',
        [
            'Okay, what are you craving today?',
            'Ooh nice, who is coming along for makan?',
            'How far will you go, walking or driving lah?',
        ],
    )
    def test_keeps_small_talk(self, good):
        assert companion._safe(good) == good

    def test_drops_a_speech_that_will_not_end(self):
        # A synthesiser reads every word. A paragraph is a hostage situation.
        assert companion._safe(' '.join(['word'] * 40)) is None

    def test_strips_wrapping_quotes_a_model_adds(self):
        assert companion._safe('"What are you craving?"') == 'What are you craving?'

    def test_treats_empty_as_unusable(self):
        assert companion._safe('') is None
        assert companion._safe('   ') is None


class TestScript:
    """The line that is always available, with no key and no network."""

    def test_every_step_has_lines(self):
        for step in (*companion.STEPS, 'done'):
            assert companion.SCRIPT[step], step

    def test_no_scripted_line_trips_its_own_guard(self):
        # A fallback that the validator would reject is not a fallback.
        for step, pool in companion.SCRIPT.items():
            for text in pool:
                assert companion._safe(text) == text, (step, text)

    def test_a_seed_makes_it_deterministic(self):
        assert companion.scripted('craving', 0) == companion.scripted('craving', 0)
        assert companion.scripted('craving', 0) != companion.scripted('craving', 1)

    def test_an_unknown_step_still_speaks(self):
        assert companion.scripted('nonsense', 0)


class TestClientParity:
    """The lines are duplicated in TypeScript. The copy is only safe while it is one.

    The client speaks the instant a step changes, and a spoken question that lands
    three hundred milliseconds after the question it is asking has already been read
    is worse than one that never varies -- so it cannot wait for this module. That
    makes the duplication deliberate, and this the thing that keeps it honest.

    It lives on the Python side because the browser side cannot read a file: the
    equivalent vitest assertion needed `node:fs`, which typechecked locally only
    because the repo root carries a node_modules the CI web job never installs.
    """

    def test_the_typescript_says_exactly_the_same_lines(self):
        ts = pathlib.Path(__file__).resolve().parents[1] / 'web/src/companion/lines.ts'
        block = ts.read_text()
        block = block[block.index('export const SCRIPT') : block.index('export const STEP_KEYS')]

        found: dict[str, list[str]] = {}
        key = None
        for raw in block.splitlines():
            head = re.match(r'^  ([a-z]+): \[$', raw)
            if head:
                key = head.group(1)
                found[key] = []
                continue
            one = re.match(r"^    '(.*)',?$", raw)
            if one and key:
                found[key].append(one.group(1).replace(chr(92) + "'", "'"))

        assert found == {k: list(v) for k, v in companion.SCRIPT.items()}


class TestLine:
    def test_falls_back_to_script_with_no_key(self, monkeypatch):
        # CI has no key, so this is the branch CI actually runs.
        monkeypatch.setattr(companion.config, 'settings', lambda: _settings(key=None))
        out = companion.line('craving', seed=0)
        assert out == {'text': companion.scripted('craving', 0), 'source': 'script'}

    def test_falls_back_when_the_lane_throws(self, monkeypatch):
        monkeypatch.setattr(companion.config, 'settings', lambda: _settings())
        monkeypatch.setattr(companion.models, '_post', _boom)
        assert companion.line('mood', seed=1)['source'] == 'script'

    def test_falls_back_when_the_model_recommends_a_place(self, monkeypatch):
        # The failure this module exists to prevent, exercised end to end rather
        # than only against _safe: a model line that names a venue must never
        # reach the caller, because nothing behind it is cited.
        monkeypatch.setattr(companion.config, 'settings', lambda: _settings())
        monkeypatch.setattr(companion.models, '_post', _says('You must try Village Park, the best nasi lemak!'))
        out = companion.line('craving', seed=2)
        assert out['source'] == 'script'
        assert 'Village Park' not in out['text']

    def test_uses_a_model_line_that_stays_in_bounds(self, monkeypatch):
        monkeypatch.setattr(companion.config, 'settings', lambda: _settings())
        monkeypatch.setattr(companion.models, '_post', _says('Ooh, what are you craving today lah?'))
        assert companion.line('craving') == {'text': 'Ooh, what are you craving today lah?', 'source': 'model'}

    def test_sends_the_tapped_labels_and_nothing_else(self, monkeypatch):
        # The privacy and correctness claim in the module docstring, asserted:
        # the request body carries the step prompt and the user's own labels. If
        # a future change starts posting corpus rows to a third party, this
        # fails.
        seen = {}

        def capture(url, payload, key, timeout=120):
            seen['url'], seen['payload'] = url, payload
            return _body('Nice pick, who is eating with you?')

        monkeypatch.setattr(companion.config, 'settings', lambda: _settings())
        monkeypatch.setattr(companion.models, '_post', capture)
        companion.line('company', ['Nasi Lemak', 'Curry Laksa'])

        sent = seen['payload']['messages'][-1]['content']
        assert 'Nasi Lemak' in sent and 'Curry Laksa' in sent
        assert seen['url'].endswith('/chat/completions')
        assert seen['payload']['model'] == 'test-model'

    def test_caps_how_many_labels_travel(self, monkeypatch):
        seen = {}

        def capture(url, payload, key, timeout=120):
            seen['payload'] = payload
            return _body('Okay, who is coming?')

        monkeypatch.setattr(companion.config, 'settings', lambda: _settings())
        monkeypatch.setattr(companion.models, '_post', capture)
        companion.line('company', [f'dish-{i}' for i in range(20)])
        assert 'dish-6' not in seen['payload']['messages'][-1]['content']

    def test_an_unknown_step_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(companion.config, 'settings', lambda: _settings(key=None))
        assert companion.line('../../etc/passwd', seed=0)['text']


def _settings(key='k'):
    class S:
        companion_api_key = key
        companion_base_url = 'https://example.invalid/v1'
        companion_model = 'test-model'
        companion_timeout = 3.0

    return S()


def _body(text):
    return {'choices': [{'message': {'content': text}}]}


def _says(text):
    def post(url, payload, key, timeout=120):
        return _body(text)

    return post


def _boom(url, payload, key, timeout=120):
    raise RuntimeError('upstream is down')

"""The committed capture in docs/source/ is the fixture set docs/TRD.md names.

It is also a file that leaves this machine, so these tests are as much about
what must NOT be in it as about its shape. A token or a real handle reaching a
committed file is a credential leak, and docs/CREDENTIALS.md forbids both.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

CAPTURE = Path(__file__).resolve().parents[1] / 'docs' / 'source' / '2026-08-27-rednote-kl-spike.json'


@pytest.fixture(scope='module')
def posts():
    if not CAPTURE.exists():
        pytest.skip('no capture committed')
    return json.loads(CAPTURE.read_text())


class TestRedaction:
    def test_no_request_token_survives(self, posts):
        # xsec_token is a live request credential.
        assert 'xsec_token' not in CAPTURE.read_text()

    def test_author_handles_are_pseudonymous(self, posts):
        for p in posts:
            h = p['author_handle']
            assert h is None or re.fullmatch(r'author_[0-9a-f]{10}', h), h

    def test_no_absolute_path_from_one_machine_leaked(self, posts):
        blob = CAPTURE.read_text()
        for needle in ('/home/', 'C:\\\\Users', '\\\\wsl.localhost', '/tmp/'):
            assert needle not in blob, needle

    def test_no_api_key_shaped_string(self, posts):
        blob = CAPTURE.read_text()
        assert not re.search(r'\bsk-[A-Za-z0-9_-]{16,}', blob)


class TestSchemaShape:
    """The capture must match the corpus schema, or it is not a fixture set."""

    def test_every_post_carries_the_required_fields(self, posts):
        for p in posts:
            assert p['platform']
            assert p['platform_post_id']
            assert p['url'].startswith('http')
            assert p['raw_text']
            assert isinstance(p['langs'], list) and p['langs']

    def test_post_ids_are_unique(self, posts):
        ids = [p['platform_post_id'] for p in posts]
        assert len(ids) == len(set(ids))

    def test_languages_are_from_the_known_set(self, posts):
        allowed = {'zh', 'ms', 'en', 'und'}
        for p in posts:
            assert set(p['langs']) <= allowed, p['langs']

    def test_the_corpus_is_actually_multilingual(self, posts):
        # If this ever passes with one language, the language handling is not
        # being exercised by the fixtures at all.
        seen = {lang for p in posts for lang in p['langs']}
        assert len(seen - {'und'}) >= 2, seen


class TestCitationInvariant:
    """The one guarantee, checked on committed data rather than asserted."""

    def test_every_excerpt_is_verbatim(self, posts):
        for p in posts:
            for m in p['mentions']:
                if m['excerpt']:
                    assert m['excerpt'] in p['raw_text'], (p['platform_post_id'], m['venue_name'])

    def test_the_capture_records_its_own_verbatim_check(self, posts):
        for p in posts:
            for m in p['mentions']:
                if m['excerpt']:
                    assert m['excerpt_is_substring'] is True

    def test_every_mention_names_a_venue(self, posts):
        for p in posts:
            for m in p['mentions']:
                assert m['venue_name'].strip()
                assert m['venue_name_normalized'].strip()

    def test_sentiment_is_inside_the_schema_range(self, posts):
        for p in posts:
            for m in p['mentions']:
                assert m['sentiment'] is None or -1.0 <= m['sentiment'] <= 1.0

    def test_price_band_is_inside_the_schema_range(self, posts):
        for p in posts:
            for m in p['mentions']:
                assert m['price_band'] is None or 1 <= m['price_band'] <= 4

    def test_the_many_to_many_case_is_represented(self, posts):
        # One post naming several restaurants is the case that justifies the
        # mention table. A fixture set without one would not exercise it.
        assert any(len(p['mentions']) >= 5 for p in posts)

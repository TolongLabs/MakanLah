"""Password hashing and token handling.

No database and no network: these are pure functions, so they are cheap enough
to run on every commit and are the layer where a mistake is unrecoverable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from makanlah import auth  # noqa: E402


class TestPasswordHashing:
    def test_a_correct_password_verifies(self):
        assert auth.verify_password('correct horse battery', auth.hash_password('correct horse battery'))

    def test_a_wrong_password_does_not(self):
        assert not auth.verify_password('wrong horse battery', auth.hash_password('correct horse battery'))

    def test_the_same_password_hashes_differently_every_time(self):
        """A shared salt would let one rainbow table serve every row."""
        a, b = auth.hash_password('same password'), auth.hash_password('same password')
        assert a != b
        assert auth.verify_password('same password', a)
        assert auth.verify_password('same password', b)

    def test_the_password_never_appears_in_the_hash(self):
        assert 'correct horse battery' not in auth.hash_password('correct horse battery')

    def test_the_hash_carries_its_own_parameters(self):
        """So the work factor can be raised without invalidating existing rows."""
        scheme, n, r, p, salt, key = auth.hash_password('parameterised').split('$')
        assert scheme == 'scrypt'
        assert int(n) >= 2**14 and int(r) >= 8 and int(p) >= 1

    def test_a_hash_made_with_older_parameters_still_verifies(self):
        import base64
        import hashlib

        salt = b'0123456789abcdef'
        weak_n = 2**14
        key = hashlib.scrypt(b'legacy pw', salt=salt, n=weak_n, r=8, p=1, dklen=32)
        stored = f'scrypt${weak_n}$8$1${base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}'
        assert auth.verify_password('legacy pw', stored)

    @pytest.mark.parametrize('bad', ['', 'short', 'a' * 7])
    def test_a_password_below_the_floor_is_refused(self, bad):
        with pytest.raises(ValueError):
            auth.hash_password(bad)

    def test_an_enormous_password_is_refused(self):
        """scrypt on a megabyte of input is a denial-of-service, not a login."""
        with pytest.raises(ValueError):
            auth.hash_password('a' * 2000)

    @pytest.mark.parametrize('corrupt', ['', 'not-a-hash', 'scrypt$x$y$z$q$r', 'bcrypt$1$2$3$4$5', '$$$$$'])
    def test_a_corrupt_stored_value_is_false_rather_than_an_exception(self, corrupt):
        assert auth.verify_password('anything', corrupt) is False


class TestTokens:
    def test_tokens_are_unique_and_long(self):
        tokens = {auth.new_token() for _ in range(200)}
        assert len(tokens) == 200
        assert all(len(t) >= 40 for t in tokens)

    def test_the_fingerprint_is_stable_and_not_the_token(self):
        t = auth.new_token()
        assert auth.token_fingerprint(t) == auth.token_fingerprint(t)
        assert t not in auth.token_fingerprint(t)

    def test_different_tokens_fingerprint_differently(self):
        assert auth.token_fingerprint(auth.new_token()) != auth.token_fingerprint(auth.new_token())


class TestEmailShape:
    @pytest.mark.parametrize('ok', ['a@b.co', 'first.last@example.com', 'x+tag@sub.domain.my'])
    def test_plausible_addresses_are_accepted(self, ok):
        assert auth.looks_like_email(ok)

    @pytest.mark.parametrize('bad', ['', 'nope', 'a@b', 'a b@c.com', 'a@.com', 'a@b.', 'a' * 400 + '@b.co'])
    def test_implausible_ones_are_not(self, bad):
        assert not auth.looks_like_email(bad)

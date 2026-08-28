"""Password hashing, opaque session tokens, and the shared guest identity.

No new dependency: `hashlib.scrypt` is memory-hard and in the standard library,
so the API image does not grow a C extension to hash a password. Parameters are
stored INSIDE each hash, so the work factor can be raised later without
invalidating hashes already in the database.

Nothing here logs, returns or formats a secret. A password never leaves this
module, and a token is returned exactly once -- at issue -- and stored hashed.
"""

import base64
import hashlib
import hmac
import os
import secrets

# 128 * N * r bytes per hash: 32 MB at these parameters. Raised by bumping N,
# which old hashes survive because each carries the N it was made with.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32
SALT_BYTES = 16


# OpenSSL caps scrypt memory at 32 MB by default, which these parameters sit
# exactly on, so it must be passed explicitly or every hash raises
# "memory limit exceeded". Computed from the parameters in play, with headroom,
# so verifying a hash made at a higher work factor still works.
def _maxmem(n: int, r: int) -> int:
    return 128 * n * r * 2


TOKEN_BYTES = 32
GUEST_EMAIL = 'guest@makanlah.local'

MIN_PASSWORD = 8
MAX_PASSWORD = 1024  # a megabyte password is a denial-of-service, not a login


def hash_password(password: str) -> str:
    """`scrypt$n$r$p$salt$key`, all base64. Self-describing so it can be upgraded."""
    if not isinstance(password, str) or not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise ValueError(f'password must be between {MIN_PASSWORD} and {MAX_PASSWORD} characters')
    salt = os.urandom(SALT_BYTES)
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=DKLEN,
        maxmem=_maxmem(SCRYPT_N, SCRYPT_R),
    )
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f'scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt)}${b64(key)}'


def verify_password(password: str, stored: str) -> bool:
    """Constant-time, and never raises on a malformed stored value.

    A parse error here means a corrupt row, not a valid login, so it returns
    False rather than propagating and turning a bad row into a 500.
    """
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split('$')
        if scheme != 'scrypt':
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(key_b64)
        got = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_maxmem(int(n), int(r)),
        )
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(got, expected)


def new_token() -> str:
    """The value the client keeps. Returned once and never stored in this form."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_fingerprint(token: str) -> str:
    """What the database stores.

    A plain SHA-256 rather than a KDF, deliberately: a 256-bit random token has
    no guessable structure, so there is nothing for a slow hash to protect. The
    reason to hash at all is that a leaked database must not yield live sessions.
    """
    return hashlib.sha256((token or '').encode()).hexdigest()


def looks_like_email(value: str) -> bool:
    """Deliberately permissive. Rejecting valid addresses is a worse failure than
    accepting an odd one, and delivery is not something this app does."""
    v = (value or '').strip()
    if not v or len(v) > 320 or ' ' in v:
        return False
    local, sep, domain = v.rpartition('@')
    return bool(sep and local and '.' in domain and not domain.startswith('.') and not domain.endswith('.'))

"""Salted, adaptive stdlib scrypt hashes; no plaintext password persistence."""

import hashlib
import hmac
import secrets

SCRYPT_N = 2**14


def hash_password(password: str) -> str:
    salt = secrets.token_hex(24)
    derived = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=SCRYPT_N, r=8, p=1, dklen=64
    )
    return f"scrypt${SCRYPT_N}$8$1${salt}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        method, n, r, p, salt, expected = encoded.split("$")
        if method != "scrypt" or (int(n), int(r), int(p)) != (SCRYPT_N, 8, 1):
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=SCRYPT_N, r=8, p=1, dklen=64
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(session_token: str) -> str:
    # Only the server can read the HttpOnly session cookie. The token is returned by /me
    # so a reloaded browser can restore its CSRF header without storing session credentials.
    return digest("mts-csrf-v1:" + session_token)

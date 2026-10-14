"""Application-level Fernet protection of private text/JSON at rest.

The key is external process configuration, never a DB default or an automatic fallback.
Metadata used to route jobs/authorize users remains queryable.
"""

import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON, Text
from sqlalchemy.types import TypeDecorator

from mts_backend.core.business import BusinessError
from mts_backend.core.config import get_settings

PREFIX = "fernet:v1:"


@lru_cache(maxsize=4)
def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError):
        raise BusinessError(
            503, "encryption_unconfigured", "Storage encryption key is unavailable."
        ) from None


def encryption_cipher() -> Fernet:
    key = get_settings().data_encryption_key.get_secret_value()
    if not key:
        raise BusinessError(
            503, "encryption_unconfigured", "Storage encryption key is unavailable."
        )
    return _fernet(key)


def encrypt_text(value: str) -> str:
    return PREFIX + encryption_cipher().encrypt(value.encode()).decode("ascii")


def decrypt_text(value: str) -> str:
    try:
        if not isinstance(value, str) or not value.startswith(PREFIX):
            raise InvalidToken
        return encryption_cipher().decrypt(value[len(PREFIX) :].encode()).decode()
    except (InvalidToken, UnicodeError):
        raise BusinessError(
            503, "encrypted_data_unavailable", "Encrypted data cannot be opened."
        ) from None


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_text(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_text(value)


class EncryptedJSON(TypeDecorator):
    # JSON stores a ciphertext string, preserving the original SQL column type.
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(decrypt_text(value))

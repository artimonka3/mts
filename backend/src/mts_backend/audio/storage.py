"""Authenticated encryption for local private audio storage; key is external."""

import os
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from mts_backend.core.business import BusinessError


class AudioStorage:
    def __init__(self, settings):
        key = settings.audio_encryption_key.get_secret_value()
        if not key:
            raise BusinessError(
                503, "storage_not_configured", "Audio encryption is not configured."
            )
        try:
            self.cipher = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise BusinessError(
                503, "storage_not_configured", "Audio encryption is not configured."
            ) from None
        self.root = Path(settings.audio_storage_path)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, key):
        try:
            safe = str(UUID(key))
        except ValueError:
            raise BusinessError(404, "not_found", "Audio not found.") from None
        return self.root / (safe + ".enc")

    def write(self, key, content):
        path = self.path(key)
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(self.cipher.encrypt(content))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, key):
        try:
            return self.cipher.decrypt(self.path(key).read_bytes())
        except (FileNotFoundError, InvalidToken):
            raise BusinessError(410, "source_expired", "Audio is unavailable.") from None

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

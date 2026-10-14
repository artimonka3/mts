"""Audio ciphertext integrity, path boundaries and decoder availability."""

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from mts_backend.audio import probe
from mts_backend.audio.storage import AudioStorage
from mts_backend.core.business import BusinessError, uid


def test_encrypted_audio_tamper_and_private_file_mode(tmp_path):
    storage = AudioStorage(
        SimpleNamespace(
            audio_encryption_key=SecretStr(Fernet.generate_key().decode()),
            audio_storage_path=str(tmp_path),
        )
    )
    key, clear = uid(), b"private recording content"
    storage.write(key, clear)
    path = storage.path(key)
    assert clear not in path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert storage.read(key) == clear
    encrypted = bytearray(path.read_bytes())
    encrypted[len(encrypted) // 2] ^= 1
    path.write_bytes(encrypted)
    with pytest.raises(BusinessError) as exc:
        storage.read(key)
    assert exc.value.code == "source_expired"
    storage.delete(key)
    assert not path.exists()


def test_audio_path_cannot_escape_private_root(tmp_path):
    storage = AudioStorage(
        SimpleNamespace(
            audio_encryption_key=SecretStr(Fernet.generate_key().decode()),
            audio_storage_path=str(tmp_path),
        )
    )
    with pytest.raises(BusinessError) as exc:
        storage.read("../../secret")
    assert exc.value.code == "not_found"


@pytest.mark.asyncio
async def test_unavailable_decoder_is_explicit_not_fake_success(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.shutil, "which", lambda _: None)
    with pytest.raises(BusinessError) as exc:
        await probe.prepare(tmp_path / "input", tmp_path / "output", SimpleNamespace())
    assert exc.value.code == "decoder_unavailable"

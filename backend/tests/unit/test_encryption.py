import pytest
from cryptography.fernet import Fernet

from mts_backend.core.business import BusinessError
from mts_backend.core.config import get_settings
from mts_backend.db.encryption import EncryptedJSON, decrypt_text, encrypt_text, encryption_cipher


@pytest.fixture
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("MTS_DATA_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def test_private_text_and_json_roundtrip_random_ciphertext(encryption_key):
    text = "Отправить КП до пятницы"
    first, second = encrypt_text(text), encrypt_text(text)
    assert first != second
    assert text not in first
    assert decrypt_text(first) == text
    codec = EncryptedJSON()
    payload = {"text": text, "unknown": None, "roles": ["manager"]}
    stored = codec.process_bind_param(payload, None)
    assert isinstance(stored, str) and text not in stored
    assert codec.process_result_value(stored, None) == payload


def test_ciphertext_tampering_and_plaintext_are_rejected(encryption_key):
    with pytest.raises(BusinessError, match="encrypted_data_unavailable"):
        decrypt_text("clear text from an old unconverted database")
    with pytest.raises(BusinessError, match="encrypted_data_unavailable"):
        decrypt_text(encrypt_text("private")[:-6] + "broken")


def test_missing_key_has_explicit_no_fallback(monkeypatch):
    monkeypatch.setenv("MTS_DATA_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(BusinessError) as error:
        encryption_cipher()
    assert error.value.status == 503
    assert error.value.code == "encryption_unconfigured"
    get_settings.cache_clear()

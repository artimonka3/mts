from mts_backend.auth.passwords import csrf_token, digest, hash_password, verify_password


def test_scrypt_hashes_salt_and_detect_wrong_password():
    first = hash_password("a safe test password")
    second = hash_password("a safe test password")
    assert first != second
    assert "a safe test password" not in first
    assert verify_password("a safe test password", first)
    assert not verify_password("incorrect", first)
    assert not verify_password("incorrect", "malformed")


def test_csrf_separate_digest_can_be_restored_without_stored_cookie():
    raw = "an opaque session value"
    csrf = csrf_token(raw)
    assert csrf != raw
    assert digest(csrf) != digest(raw)
    assert csrf == csrf_token(raw)

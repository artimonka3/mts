from fastapi.testclient import TestClient

from mts_backend.main import create_app


def test_oversized_declared_body_rejected_before_endpoint(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/login", content=b"{}", headers={"Content-Length": str(1048577)}
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_oversized_chunked_body_without_declared_length(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=iter([b'{"login":"', b"x" * 1048577, b'","password":"x"}']),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"

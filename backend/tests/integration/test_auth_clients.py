"""Small MVP foundation checks; additive data in a dedicated _test PostgreSQL database."""

import os
import secrets
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from mts_backend.auth.passwords import hash_password
from mts_backend.core.config import Settings
from mts_backend.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def foundation():
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set MTS_TEST_DATABASE_URL to a dedicated _test PostgreSQL database.")
    parsed = make_url(url)
    assert (parsed.database or "").endswith("_test"), "Refuse integration tests on normal database."
    sync = parsed.set(drivername="postgresql").render_as_string(hide_password=False)
    password = secrets.token_hex(10)
    org = str(uuid4())
    users = [(str(uuid4()), "test-" + uuid4().hex) for _ in range(2)]
    with psycopg.connect(sync) as db:
        db.execute(
            "INSERT INTO organizations(id,name,status,created_at) VALUES(%s,%s,'active',now())",
            (org, "test foundation"),
        )
        for identifier, login in users:
            db.execute(
                "INSERT INTO users(id,organization_id,login,display_name,password_hash,"
                "is_active,created_at) "
                "VALUES(%s,%s,%s,%s,%s,true,now())",
                (identifier, org, login, "Test user", hash_password(password)),
            )
    settings = Settings(
        database_url=url,
        environment="test",
        cors_origins=["http://testserver"],
        auth_login_max_attempts=50,
        _env_file=None,
    )
    yield create_app(settings), users, password, sync


def sign_in(client, login, password):
    response = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}


def test_login_csrf_logout_and_owner_boundaries(foundation):
    app, users, password, _ = foundation
    with TestClient(app) as first, TestClient(create_app(app.state.settings)) as second:
        assert first.get("/api/v1/me").status_code == 401
        headers = sign_in(first, users[0][1], password)
        assert first.get("/api/v1/me").json()["csrf_token"] == headers["X-CSRF-Token"]
        payload = {"display_name": "Клиент", "contacts": {"email": "demo@example.test"}}
        assert first.post("/api/v1/clients", json=payload).status_code == 403
        denied = {**headers, "Origin": "https://evil.example"}
        assert first.post("/api/v1/clients", json=payload, headers=denied).status_code == 403
        response = first.post("/api/v1/clients", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        card = response.json()
        assert card["version"] == 1
        assert "owner_id" not in card
        sign_in(second, users[1][1], password)
        assert second.get(f"/api/v1/clients/{card['id']}").status_code == 404
        assert second.get("/api/v1/clients").json()["total"] == 0
        response = first.patch(
            f"/api/v1/clients/{card['id']}",
            headers=headers,
            json={"expected_version": 1, "notes": "обновлено"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["version"] == 2
        assert (
            first.patch(
                f"/api/v1/clients/{card['id']}",
                headers=headers,
                json={"expected_version": 1, "notes": "stale"},
            ).status_code
            == 409
        )
        assert (
            first.patch(
                f"/api/v1/clients/{card['id']}",
                headers=headers,
                json={"expected_version": 2, "display_name": None},
            ).status_code
            == 422
        )
        assert first.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert first.get("/api/v1/me").status_code == 401


def test_login_throttle_is_persistent_and_secrets_not_stored(foundation):
    app, users, password, sync = foundation
    # Different fresh client/IP bucket avoids failures from unrelated checks.
    app.state.settings.auth_login_max_attempts = 2
    with TestClient(app, client=("rate-test-" + uuid4().hex, 50000)) as client:
        login = users[0][1]
        for _ in range(2):
            response = client.post("/api/v1/auth/login", json={"login": login, "password": "wrong"})
            assert response.status_code == 401
        response = client.post("/api/v1/auth/login", json={"login": login, "password": password})
        assert response.status_code == 429
        assert response.headers["Retry-After"]
    with psycopg.connect(sync) as db:
        rows = db.execute("SELECT bucket FROM login_attempts").fetchall()
        assert rows and all(len(row[0]) == 64 for row in rows)
        assert not any(login in row[0] for row in rows)

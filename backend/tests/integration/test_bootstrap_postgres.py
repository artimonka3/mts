"""Stage 2 acceptance checks against a disposable PostgreSQL database."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from mts_backend.core.config import Settings
from mts_backend.main import create_app

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def postgres_url():
    value = os.environ.get("MTS_BOOTSTRAP_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set MTS_BOOTSTRAP_TEST_DATABASE_URL to a disposable database ending in _test.")
    parsed = make_url(value)
    if parsed.drivername != "postgresql+psycopg" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Integration tests require a PostgreSQL database name ending in _test.")
    connection_url = parsed.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(connection_url) as connection:
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        if {row[0] for row in tables} - {"alembic_version"}:
            pytest.fail("Refusing to migrate a database containing business tables.")
    return value


def command_env(url):
    return {
        **os.environ,
        "MTS_DATABASE_URL": url,
        "MTS_ENVIRONMENT": "test",
        "MTS_WORKER_POLL_SECONDS": "0.1",
        "PYTHONPATH": str(BACKEND / "src"),
    }


def alembic(url, *arguments):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND,
        env=command_env(url),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, "Alembic failed; inspect the disposable test environment."
    return result


@pytest.fixture
def migrated(postgres_url):
    alembic(postgres_url, "upgrade", "head")
    yield postgres_url
    alembic(postgres_url, "upgrade", "head")


def test_api_and_worker_use_real_migrated_database(migrated):
    settings = Settings(database_url=migrated, environment="test", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "database": "ok",
            "schema": "0003_encrypted_metadata",
        }
        assert client.get("/api/v1/capabilities").json()["processing"]["llm"] == "disabled"
    result = subprocess.run(
        [sys.executable, "-m", "mts_backend.worker", "--once"],
        cwd=BACKEND,
        env=command_env(migrated),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert migrated not in output
    password = make_url(migrated).password
    if password:
        assert password not in output
    records = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    assert any(
        record.get("event") == "worker_heartbeat" and record.get("ready") for record in records
    )


def test_api_and_worker_reject_unmigrated_database(migrated):
    alembic(migrated, "downgrade", "base")
    with TestClient(create_app(Settings(database_url=migrated, _env_file=None))) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "service_not_ready"
        assert migrated not in response.text
    result = subprocess.run(
        [sys.executable, "-m", "mts_backend.worker", "--once"],
        cwd=BACKEND,
        env=command_env(migrated),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 1


def test_api_liveness_survives_unreachable_postgres(postgres_url):
    unreachable = (
        make_url(postgres_url).set(host="127.0.0.1", port=1).render_as_string(hide_password=False)
    )
    settings = Settings(database_url=unreachable, db_connect_timeout_seconds=1, _env_file=None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert unreachable not in response.text


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGTERM acceptance check")
def test_worker_stops_cleanly_on_sigterm(migrated, tmp_path):
    log_path = tmp_path / "worker.jsonl"
    with log_path.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "mts_backend.worker"],
            cwd=BACKEND,
            env=command_env(migrated),
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while "worker_heartbeat" not in log_path.read_text():
                assert process.poll() is None, "Worker exited before its first heartbeat."
                assert time.monotonic() < deadline, "Worker did not become ready."
                time.sleep(0.05)
            process.terminate()
            assert process.wait(timeout=5) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert "worker_stopped" in log_path.read_text()


def test_migration_supports_offline_sql(postgres_url):
    result = alembic(postgres_url, "upgrade", "head", "--sql")
    assert "alembic_version" in result.stdout
    assert "0003_encrypted_metadata" in result.stdout
    assert postgres_url not in result.stdout + result.stderr

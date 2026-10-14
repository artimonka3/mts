from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from mts_backend.main import create_app


def test_liveness_and_capabilities_do_not_check_database(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        checker = AsyncMock(side_effect=AssertionError("Database must not be used"))
        app.state.readiness_checker = checker
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/api/v1/capabilities").json() == {
            "stage": 13,
            "processing": {"asr": "disabled", "diarization": "disabled", "llm": "disabled"},
            "business_api": "mvp",
            "analysis_modes": ["known_demo", "manual"],
            "accuracy": "not_measured",
        }
        checker.assert_not_awaited()


def test_readiness_success_checks_dependency(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        checker = AsyncMock(return_value=True)
        app.state.readiness_checker = checker
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "database": "ok",
            "schema": "0003_encrypted_metadata",
        }
        checker.assert_awaited_once_with()


def test_readiness_failure_has_safe_error_and_request_id(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.readiness_checker = AsyncMock(return_value=False)
        response = client.get("/health/ready", headers={"X-Request-ID": "demo-123"})
        assert response.status_code == 503
        assert response.headers["X-Request-ID"] == "demo-123"
        assert response.json() == {
            "error": {
                "code": "service_not_ready",
                "message": "Service is not ready.",
                "request_id": "demo-123",
                "details": [],
            }
        }
        assert "unit-secret" not in response.text


def test_unexpected_error_does_not_echo_secret_or_url(settings):
    app = create_app(settings)

    @app.get("/test/failure")
    async def failure():
        raise RuntimeError("password=unit-secret; https://private-host/private-resource")

    with TestClient(app) as client:
        response = client.get("/test/failure?token=private-token")
        assert response.status_code == 500
        error = response.json()["error"]
        assert error["code"] == "internal_error"
        assert error["request_id"] == response.headers["X-Request-ID"]
        for sensitive in ("unit-secret", "private-host", "private-token"):
            assert sensitive not in response.text


def test_http_error_detail_is_sanitized(settings):
    app = create_app(settings)

    @app.get("/test/private-error")
    async def private_error():
        raise HTTPException(403, "private exception diagnostics")

    with TestClient(app) as client:
        response = client.get("/test/private-error")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
        assert "private exception diagnostics" not in response.text


def test_request_validation_does_not_echo_input(settings):
    app = create_app(settings)

    @app.get("/test/validation")
    async def validate(count: int):
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/test/validation?count=secret-input")
        assert response.status_code == 422
        assert response.json()["error"]["details"] == [
            {"location": ["query", "count"], "type": "int_parsing"}
        ]
        assert "secret-input" not in response.text


def test_unknown_routes_and_disabled_docs(settings):
    with TestClient(create_app(settings)) as client:
        for path in ("/unimplemented", "/docs", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "not_found"


def test_invalid_request_id_is_replaced(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "secret value with spaces"})
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 32
        int(request_id, 16)


def test_method_error_preserves_allow_header(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/health/live")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"
        assert "GET" in response.headers["Allow"]


def test_cors_allows_only_explicit_origin_with_credentials(settings):
    settings = settings.model_copy(
        update={
            "cors_origins": ["http://localhost:5173"],
            "cors_allow_credentials": True,
        }
    )
    with TestClient(create_app(settings)) as client:
        allowed = client.options(
            "/health/live",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert allowed.headers["Access-Control-Allow-Credentials"] == "true"
        denied = client.get("/health/live", headers={"Origin": "https://untrusted.example"})
        assert "Access-Control-Allow-Origin" not in denied.headers
        denied_preflight = client.options(
            "/health/live",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert denied_preflight.status_code == 400
        assert denied_preflight.json()["error"]["code"] == "cors_request_denied"
        assert "Access-Control-Allow-Origin" not in denied_preflight.headers


def test_cors_is_present_on_unexpected_error(settings):
    settings = settings.model_copy(update={"cors_origins": ["http://localhost:5173"]})
    app = create_app(settings)

    @app.get("/test/failure")
    async def failure():
        raise RuntimeError("private diagnostics")

    with TestClient(app) as client:
        response = client.get("/test/failure", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 500
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_openapi_documents_readiness_success_and_safe_failure(settings):
    spec = create_app(settings).openapi()
    responses = spec["paths"]["/health/ready"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadyResponse"
    }
    assert responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }

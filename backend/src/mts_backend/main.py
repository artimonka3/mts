"""FastAPI factory. Importing the module does not open a database connection."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from mts_backend.agreements.routes import router as agreements_router
from mts_backend.analysis.routes import router as analysis_router
from mts_backend.api.health import router
from mts_backend.auth.routes import router as auth_router
from mts_backend.calls.routes import router as calls_router
from mts_backend.clients.routes import router as clients_router
from mts_backend.core.business import BusinessError, business_error_handler
from mts_backend.core.config import Settings, get_settings
from mts_backend.core.errors import (
    error_response,
    http_exception_handler,
    make_request_id,
    validation_exception_handler,
)
from mts_backend.core.limits import BodyLimitMiddleware
from mts_backend.core.logging import configure_logging, log_event
from mts_backend.dashboard.routes import router as dashboard_router
from mts_backend.db.readiness import build_engine, check_readiness
from mts_backend.tasks.routes import router as tasks_router
from mts_backend.transcripts.routes import router as transcripts_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings)
        application.state.engine = engine
        application.state.readiness_checker = partial(
            check_readiness, engine, settings.db_connect_timeout_seconds
        )
        log_event("api_started")
        try:
            yield
        finally:
            await engine.dispose()
            log_event("api_stopped")

    application = FastAPI(
        title="MTS conversation assistant backend",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    application.state.settings = settings
    application.add_middleware(BodyLimitMiddleware, upload_max_bytes=settings.upload_max_bytes)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "Idempotency-Key",
            "If-Match",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = make_request_id(request.headers.get("X-Request-ID"))
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "request_failed",
                level=logging.ERROR,
                request_id=request.state.request_id,
                method=request.method,
                status_code=500,
            )
            response = error_response(request, 500, "internal_error", "An internal error occurred.")
            # This middleware surrounds CORSMiddleware; include CORS on safe error responses too.
            origin = request.headers.get("Origin")
            if origin in settings.cors_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Vary"] = "Origin"
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                if settings.cors_allow_credentials:
                    response.headers["Access-Control-Allow-Credentials"] = "true"
        if (
            response.status_code == 400
            and request.method == "OPTIONS"
            and "Origin" in request.headers
            and "Access-Control-Request-Method" in request.headers
        ):
            cors_response = error_response(
                request, 400, "cors_request_denied", "CORS request is not allowed."
            )
            for header, value in response.headers.items():
                if header.lower().startswith("access-control-") or header.lower() == "vary":
                    cors_response.headers[header] = value
            response = cors_response
        response.headers["X-Request-ID"] = request.state.request_id
        log_event(
            "request_completed",
            request_id=request.state.request_id,
            method=request.method,
            status_code=response.status_code,
        )
        return response

    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(BusinessError, business_error_handler)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(clients_router)
    for business_router in (
        calls_router,
        transcripts_router,
        analysis_router,
        agreements_router,
        tasks_router,
        dashboard_router,
    ):
        application.include_router(business_router)
    return application


app = create_app()

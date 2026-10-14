"""Liveness is independent of database connectivity."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from mts_backend.api.schemas import (
    CapabilitiesResponse,
    DisabledProcessing,
    LiveResponse,
    ReadyResponse,
)
from mts_backend.core.errors import ErrorEnvelope, error_response
from mts_backend.db.readiness import EXPECTED_SCHEMA_REVISION

router = APIRouter()


@router.get("/health/live", tags=["health"], response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get(
    "/health/ready",
    tags=["health"],
    response_model=ReadyResponse,
    responses={503: {"model": ErrorEnvelope, "description": "Database or schema is not ready."}},
)
async def ready(request: Request) -> ReadyResponse | JSONResponse:
    if not await request.app.state.readiness_checker():
        return error_response(request, 503, "service_not_ready", "Service is not ready.")
    return ReadyResponse(schema=EXPECTED_SCHEMA_REVISION)


@router.get("/api/v1/capabilities", tags=["system"], response_model=CapabilitiesResponse)
async def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(processing=DisabledProcessing())

"""Public error responses do not include exception text or input values."""

import re
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ErrorPayload(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


def make_request_id(value: str | None) -> str:
    return value if value and REQUEST_ID_PATTERN.fullmatch(value) else uuid4().hex


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorPayload(
                code=code, message=message, request_id=request_id, details=details or []
            )
        ).model_dump(),
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    errors = {
        400: ("bad_request", "Invalid request."),
        401: ("unauthorized", "Authentication is required."),
        403: ("forbidden", "Access is denied."),
        404: ("not_found", "Resource not found."),
        405: ("method_not_allowed", "Method is not allowed."),
        409: ("conflict", "Request conflicts with the current state."),
        413: ("payload_too_large", "Request exceeds size limit."),
        422: ("validation_error", "Request validation failed."),
        429: ("too_many_requests", "Too many requests."),
        503: ("service_unavailable", "Service is temporarily unavailable."),
    }
    code, message = errors.get(exc.status_code, ("request_failed", "Request failed."))
    response = error_response(request, exc.status_code, code, message)
    if exc.status_code == 405 and exc.headers:
        allowed_methods = exc.headers.get("Allow") or exc.headers.get("allow")
        if allowed_methods:
            response.headers["Allow"] = allowed_methods
    return response


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [{"location": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
    return error_response(request, 422, "validation_error", "Request validation failed.", details)

"""Session authentication and persistent account/IP login throttling."""

import asyncio
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.auth.dependencies import allowed_origin, current_user
from mts_backend.auth.passwords import csrf_token, digest, hash_password, verify_password
from mts_backend.core.business import utcnow
from mts_backend.core.errors import error_response
from mts_backend.db.models import LoginAttempt, Session, User
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["authentication"])
Db = Annotated[AsyncSession, Depends(get_db)]
SignedIn = Annotated[User, Depends(current_user)]
DUMMY_HASH = hash_password("unusable-placeholder-password")


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)

    @field_validator("login")
    @classmethod
    def canonical_login(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Login is empty.")
        return value


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "organization_id": user.organization_id,
        "login": user.login,
        "display_name": user.display_name,
    }


async def login_is_limited(
    db: AsyncSession, request: Request, login: str
) -> tuple[bool, list[str]]:
    settings = request.app.state.settings
    address = request.client.host if request.client else "unknown"
    buckets = sorted([digest("account:" + login), digest("address:" + address)])
    # Serialize same account/address attempts even across API instances.
    for bucket in buckets:
        key = int(bucket[:16], 16)
        if key >= 2**63:
            key -= 2**64
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    cutoff = utcnow() - timedelta(seconds=settings.auth_login_window_seconds)
    await db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
    for bucket in buckets:
        attempts = await db.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.bucket == bucket, LoginAttempt.attempted_at >= cutoff)
        )
        if attempts >= settings.auth_login_max_attempts:
            return True, buckets
    return False, buckets


@router.post("/auth/login")
async def login(body: LoginInput, request: Request, response: Response, db: Db):
    allowed_origin(request, required=False)
    limited, buckets = await login_is_limited(db, request, body.login)
    if limited:
        result = error_response(request, 429, "rate_limit_exceeded", "Please try signing in later.")
        result.headers["Retry-After"] = str(request.app.state.settings.auth_login_window_seconds)
        return result
    user = await db.scalar(select(User).where(User.login == body.login))
    valid = await asyncio.to_thread(
        verify_password, body.password, user.password_hash if user else DUMMY_HASH
    )
    if not valid or user is None or not user.is_active:
        db.add_all([LoginAttempt(bucket=bucket) for bucket in buckets])
        # Return instead of raising so request transaction retains throttling attempts.
        return error_response(request, 401, "invalid_credentials", "Invalid login or password.")
    raw = secrets.token_urlsafe(48)
    csrf = csrf_token(raw)
    settings = request.app.state.settings
    old = request.cookies.get(settings.session_cookie_name)
    if old:
        previous = await db.scalar(select(Session).where(Session.token_digest == digest(old)))
        if previous:
            previous.revoked_at = utcnow()
    db.add(
        Session(
            user_id=user.id,
            token_digest=digest(raw),
            csrf_digest=digest(csrf),
            expires_at=utcnow() + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    await db.flush()
    response.set_cookie(
        settings.session_cookie_name,
        raw,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"user": public_user(user), "csrf_token": csrf}


@router.get("/me")
async def me(request: Request, user: SignedIn):
    return {**public_user(user), "csrf_token": request.state.csrf_token}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, user: SignedIn):
    request.state.auth_session.revoked_at = utcnow()
    response = Response(status_code=204)
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=request.app.state.settings.session_cookie_secure,
        samesite="lax",
    )
    return response

"""Opaque sessions plus owner-only business dependencies."""

import hmac
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.auth.passwords import csrf_token, digest
from mts_backend.core.business import BusinessError, utcnow
from mts_backend.db.models import Session, User
from mts_backend.db.session import get_db


def allowed_origin(request: Request, *, required: bool) -> None:
    origin = request.headers.get("origin")
    if origin is None and not required:
        return
    base = urlsplit(str(request.base_url))
    same_origin = f"{base.scheme}://{base.netloc}"
    if not origin or origin not in {*request.app.state.settings.cors_origins, same_origin}:
        raise BusinessError(403, "csrf_origin_denied", "Request origin is not allowed.")


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> User:
    settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw or len(raw) > 256:
        raise BusinessError(401, "authentication_required", "Sign in is required.")
    session = await db.scalar(
        select(Session).where(
            Session.token_digest == digest(raw),
            Session.revoked_at.is_(None),
            Session.expires_at > utcnow(),
        )
    )
    if session is None:
        raise BusinessError(401, "authentication_required", "Session has expired.")
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise BusinessError(401, "authentication_required", "Sign in is required.")
    request.state.auth_session = session
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        allowed_origin(request, required=True)
        token = csrf_header or ""
        if len(token) > 256 or not hmac.compare_digest(digest(token), session.csrf_digest):
            raise BusinessError(403, "csrf_token_invalid", "CSRF token is required.")
    request.state.csrf_token = csrf_token(raw)
    return user

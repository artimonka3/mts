"""Small shared owner-scoped transaction helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from mts_backend.core.errors import error_response


class BusinessError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


async def business_error_handler(request, exc):
    return error_response(request, exc.status, exc.code, exc.message)


def utcnow():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


async def owned(db, model, identifier, user, include_deleted=False):
    try:
        identifier = str(UUID(str(identifier)))
    except (ValueError, TypeError, AttributeError):
        raise BusinessError(404, "not_found", "Resource not found.") from None
    q = select(model).where(
        model.id == identifier,
        model.owner_id == user.id,
        model.organization_id == user.organization_id,
    )
    if hasattr(model, "deleted_at") and not include_deleted:
        q = q.where(model.deleted_at.is_(None))
    obj = (await db.execute(q.with_for_update())).scalar_one_or_none()
    if obj is None:
        raise BusinessError(404, "not_found", "Resource not found.")
    return obj


def version_check(obj, expected):
    if obj.version != expected:
        raise BusinessError(409, "version_conflict", "Reload resource before editing.")


async def audit(db, user, obj, operation, fields):
    from mts_backend.db.models import AuditEvent

    db.add(
        AuditEvent(
            owner_id=user.id,
            organization_id=user.organization_id,
            entity_type=type(obj).__name__,
            entity_id=str(obj.id),
            operation=operation,
            changed_fields=list(fields),
        )
    )

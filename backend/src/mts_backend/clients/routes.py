"""Owner-scoped client cards with optimistic revisions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mts_backend.auth.dependencies import current_user
from mts_backend.core.business import BusinessError, audit, owned, utcnow, version_check
from mts_backend.db.models import Call, Client, User
from mts_backend.db.session import get_db

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])
Db = Annotated[AsyncSession, Depends(get_db)]
SignedIn = Annotated[User, Depends(current_user)]


class ClientInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    contacts: dict[str, str] = Field(default_factory=dict, max_length=20)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("display_name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is empty.")
        return value.strip()

    @field_validator("contacts")
    @classmethod
    def bounded_contacts(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 80 or len(v) > 1000 for k, v in value.items()):
            raise ValueError("Contact field is too long.")
        return value


class ClientPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    contacts: dict[str, str] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Name cannot be null.")
        return ClientInput.nonempty_name(value)

    @field_validator("contacts")
    @classmethod
    def validate_contacts(cls, value: dict[str, str] | None) -> dict[str, str]:
        if value is None:
            raise ValueError("Contacts cannot be null.")
        return ClientInput.bounded_contacts(value)


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


def serialize(client: Client) -> dict:
    return {
        "id": client.id,
        "display_name": client.display_name,
        "contacts": client.contacts,
        "notes": client.notes,
        "version": client.version,
        "created_at": client.created_at,
    }


@router.get("")
async def list_clients(
    db: Db,
    user: SignedIn,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    query: Annotated[str | None, Query(max_length=200)] = None,
):
    conditions = [
        Client.owner_id == user.id,
        Client.organization_id == user.organization_id,
        Client.deleted_at.is_(None),
    ]
    if query:
        # Names are encrypted. Small-MVP search decrypts only this owner's cards.
        rows = list(
            await db.scalars(
                select(Client).where(*conditions).order_by(Client.created_at.desc(), Client.id)
            )
        )
        matching = [row for row in rows if query.casefold() in row.display_name.casefold()]
        return {
            "items": [serialize(row) for row in matching[offset : offset + limit]],
            "total": len(matching),
            "limit": limit,
            "offset": offset,
        }
    total = await db.scalar(select(func.count()).select_from(Client).where(*conditions))
    rows = await db.scalars(
        select(Client)
        .where(*conditions)
        .order_by(Client.created_at.desc(), Client.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [serialize(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
async def create_client(body: ClientInput, db: Db, user: SignedIn):
    client = Client(owner_id=user.id, organization_id=user.organization_id, **body.model_dump())
    db.add(client)
    await db.flush()
    await audit(db, user, client, "create", ["display_name", "contacts", "notes"])
    return serialize(client)


@router.get("/{client_id}")
async def get_client(client_id: str, db: Db, user: SignedIn):
    return serialize(await owned(db, Client, client_id, user))


@router.patch("/{client_id}")
async def update_client(client_id: str, body: ClientPatch, db: Db, user: SignedIn):
    client = await owned(db, Client, client_id, user)
    version_check(client, body.expected_version)
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    for field in changes:
        setattr(client, field, changes[field])
    if changes:
        client.version += 1
        await audit(db, user, client, "update", list(changes))
    return serialize(client)


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: str, body: VersionInput, db: Db, user: SignedIn):
    client = await owned(db, Client, client_id, user)
    version_check(client, body.expected_version)
    linked = await db.scalar(
        select(Call.id).where(Call.client_id == client.id, Call.deleted_at.is_(None)).limit(1)
    )
    if linked:
        raise BusinessError(
            409, "client_has_calls", "Remove client from its calls before deleting."
        )
    client.deleted_at = utcnow()
    client.version += 1
    await audit(db, user, client, "delete", ["deleted_at"])


@router.get("/{client_id}/calls")
async def client_calls(
    client_id: str,
    db: Db,
    user: SignedIn,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await owned(db, Client, client_id, user)
    conditions = [
        Call.client_id == client_id,
        Call.owner_id == user.id,
        Call.organization_id == user.organization_id,
        Call.deleted_at.is_(None),
    ]
    total = await db.scalar(select(func.count()).select_from(Call).where(*conditions))
    calls = await db.scalars(
        select(Call)
        .where(*conditions)
        .order_by(Call.created_at.desc(), Call.id)
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "id": call.id,
            "title": call.title,
            "client_id": call.client_id,
            "call_at": call.call_at,
            "timezone": call.timezone,
            "source": call.source,
            "is_demo": call.is_demo,
            "processing_status": call.processing_status,
            "analysis_status": call.analysis_status,
            "version": call.version,
            "created_at": call.created_at,
        }
        for call in calls
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}

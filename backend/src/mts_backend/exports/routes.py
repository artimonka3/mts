# ruff: noqa: B008 - FastAPI dependency defaults.
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from mts_backend.auth.dependencies import current_user
from mts_backend.db.models import Call, Client, Participant, Setting
from mts_backend.db.session import get_db
from mts_backend.exports.service import calendar_bytes, spreadsheet_bytes
from mts_backend.tasks.query import TaskFilters, select_tasks

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/tasks.ics")
async def export_ics(
    filters: TaskFilters = Depends(),
    user=Depends(current_user),
    db=Depends(get_db),
):
    records = await select_tasks(db, user, filters)
    body, skipped = calendar_bytes(records)
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tasks.ics"',
            "X-Skipped-Count": str(len(skipped)),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/tasks.xlsx")
async def export_xlsx(
    filters: TaskFilters = Depends(),
    user=Depends(current_user),
    db=Depends(get_db),
):
    records = await select_tasks(db, user, filters)
    call_ids = {item.call_id for item in records}
    calls = {x.id: x for x in await db.scalars(select(Call).where(Call.id.in_(call_ids)))}
    clients = {
        x.id: x
        for x in await db.scalars(
            select(Client).where(
                Client.owner_id == user.id,
                Client.organization_id == user.organization_id,
                Client.deleted_at.is_(None),
            )
        )
    }
    participants = {
        x.id: x
        for x in await db.scalars(
            select(Participant).where(
                Participant.call_id.in_(call_ids),
                Participant.owner_id == user.id,
            )
        )
    }
    tags = {
        x.id: x
        for x in await db.scalars(
            select(Setting).where(
                Setting.owner_id == user.id,
                Setting.kind == "tag",
                Setting.deleted_at.is_(None),
            )
        )
    }
    details = {}
    for item in records:
        client = clients.get(calls[item.call_id].client_id)
        obligor = participants.get(item.data.get("obligor_participant_id"))
        recipient = participants.get(item.data.get("recipient_participant_id"))
        details[item.id] = {
            "client": client.display_name if client else "",
            "obligor": obligor.display_name if obligor else "",
            "recipient": recipient.display_name if recipient else "",
            "tags": ", ".join(
                tags[tag].data["name"] for tag in item.data.get("tag_ids", []) if tag in tags
            ),
        }
    return Response(
        spreadsheet_bytes(records, details),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="tasks.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )

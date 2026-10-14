"""Real database result lifecycle; all records are rolled back after each test."""

import os
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mts_backend.agreements.routes import edit_agreement, transition
from mts_backend.agreements.schemas import AgreementEdit, AgreementTransition
from mts_backend.agreements.service import serialize_agreement
from mts_backend.analysis.fixtures import load_dataset
from mts_backend.analysis.service import initialize_demo
from mts_backend.core.business import BusinessError, uid
from mts_backend.db.models import Agreement, AgreementRevision, Call, Organization, Transcript, User
from mts_backend.transcripts.service import create_revision

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_all_fixture_initialization_and_review_revision_lifecycle():
    url = os.environ.get("MTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MTS_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with async_sessionmaker(bind=connection, expire_on_commit=False)() as db:
                organization = Organization(id=uid(), name="result test")
                db.add(organization)
                await db.flush()
                user = User(
                    id=uid(),
                    organization_id=organization.id,
                    login="test-" + uid(),
                    display_name="test",
                    password_hash="unused",
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                calls = []
                for scenario in load_dataset()["dialogues"]:
                    call = Call(
                        id=uid(),
                        owner_id=user.id,
                        organization_id=organization.id,
                        title=scenario["title"],
                        call_at=datetime.fromisoformat(scenario["call_at"]),
                        timezone=scenario["timezone"],
                        language="ru",
                        source="demo",
                        is_demo=True,
                        scenario_id=scenario["id"],
                        version=1,
                    )
                    db.add(call)
                    await db.flush()
                    await initialize_demo(db, call, scenario)
                    calls.append(call)
                    agreements = (
                        await db.scalars(select(Agreement).where(Agreement.call_id == call.id))
                    ).all()
                    assert len(agreements) == len(scenario["gold"]["agreements"])
                    assert call.analysis_status == "ready"
                    for item in agreements:
                        serialized = await serialize_agreement(db, item)
                        assert serialized["verification"] == "proposed"
                        assert serialized["provenance"] == {"source": "fixture", "is_demo": True}
                call = calls[0]
                item = await db.scalar(select(Agreement).where(Agreement.call_id == call.id))
                accepted = await transition(
                    item.id,
                    "accept",
                    AgreementTransition(expected_version=1),
                    "accept-test",
                    db,
                    user,
                )
                replay = await transition(
                    item.id,
                    "accept",
                    AgreementTransition(expected_version=1),
                    "accept-test",
                    db,
                    user,
                )
                assert accepted == replay
                assert accepted["verification"] == "accepted" and accepted["version"] == 2
                with pytest.raises(BusinessError) as exc:
                    await edit_agreement(
                        item.id, AgreementEdit(expected_version=2, action="Changed"), db, user
                    )
                assert exc.value.code == "confirmation_required"
                changed = await edit_agreement(
                    item.id,
                    AgreementEdit(expected_version=2, action="Changed", confirm_changes=True),
                    db,
                    user,
                )
                assert changed["version"] == 3 and changed["action"] == "Changed"
                original_transcript = await db.get(Transcript, call.current_transcript_id)
                await create_revision(
                    db, call, [{**s, "text": s["text"] + " "} for s in original_transcript.segments]
                )
                assert (await serialize_agreement(db, item))["requires_recheck"] is True
                history = (
                    await db.scalars(
                        select(AgreementRevision)
                        .where(AgreementRevision.agreement_id == item.id)
                        .order_by(AgreementRevision.version)
                    )
                ).all()
                assert [r.version for r in history] == [1, 2, 3]
                assert history[0].data["data"]["action"] != "Changed"
                # Expired sources must not be leaked through serialized evidence.
                original_transcript.availability = "expired"
                assert all(
                    "quote" not in evidence
                    for evidence in (await serialize_agreement(db, item))["evidence"]
                )
            await transaction.rollback()
    finally:
        await engine.dispose()

"""MVP persistence. JSON snapshots keep provider payloads independent of an LLM SDK."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from mts_backend.db.base import Base
from mts_backend.db.encryption import EncryptedJSON, EncryptedText


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class IdentityMixin:
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OwnedMixin:
    owner_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)


def owner_constraint():
    return ForeignKeyConstraint(
        ["owner_id", "organization_id"], ["users.id", "users.organization_id"]
    )


def call_constraint():
    return ForeignKeyConstraint(
        ["call_id", "owner_id", "organization_id"],
        ["calls.id", "calls.owner_id", "calls.organization_id"],
    )


class Organization(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="active")


class User(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("id", "organization_id"),)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    login: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Session(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(IdentityMixin, Base):
    __tablename__ = "login_attempts"
    bucket: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Client(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (
        owner_constraint(),
        UniqueConstraint("id", "owner_id", "organization_id"),
        CheckConstraint("version > 0"),
    )
    display_name: Mapped[str] = mapped_column(EncryptedText())
    contacts: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    notes: Mapped[str | None] = mapped_column(EncryptedText())
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Call(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "calls"
    __table_args__ = (
        owner_constraint(),
        UniqueConstraint("id", "owner_id", "organization_id"),
        ForeignKeyConstraint(
            ["client_id", "owner_id", "organization_id"],
            ["clients.id", "clients.owner_id", "clients.organization_id"],
        ),
        CheckConstraint("version > 0"),
        Index("ix_calls_owner_created", "owner_id", "created_at", "id"),
    )
    client_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    title: Mapped[str] = mapped_column(EncryptedText())
    call_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Minsk")
    language: Mapped[str] = mapped_column(String(16), default="ru")
    source: Mapped[str] = mapped_column(String(32), default="upload")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    scenario_id: Mapped[str | None] = mapped_column(String(120))
    processing_status: Mapped[str] = mapped_column(String(40), default="received")
    analysis_status: Mapped[str] = mapped_column(String(40), default="not_connected")
    current_transcript_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    current_summary_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    version: Mapped[int] = mapped_column(Integer, default=1)
    notice_version: Mapped[str | None] = mapped_column(String(80))
    processing_rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Participant(IdentityMixin, OwnedMixin, Base):
    __tablename__ = "participants"
    __table_args__ = (owner_constraint(), call_constraint())
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    display_name: Mapped[str | None] = mapped_column(EncryptedText())
    role: Mapped[str] = mapped_column(String(32), default="unknown")
    speaker_id: Mapped[str | None] = mapped_column(String(80))


class Transcript(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        owner_constraint(),
        call_constraint(),
        UniqueConstraint("call_id", "revision"),
        UniqueConstraint("id", "call_id", "owner_id", "organization_id"),
    )
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    segments: Mapped[list] = mapped_column(EncryptedJSON(), default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability: Mapped[str] = mapped_column(String(32), default="available")


class AnalysisRun(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (owner_constraint(), call_constraint())
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    source: Mapped[str] = mapped_column(String(32), default="fixture")
    settings_snapshot: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)


class Summary(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "summaries"
    __table_args__ = (
        owner_constraint(),
        call_constraint(),
        UniqueConstraint("call_id", "version"),
    )
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(EncryptedText(), default="")
    client_message_draft: Mapped[str] = mapped_column(EncryptedText(), default="")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability: Mapped[str] = mapped_column(String(32), default="available")


class Agreement(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "agreements"
    __table_args__ = (
        owner_constraint(),
        call_constraint(),
        CheckConstraint("version > 0"),
        Index("ix_agreements_owner_states", "owner_id", "verification", "execution"),
    )
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"))
    transcript_id: Mapped[str | None] = mapped_column(ForeignKey("transcripts.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    verification: Mapped[str] = mapped_column(String(32), default="proposed")
    execution: Mapped[str] = mapped_column(String(32), default="open")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    data: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgreementRevision(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "agreement_revisions"
    __table_args__ = (UniqueConstraint("agreement_id", "version"),)
    agreement_id: Mapped[str] = mapped_column(ForeignKey("agreements.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(EncryptedJSON())


class AudioAsset(IdentityMixin, OwnedMixin, Base):
    __tablename__ = "audio_assets"
    __table_args__ = (owner_constraint(), call_constraint(), CheckConstraint("size_bytes >= 0"))
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="original")
    storage_key: Mapped[str] = mapped_column(String(240), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    availability: Mapped[str] = mapped_column(String(32), default="available")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        owner_constraint(),
        call_constraint(),
        CheckConstraint("attempt >= 0"),
        Index("ix_jobs_poll", "status", "not_before"),
    )
    call_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_token: Mapped[str | None] = mapped_column(String(80))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class Setting(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "settings"
    __table_args__ = (owner_constraint(), CheckConstraint("version > 0"))
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SettingRevision(IdentityMixin, Base):
    __tablename__ = "setting_revisions"
    __table_args__ = (UniqueConstraint("setting_id", "version"),)
    setting_id: Mapped[str] = mapped_column(ForeignKey("settings.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(EncryptedJSON())


class Reminder(IdentityMixin, OwnedMixin, Base):
    __tablename__ = "reminders"
    __table_args__ = (
        owner_constraint(),
        UniqueConstraint("agreement_id", "agreement_version", "scheduled_at"),
        Index("ix_reminders_poll", "status", "scheduled_at"),
    )
    agreement_id: Mapped[str] = mapped_column(ForeignKey("agreements.id"), index=True)
    agreement_version: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="scheduled")


class Notification(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (owner_constraint(),)
    agreement_id: Mapped[str | None] = mapped_column(ForeignKey("agreements.id"))
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deduplication_key: Mapped[str] = mapped_column(String(240), unique=True)


class OutboxEvent(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        owner_constraint(),
        UniqueConstraint("agreement_id", "aggregate_version", "event_type"),
        Index("ix_outbox_poll", "status", "not_before"),
    )
    agreement_id: Mapped[str] = mapped_column(ForeignKey("agreements.id"), index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DeliveryAttempt(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (UniqueConstraint("event_id", "attempt"),)
    event_id: Mapped[str] = mapped_column(ForeignKey("outbox_events.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(80))
    response_code: Mapped[int | None] = mapped_column(Integer)


class AuditEvent(IdentityMixin, CreatedMixin, OwnedMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (owner_constraint(),)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    operation: Mapped[str] = mapped_column(String(80))
    changed_fields: Mapped[list] = mapped_column(JSON, default=list)


class IdempotencyRecord(IdentityMixin, CreatedMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("owner_id", "operation", "key"),)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(128))
    digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    status_code: Mapped[int] = mapped_column(Integer, default=202)


class MockCRMRecord(Base):
    """Local demo receiver state; event IDs enable replay without real CRM credentials."""

    __tablename__ = "mock_crm_records"
    __table_args__ = (owner_constraint(),)
    agreement_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    owner_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    organization_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    version: Mapped[int] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    event_ids: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

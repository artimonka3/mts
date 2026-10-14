"""MVP business storage; frozen SQL independent of future ORM changes."""

from alembic import op

revision = "0002_business"
down_revision = "0001_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE login_attempts (
        bucket VARCHAR(64) NOT NULL,
        attempted_at TIMESTAMP WITH TIME ZONE NOT NULL,
        id UUID NOT NULL,
        PRIMARY KEY (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_login_attempts_attempted_at ON login_attempts (attempted_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_login_attempts_bucket ON login_attempts (bucket)
        """
    )
    op.execute(
        """
        CREATE TABLE organizations (
        name VARCHAR(200) NOT NULL,
        status VARCHAR(32) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE users (
        organization_id UUID NOT NULL,
        login VARCHAR(120) NOT NULL,
        display_name VARCHAR(200) NOT NULL,
        password_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (id, organization_id),
        FOREIGN KEY(organization_id) REFERENCES organizations (id),
        UNIQUE (login)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE audit_events (
        entity_type VARCHAR(80) NOT NULL,
        entity_id VARCHAR(80) NOT NULL,
        operation VARCHAR(80) NOT NULL,
        changed_fields JSON NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_audit_events_owner_id ON audit_events (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE clients (
        display_name VARCHAR(200) NOT NULL,
        contacts JSON NOT NULL,
        notes TEXT,
        version INTEGER NOT NULL,
        deleted_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        UNIQUE (id, owner_id, organization_id),
        CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_clients_owner_id ON clients (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE idempotency_records (
        owner_id UUID NOT NULL,
        operation VARCHAR(120) NOT NULL,
        key VARCHAR(128) NOT NULL,
        digest VARCHAR(64) NOT NULL,
        response JSON NOT NULL,
        status_code INTEGER NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (owner_id, operation, key),
        FOREIGN KEY(owner_id) REFERENCES users (id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE mock_crm_records (
        agreement_id UUID NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        version INTEGER NOT NULL,
        deleted BOOLEAN NOT NULL,
        event_ids JSON NOT NULL,
        payload JSON NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (agreement_id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE sessions (
        user_id UUID NOT NULL,
        token_digest VARCHAR(64) NOT NULL,
        csrf_digest VARCHAR(64) NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        revoked_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(user_id) REFERENCES users (id),
        UNIQUE (token_digest)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_sessions_expires_at ON sessions (expires_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_sessions_user_id ON sessions (user_id)
        """
    )
    op.execute(
        """
        CREATE TABLE settings (
        kind VARCHAR(32) NOT NULL,
        version INTEGER NOT NULL,
        data JSON NOT NULL,
        deleted_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_settings_owner_id ON settings (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE calls (
        client_id UUID,
        title VARCHAR(200) NOT NULL,
        call_at TIMESTAMP WITH TIME ZONE NOT NULL,
        timezone VARCHAR(80) NOT NULL,
        language VARCHAR(16) NOT NULL,
        source VARCHAR(32) NOT NULL,
        is_demo BOOLEAN NOT NULL,
        scenario_id VARCHAR(120),
        processing_status VARCHAR(40) NOT NULL,
        analysis_status VARCHAR(40) NOT NULL,
        current_transcript_id UUID,
        current_summary_id UUID,
        version INTEGER NOT NULL,
        notice_version VARCHAR(80),
        processing_rights_confirmed BOOLEAN NOT NULL,
        deleted_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        UNIQUE (id, owner_id, organization_id),
        FOREIGN KEY(client_id, owner_id, organization_id) REFERENCES clients (id, owner_id,
        organization_id),
        CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_calls_owner_created ON calls (owner_id, created_at, id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_calls_owner_id ON calls (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE setting_revisions (
        setting_id UUID NOT NULL,
        version INTEGER NOT NULL,
        data JSON NOT NULL,
        id UUID NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (setting_id, version),
        FOREIGN KEY(setting_id) REFERENCES settings (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_setting_revisions_setting_id ON setting_revisions (setting_id)
        """
    )
    op.execute(
        """
        CREATE TABLE audio_assets (
        call_id UUID NOT NULL,
        kind VARCHAR(32) NOT NULL,
        storage_key VARCHAR(240) NOT NULL,
        mime VARCHAR(100) NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        size_bytes INTEGER NOT NULL,
        duration_ms INTEGER,
        channels INTEGER,
        availability VARCHAR(32) NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        CHECK (size_bytes >= 0),
        UNIQUE (storage_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_audio_assets_call_id ON audio_assets (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_audio_assets_owner_id ON audio_assets (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE jobs (
        call_id UUID NOT NULL,
        stage VARCHAR(40) NOT NULL,
        status VARCHAR(32) NOT NULL,
        attempt INTEGER NOT NULL,
        max_attempts INTEGER NOT NULL,
        not_before TIMESTAMP WITH TIME ZONE NOT NULL,
        lease_token VARCHAR(80),
        lease_until TIMESTAMP WITH TIME ZONE,
        error_code VARCHAR(80),
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        CHECK (attempt >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_jobs_call_id ON jobs (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_jobs_owner_id ON jobs (owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_jobs_poll ON jobs (status, not_before)
        """
    )
    op.execute(
        """
        CREATE TABLE participants (
        call_id UUID NOT NULL,
        display_name VARCHAR(200),
        role VARCHAR(32) NOT NULL,
        speaker_id VARCHAR(80),
        id UUID NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_participants_call_id ON participants (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_participants_owner_id ON participants (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE transcripts (
        call_id UUID NOT NULL,
        revision INTEGER NOT NULL,
        source VARCHAR(32) NOT NULL,
        segments JSON NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE,
        availability VARCHAR(32) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        UNIQUE (call_id, revision),
        UNIQUE (id, call_id, owner_id, organization_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_transcripts_call_id ON transcripts (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_transcripts_owner_id ON transcripts (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE analysis_runs (
        call_id UUID NOT NULL,
        transcript_id UUID NOT NULL,
        status VARCHAR(32) NOT NULL,
        source VARCHAR(32) NOT NULL,
        settings_snapshot JSON NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        FOREIGN KEY(transcript_id) REFERENCES transcripts (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_analysis_runs_call_id ON analysis_runs (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_analysis_runs_owner_id ON analysis_runs (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE agreements (
        call_id UUID NOT NULL,
        analysis_run_id UUID,
        transcript_id UUID,
        version INTEGER NOT NULL,
        verification VARCHAR(32) NOT NULL,
        execution VARCHAR(32) NOT NULL,
        source VARCHAR(32) NOT NULL,
        data JSON NOT NULL,
        accepted_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        CHECK (version > 0),
        FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id),
        FOREIGN KEY(transcript_id) REFERENCES transcripts (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_agreements_call_id ON agreements (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_agreements_owner_id ON agreements (owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_agreements_owner_states ON agreements (owner_id, verification,
        execution)
        """
    )
    op.execute(
        """
        CREATE TABLE summaries (
        call_id UUID NOT NULL,
        analysis_run_id UUID,
        version INTEGER NOT NULL,
        summary TEXT NOT NULL,
        client_message_draft TEXT NOT NULL,
        source VARCHAR(32) NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE,
        availability VARCHAR(32) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(call_id, owner_id, organization_id) REFERENCES calls (id, owner_id,
        organization_id),
        UNIQUE (call_id, version),
        FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_summaries_call_id ON summaries (call_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_summaries_owner_id ON summaries (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE agreement_revisions (
        agreement_id UUID NOT NULL,
        version INTEGER NOT NULL,
        data JSON NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (agreement_id, version),
        FOREIGN KEY(agreement_id) REFERENCES agreements (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_agreement_revisions_agreement_id ON agreement_revisions
        (agreement_id)
        """
    )
    op.execute(
        """
        CREATE TABLE notifications (
        agreement_id UUID,
        kind VARCHAR(32) NOT NULL,
        version INTEGER NOT NULL,
        read_at TIMESTAMP WITH TIME ZONE,
        deduplication_key VARCHAR(240) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        FOREIGN KEY(agreement_id) REFERENCES agreements (id),
        UNIQUE (deduplication_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_notifications_owner_id ON notifications (owner_id)
        """
    )
    op.execute(
        """
        CREATE TABLE outbox_events (
        agreement_id UUID NOT NULL,
        aggregate_version INTEGER NOT NULL,
        event_type VARCHAR(80) NOT NULL,
        payload JSON NOT NULL,
        status VARCHAR(32) NOT NULL,
        attempt INTEGER NOT NULL,
        not_before TIMESTAMP WITH TIME ZONE NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        UNIQUE (agreement_id, aggregate_version, event_type),
        FOREIGN KEY(agreement_id) REFERENCES agreements (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_outbox_events_agreement_id ON outbox_events (agreement_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_outbox_events_owner_id ON outbox_events (owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_outbox_poll ON outbox_events (status, not_before)
        """
    )
    op.execute(
        """
        CREATE TABLE reminders (
        agreement_id UUID NOT NULL,
        agreement_version INTEGER NOT NULL,
        scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
        status VARCHAR(32) NOT NULL,
        id UUID NOT NULL,
        owner_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(owner_id, organization_id) REFERENCES users (id, organization_id),
        UNIQUE (agreement_id, agreement_version, scheduled_at),
        FOREIGN KEY(agreement_id) REFERENCES agreements (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_reminders_agreement_id ON reminders (agreement_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_reminders_owner_id ON reminders (owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_reminders_poll ON reminders (status, scheduled_at)
        """
    )
    op.execute(
        """
        CREATE TABLE delivery_attempts (
        event_id UUID NOT NULL,
        attempt INTEGER NOT NULL,
        result VARCHAR(80) NOT NULL,
        response_code INTEGER,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (event_id, attempt),
        FOREIGN KEY(event_id) REFERENCES outbox_events (id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_delivery_attempts_event_id ON delivery_attempts (event_id)
        """
    )


def downgrade() -> None:
    op.drop_table("delivery_attempts")
    op.drop_table("reminders")
    op.drop_table("outbox_events")
    op.drop_table("notifications")
    op.drop_table("agreement_revisions")
    op.drop_table("summaries")
    op.drop_table("agreements")
    op.drop_table("analysis_runs")
    op.drop_table("transcripts")
    op.drop_table("participants")
    op.drop_table("jobs")
    op.drop_table("audio_assets")
    op.drop_table("setting_revisions")
    op.drop_table("calls")
    op.drop_table("settings")
    op.drop_table("sessions")
    op.drop_table("mock_crm_records")
    op.drop_table("idempotency_records")
    op.drop_table("clients")
    op.drop_table("audit_events")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("login_attempts")

"""Widen encrypted display fields; prior stage2 has no business records."""

import sqlalchemy as sa

from alembic import op

revision = "0003_encrypted_metadata"
down_revision = "0002_business"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mock_crm_records",
        sa.Column("terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for table, column in [
        ("clients", "display_name"),
        ("calls", "title"),
        ("participants", "display_name"),
    ]:
        op.alter_column(table, column, type_=sa.Text())


def downgrade() -> None:
    # Keep widened columns: encrypted values must never be silently truncated.
    op.drop_column("mock_crm_records", "terminal")

"""Initialize the migration chain without premature business tables.

Revision ID: 0001_bootstrap
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_bootstrap"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Alembic creates its version table; domain schema belongs to stage 3."""


def downgrade() -> None:
    """There are no domain objects to remove in this baseline."""

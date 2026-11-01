"""add nullable attempt identity to row dispositions

Revision ID: b4f3e2d1a907
Revises: a41d9c7e6f20
Create Date: 2026-10-31 23:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4f3e2d1a907"
down_revision: str | Sequence[str] | None = "a41d9c7e6f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Expand both disposition tables with nullable attempt references."""
    op.add_column("rejected_records", sa.Column("attempt_id", sa.String(length=100), nullable=True))
    op.add_column(
        "duplicate_records", sa.Column("attempt_id", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    """Drop attempt identity after the dependent constraints are removed."""
    with op.batch_alter_table("duplicate_records", recreate="always") as batch_op:
        batch_op.drop_column("attempt_id")
    with op.batch_alter_table("rejected_records", recreate="always") as batch_op:
        batch_op.drop_column("attempt_id")

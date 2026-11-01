"""backfill row dispositions to their latest recorded attempt

Revision ID: c5a4f7d9e210
Revises: b4f3e2d1a907
Create Date: 2026-10-31 23:56:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5a4f7d9e210"
down_revision: str | Sequence[str] | None = "b4f3e2d1a907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Attribute existing run-level rows to the latest attempt available."""
    for table_name in ("rejected_records", "duplicate_records"):
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET attempt_id = (
                    SELECT attempt_id
                    FROM run_attempts
                    WHERE run_attempts.run_id = {table_name}.run_id
                    ORDER BY attempt_number DESC
                    LIMIT 1
                )
                WHERE attempt_id IS NULL
                """
            )
        )
        unassigned = op.get_bind().scalar(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE attempt_id IS NULL")
        )
        if unassigned:
            raise RuntimeError(
                f"Cannot assign {unassigned} {table_name} rows because their runs have no attempt."
            )


def downgrade() -> None:
    """Keep the attribution values until the preceding schema migration drops them."""

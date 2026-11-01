"""enforce attempt-scoped row disposition evidence

Revision ID: d6b7c8e9f103
Revises: c5a4f7d9e210
Create Date: 2026-10-31 23:57:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6b7c8e9f103"
down_revision: str | Sequence[str] | None = "c5a4f7d9e210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require each disposition to belong to one persisted run attempt."""
    with op.batch_alter_table("rejected_records", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_rejected_run_row", type_="unique")
        batch_op.alter_column("attempt_id", existing_type=sa.String(length=100), nullable=False)
        batch_op.create_unique_constraint(
            "uq_rejected_attempt_row", ["attempt_id", "source_row_number"]
        )
        batch_op.create_foreign_key(
            "fk_rejected_run_attempt",
            "run_attempts",
            ["run_id", "attempt_id"],
            ["run_id", "attempt_id"],
        )

    with op.batch_alter_table("duplicate_records", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_duplicate_run_row", type_="unique")
        batch_op.alter_column("attempt_id", existing_type=sa.String(length=100), nullable=False)
        batch_op.create_unique_constraint(
            "uq_duplicate_attempt_row", ["attempt_id", "source_row_number"]
        )
        batch_op.create_foreign_key(
            "fk_duplicate_run_attempt",
            "run_attempts",
            ["run_id", "attempt_id"],
            ["run_id", "attempt_id"],
        )


def downgrade() -> None:
    """Refuse rollback if it would merge and discard rows from distinct attempts."""
    connection = op.get_bind()
    for table_name in ("rejected_records", "duplicate_records"):
        conflicting_groups = connection.scalar(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT run_id, source_row_number
                    FROM {table_name}
                    GROUP BY run_id, source_row_number
                    HAVING COUNT(*) > 1
                ) AS repeated_dispositions
                """
            )
        )
        if conflicting_groups:
            raise RuntimeError(f"Cannot downgrade {table_name}: attempt history would be lost.")

    with op.batch_alter_table("duplicate_records", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_duplicate_run_attempt", type_="foreignkey")
        batch_op.drop_constraint("uq_duplicate_attempt_row", type_="unique")
        batch_op.alter_column("attempt_id", existing_type=sa.String(length=100), nullable=True)
        batch_op.create_unique_constraint("uq_duplicate_run_row", ["run_id", "source_row_number"])

    with op.batch_alter_table("rejected_records", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_rejected_run_attempt", type_="foreignkey")
        batch_op.drop_constraint("uq_rejected_attempt_row", type_="unique")
        batch_op.alter_column("attempt_id", existing_type=sa.String(length=100), nullable=True)
        batch_op.create_unique_constraint("uq_rejected_run_row", ["run_id", "source_row_number"])

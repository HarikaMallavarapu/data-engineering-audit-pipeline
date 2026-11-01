"""require positive pipeline versions and run attempts

Revision ID: a41d9c7e6f20
Revises: 2d84ddb87cb2
Create Date: 2026-10-31 23:40:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "a41d9c7e6f20"
down_revision: str | Sequence[str] | None = "2d84ddb87cb2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add positive-value checks using SQLite-compatible table rebuilds."""
    # A previous interrupted SQLite batch operation may have left its staging table.
    tables = set(inspect(op.get_bind()).get_table_names())
    for stale_table in ("_alembic_tmp_pipeline_versions", "_alembic_tmp_run_attempts"):
        if stale_table in tables:
            op.drop_table(stale_table)

    with op.batch_alter_table("pipeline_versions", recreate="always") as batch_op:
        batch_op.create_check_constraint("ck_pipeline_version_number_positive", "version >= 1")

    with op.batch_alter_table("run_attempts", recreate="always") as batch_op:
        batch_op.create_check_constraint("ck_run_attempt_number_positive", "attempt_number >= 1")


def downgrade() -> None:
    """Remove positive-value checks."""
    with op.batch_alter_table("run_attempts", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_run_attempt_number_positive", type_="check")

    with op.batch_alter_table("pipeline_versions", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_pipeline_version_number_positive", type_="check")

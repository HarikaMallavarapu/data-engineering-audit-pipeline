"""add dynamic engine profiles, rules, plans, and guarded AI accounting

Revision ID: e19c4a2b75f1
Revises: d6b7c8e9f103
Create Date: 2026-11-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.models import (
    AIBudget,
    AICache,
    AIUsage,
    ProcessingPlan,
    RuleVersion,
    SchemaProfile,
    TransformationVersion,
)

revision: str = "e19c4a2b75f1"
down_revision: str | Sequence[str] | None = "d6b7c8e9f103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable source profile metadata and new versioned engine tables."""
    op.add_column("source_files", sa.Column("profile", sa.JSON(), nullable=True))
    op.add_column("source_files", sa.Column("schema_fingerprint", sa.String(length=64), nullable=True))
    op.create_index("ix_source_files_schema_fingerprint", "source_files", ["schema_fingerprint"])
    bind = op.get_bind()
    for model in (
        AIBudget,
        AIUsage,
        AICache,
        SchemaProfile,
        RuleVersion,
        TransformationVersion,
        ProcessingPlan,
    ):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove added engine tables and source profile fields."""
    bind = op.get_bind()
    for model in (
        ProcessingPlan,
        TransformationVersion,
        RuleVersion,
        SchemaProfile,
        AICache,
        AIUsage,
        AIBudget,
    ):
        model.__table__.drop(bind=bind, checkfirst=True)
    op.drop_index("ix_source_files_schema_fingerprint", table_name="source_files")
    op.drop_column("source_files", "schema_fingerprint")
    op.drop_column("source_files", "profile")

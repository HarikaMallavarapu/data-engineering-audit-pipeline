"""persist per-check validation executions by pipeline attempt

Revision ID: f2a4b6c8d0e1
Revises: e19c4a2b75f1
Create Date: 2026-11-01 00:00:00
"""

from collections.abc import Sequence

from alembic import op
from app.models import ValidationDefinition, ValidationExecution

revision: str = "f2a4b6c8d0e1"
down_revision: str | Sequence[str] | None = "e19c4a2b75f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    ValidationDefinition.__table__.create(bind=bind, checkfirst=True)
    ValidationExecution.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    ValidationExecution.__table__.drop(bind=bind, checkfirst=True)
    ValidationDefinition.__table__.drop(bind=bind, checkfirst=True)

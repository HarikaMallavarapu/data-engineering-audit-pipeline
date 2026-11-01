"""persist versioned quality baselines

Revision ID: a8c6e4d2f109
Revises: f2a4b6c8d0e1
Create Date: 2026-11-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
from app.models import QualityBaseline

revision: str = "a8c6e4d2f109"
down_revision: str | Sequence[str] | None = "f2a4b6c8d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    QualityBaseline.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    QualityBaseline.__table__.drop(bind=op.get_bind(), checkfirst=True)

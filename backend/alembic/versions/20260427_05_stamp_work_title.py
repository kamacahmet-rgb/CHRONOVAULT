"""stamps: work_title (medya sertifikası)

Revision ID: 20260427_05
Revises: 20260426_04
Create Date: 2026-04-27

docs/Medya-Damga-Sertifikasi.md
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260427_05"
down_revision: Union[str, None] = "20260426_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stamps",
        sa.Column("work_title", sa.String(length=300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stamps", "work_title")

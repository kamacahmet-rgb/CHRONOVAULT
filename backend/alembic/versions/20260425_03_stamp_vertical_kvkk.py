"""stamps: vertical, KVKK / işleme meta alanları

Revision ID: 20260425_03
Revises: 20260424_02
Create Date: 2026-04-23

docs/KVKK-Vertical-Damgalama.md
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260425_03"
down_revision: Union[str, None] = "20260424_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stamps", sa.Column("vertical", sa.String(length=40), nullable=True))
    op.add_column("stamps", sa.Column("processing_purpose", sa.String(length=120), nullable=True))
    op.add_column("stamps", sa.Column("data_category", sa.String(length=32), nullable=True))
    op.add_column("stamps", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stamps", sa.Column("consent_reference", sa.String(length=120), nullable=True))
    op.create_index("ix_stamps_vertical", "stamps", ["vertical"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stamps_vertical", table_name="stamps")
    op.drop_column("stamps", "consent_reference")
    op.drop_column("stamps", "retention_until")
    op.drop_column("stamps", "data_category")
    op.drop_column("stamps", "processing_purpose")
    op.drop_column("stamps", "vertical")

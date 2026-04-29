"""stamps: idempotency_key + credits_charged (kurumsal kredi akışı)

Revision ID: 20260426_04
Revises: 20260425_03
Create Date: 2026-04-26

backend/TurkDamga-Backend.md — Damgalama akışı
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_04"
down_revision: Union[str, None] = "20260425_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stamps",
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "stamps",
        sa.Column(
            "credits_charged",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index("ix_stamps_idempotency_key", "stamps", ["idempotency_key"], unique=False)
    op.create_index(
        "uq_stamps_user_idempotency_key",
        "stamps",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_stamps_user_idempotency_key", table_name="stamps")
    op.drop_index("ix_stamps_idempotency_key", table_name="stamps")
    op.drop_column("stamps", "credits_charged")
    op.drop_column("stamps", "idempotency_key")

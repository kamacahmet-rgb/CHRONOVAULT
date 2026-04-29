"""organization_credit_balances, wholesale_contracts, credit_ledger_entries

Revision ID: 20260424_02
Revises: 20260423_01
Create Date: 2026-04-23

Toptan kontrat ve kurumsal kredi bakiyesi (docs/Toptan-Satis-Kredi-Kontrat.md).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260424_02"
down_revision: Union[str, None] = "20260423_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_credit_balances",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )

    op.create_table(
        "wholesale_contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("buyer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_type", sa.String(length=32), nullable=False, server_default="credits"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("credit_quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("pricing_currency", sa.String(length=8), nullable=False, server_default="TRY"),
        sa.Column("external_legal_ref", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("settlement_token_symbol", sa.String(length=20), nullable=True),
        sa.Column("settlement_token_amount", sa.String(length=64), nullable=True),
        sa.Column("settlement_tx_hash", sa.String(length=66), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wholesale_contracts_buyer_org",
        "wholesale_contracts",
        ["buyer_organization_id"],
        unique=False,
    )

    op.create_table(
        "credit_ledger_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["wholesale_contracts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_credit_ledger_org",
        "credit_ledger_entries",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_org", table_name="credit_ledger_entries")
    op.drop_table("credit_ledger_entries")
    op.drop_index("ix_wholesale_contracts_buyer_org", table_name="wholesale_contracts")
    op.drop_table("wholesale_contracts")
    op.drop_table("organization_credit_balances")

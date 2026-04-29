"""İlk şema: users ve stamps (TurkDamga-Backend.md taban kolonları)

Revision ID: 20260422_00
Revises: None
Create Date: 2026-04-22

Sonraki migrasyonlar (20260423_01 …) users/stamps üzerine ek kolon ve tablolar ekler.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260422_00"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("used_this_month", sa.Integer(), nullable=False, server_default="0"),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "stamps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("project", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("polygon_tx", sa.String(length=66), nullable=True),
        sa.Column("polygon_url", sa.String(length=200), nullable=True),
        sa.Column("polygon_block", sa.BigInteger(), nullable=True),
        sa.Column("polygon_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("ots_file_data", sa.Text(), nullable=True),
        sa.Column("ots_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("ots_bitcoin_block", sa.BigInteger(), nullable=True),
        sa.Column("ots_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chain", sa.String(length=20), nullable=False, server_default="both"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_stamps_user_id", "stamps", ["user_id"], unique=False)
    op.create_index("ix_stamps_file_hash", "stamps", ["file_hash"], unique=False)
    op.create_index("ix_stamps_created_at", "stamps", ["created_at"], unique=False)
    op.create_index("ix_stamps_hash_user", "stamps", ["file_hash", "user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stamps_hash_user", table_name="stamps")
    op.drop_index("ix_stamps_created_at", table_name="stamps")
    op.drop_index("ix_stamps_file_hash", table_name="stamps")
    op.drop_index("ix_stamps_user_id", table_name="stamps")
    op.drop_table("stamps")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

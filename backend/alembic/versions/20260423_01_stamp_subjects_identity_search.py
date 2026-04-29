"""stamp_subjects tablosu, users kimlik/rol alanları, stamps.search_vector GIN

Revision ID: 20260423_01
Revises:
Create Date: 2026-04-23

Notlar:
- down_revision = 20260422_00: users + stamps tabloları önce 20260422_00 ile oluşturulur.
- users ve stamps tabloları veritabanında mevcut olmalı (TurkDamga-Backend.md şeması).
- PostgreSQL 13+ önerilir (gen_random_uuid).
- search_vector: sunucuda 'turkish' text search config yoksa aşağıdaki
  op.execute bloklarında 'simple' kullanın.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260423_01"
down_revision: Union[str, None] = "20260422_00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("subject_tc_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("subject_binding_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_organization_id", "users", ["organization_id"], unique=False)
    op.create_index(
        "ix_users_subject_tc_fingerprint",
        "users",
        ["subject_tc_fingerprint"],
        unique=False,
    )
    op.alter_column("users", "role", server_default=None)

    op.create_table(
        "stamp_subjects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("stamp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tc_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["stamp_id"], ["stamps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stamp_subjects_stamp_id", "stamp_subjects", ["stamp_id"], unique=False)
    op.create_index(
        "ix_stamp_subjects_tc_fingerprint", "stamp_subjects", ["tc_fingerprint"], unique=False
    )
    op.create_index(
        "ix_stamp_subjects_organization_id",
        "stamp_subjects",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_stamp_subject_fp_org",
        "stamp_subjects",
        ["tc_fingerprint", "organization_id"],
        unique=False,
    )

    # Tam metin araması (SQLAlchemy modelinde opsiyonel; sorgu raw SQL veya tsvector ile)
    op.execute(
        """
        ALTER TABLE stamps ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
          setweight(to_tsvector('simple', coalesce(description, '')), 'B')
          || setweight(to_tsvector('simple', coalesce(file_name, '')), 'A')
        ) STORED;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_stamps_search_vector
        ON stamps USING GIN (search_vector);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_stamps_search_vector;")
    op.execute("ALTER TABLE stamps DROP COLUMN IF EXISTS search_vector;")

    op.drop_index("ix_stamp_subject_fp_org", table_name="stamp_subjects")
    op.drop_index("ix_stamp_subjects_organization_id", table_name="stamp_subjects")
    op.drop_index("ix_stamp_subjects_tc_fingerprint", table_name="stamp_subjects")
    op.drop_index("ix_stamp_subjects_stamp_id", table_name="stamp_subjects")
    op.drop_table("stamp_subjects")

    op.drop_index("ix_users_subject_tc_fingerprint", table_name="users")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "subject_binding_verified_at")
    op.drop_column("users", "subject_tc_fingerprint")
    op.drop_column("users", "organization_id")
    op.drop_column("users", "role")

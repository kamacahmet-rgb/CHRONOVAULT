"""users.credit_balance — damga için ön ödemeli kredi (GAS × çarpan)

Revision ID: 20260430_08
Revises: 20260429_07
Create Date: 2026-04-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_08"
down_revision: Union[str, None] = "20260429_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(sa.text("UPDATE users SET credit_balance = 10000 WHERE credit_balance = 0"))
    op.alter_column("users", "credit_balance", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "credit_balance")

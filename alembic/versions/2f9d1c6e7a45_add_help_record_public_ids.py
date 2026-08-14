"""add help record public ids

Revision ID: 2f9d1c6e7a45
Revises: a47d8b1c6e2f
Create Date: 2026-08-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "2f9d1c6e7a45"
down_revision: Union[str, None] = "a47d8b1c6e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offer", sa.Column("public_id", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True))
    op.add_column("demand", sa.Column("public_id", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True))
    op.create_index("ix_offer_public_id", "offer", ["public_id"])
    op.create_index("ix_demand_public_id", "demand", ["public_id"])


def downgrade() -> None:
    op.drop_index("ix_demand_public_id", table_name="demand")
    op.drop_index("ix_offer_public_id", table_name="offer")
    op.drop_column("demand", "public_id")
    op.drop_column("offer", "public_id")

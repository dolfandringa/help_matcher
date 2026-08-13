"""add help record titles

Revision ID: a47d8b1c6e2f
Revises: 6d71d4e88b8b
Create Date: 2026-08-13 16:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "a47d8b1c6e2f"
down_revision: Union[str, None] = "6d71d4e88b8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offer", sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True))
    op.add_column("demand", sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True))
    op.execute("UPDATE offer SET title = left(original_message, 200) WHERE title IS NULL")
    op.execute("UPDATE demand SET title = left(original_message, 200) WHERE title IS NULL")
    op.alter_column("offer", "title", nullable=False)
    op.alter_column("demand", "title", nullable=False)


def downgrade() -> None:
    op.drop_column("demand", "title")
    op.drop_column("offer", "title")

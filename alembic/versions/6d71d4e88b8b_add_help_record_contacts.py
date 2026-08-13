"""add help record contacts

Revision ID: 6d71d4e88b8b
Revises: 9bfb7f6b0f4c
Create Date: 2026-08-13 16:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "6d71d4e88b8b"
down_revision: Union[str, None] = "9bfb7f6b0f4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offeruser",
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offer.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("offer_id", "user_id"),
        sa.UniqueConstraint("offer_id", "user_id"),
    )
    op.create_table(
        "demanduser",
        sa.Column("demand_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["demand_id"], ["demand.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("demand_id", "user_id"),
        sa.UniqueConstraint("demand_id", "user_id"),
    )
    op.execute("""
        UPDATE "user"
        SET phone_number = offer.phone_number
        FROM offer
        WHERE "user".id = offer.user_id
            AND "user".phone_number IS NULL
            AND offer.phone_number IS NOT NULL
    """)
    op.execute("""
        UPDATE "user"
        SET phone_number = demand.phone_number
        FROM demand
        WHERE "user".id = demand.user_id
            AND "user".phone_number IS NULL
            AND demand.phone_number IS NOT NULL
    """)
    op.execute("""
        INSERT INTO offeruser (offer_id, user_id)
        SELECT id, user_id FROM offer
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO demanduser (demand_id, user_id)
        SELECT id, user_id FROM demand
        ON CONFLICT DO NOTHING
    """)
    op.drop_index(op.f("ix_offer_phone_number"), table_name="offer")
    op.drop_index(op.f("ix_offer_user_id"), table_name="offer")
    op.drop_index(op.f("ix_demand_phone_number"), table_name="demand")
    op.drop_index(op.f("ix_demand_user_id"), table_name="demand")
    op.drop_column("offer", "phone_number")
    op.drop_column("offer", "user_id")
    op.drop_column("demand", "phone_number")
    op.drop_column("demand", "user_id")


def downgrade() -> None:
    op.add_column("demand", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("demand", sa.Column("phone_number", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True))
    op.add_column("offer", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("offer", sa.Column("phone_number", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True))
    op.execute("""
        UPDATE offer
        SET user_id = offeruser.user_id,
            phone_number = "user".phone_number
        FROM offeruser
        JOIN "user" ON "user".id = offeruser.user_id
        WHERE offer.id = offeruser.offer_id
            AND offer.user_id IS NULL
    """)
    op.execute("""
        UPDATE demand
        SET user_id = demanduser.user_id,
            phone_number = "user".phone_number
        FROM demanduser
        JOIN "user" ON "user".id = demanduser.user_id
        WHERE demand.id = demanduser.demand_id
            AND demand.user_id IS NULL
    """)
    op.alter_column("offer", "user_id", nullable=False)
    op.alter_column("demand", "user_id", nullable=False)
    op.create_foreign_key(None, "offer", "user", ["user_id"], ["id"])
    op.create_foreign_key(None, "demand", "user", ["user_id"], ["id"])
    op.create_index(op.f("ix_offer_phone_number"), "offer", ["phone_number"], unique=False)
    op.create_index(op.f("ix_offer_user_id"), "offer", ["user_id"], unique=False)
    op.create_index(op.f("ix_demand_phone_number"), "demand", ["phone_number"], unique=False)
    op.create_index(op.f("ix_demand_user_id"), "demand", ["user_id"], unique=False)
    op.drop_table("demanduser")
    op.drop_table("offeruser")

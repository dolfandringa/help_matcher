"""add help record geometry

Revision ID: 9bfb7f6b0f4c
Revises: d1cfd01d0f0b
Create Date: 2026-08-13 14:49:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9bfb7f6b0f4c"
down_revision: Union[str, None] = "d1cfd01d0f0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "offer",
        sa.Column(
            "geometry",
            geoalchemy2.Geometry(
                geometry_type="GEOMETRY",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "demand",
        sa.Column(
            "geometry",
            geoalchemy2.Geometry(
                geometry_type="GEOMETRY",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_offer_geometry_gist", "offer", ["geometry"], unique=False, postgresql_using="gist")
    op.create_index("ix_demand_geometry_gist", "demand", ["geometry"], unique=False, postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("ix_demand_geometry_gist", table_name="demand")
    op.drop_index("ix_offer_geometry_gist", table_name="offer")
    op.drop_column("demand", "geometry")
    op.drop_column("offer", "geometry")

"""add equipment table

Revision ID: 4ecede3a6f58
Revises: a1b2c3d4e5f6
Create Date: 2026-03-17 09:16:55.165098

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = "4ecede3a6f58"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_by", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column(
            "manufacturer", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column(
            "serial_number", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column(
            "system_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column(
            "category", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("room", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("estimated_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "status", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False
        ),
        sa.Column("is_api_controllable", sa.Boolean(), nullable=False),
        sa.Column(
            "api_interface", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photos", sa.JSON(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_category"), "equipment", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_equipment_location_id"), "equipment", ["location_id"], unique=False
    )
    op.create_index(
        op.f("ix_equipment_manufacturer"), "equipment", ["manufacturer"], unique=False
    )
    op.create_index(op.f("ix_equipment_name"), "equipment", ["name"], unique=False)
    op.create_index(op.f("ix_equipment_status"), "equipment", ["status"], unique=False)
    op.create_index(
        op.f("ix_equipment_system_id"), "equipment", ["system_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_equipment_system_id"), table_name="equipment")
    op.drop_index(op.f("ix_equipment_status"), table_name="equipment")
    op.drop_index(op.f("ix_equipment_name"), table_name="equipment")
    op.drop_index(op.f("ix_equipment_manufacturer"), table_name="equipment")
    op.drop_index(op.f("ix_equipment_location_id"), table_name="equipment")
    op.drop_index(op.f("ix_equipment_category"), table_name="equipment")
    op.drop_table("equipment")

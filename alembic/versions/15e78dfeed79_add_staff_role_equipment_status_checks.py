"""add CHECK constraints for staff.role and equipment.status

Revision ID: 15e78dfeed79
Revises: 4046478f7b78
Create Date: 2026-03-20

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15e78dfeed79"
down_revision: Union[str, None] = "4046478f7b78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_STAFF_ROLES = (
    "admin",
    "researcher",
    "lab_manager",
    "technician",
    "viewer",
    "member",
    "PI",
)

VALID_EQUIPMENT_STATUSES = (
    "active",
    "maintenance",
    "broken",
    "decommissioned",
    "deleted",
)


def upgrade() -> None:
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        f"role IN ({','.join(repr(v) for v in VALID_STAFF_ROLES)})",
    )
    op.create_check_constraint(
        "ck_equipment_status",
        "equipment",
        f"status IN ({','.join(repr(v) for v in VALID_EQUIPMENT_STATUSES)})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_equipment_status", "equipment", type_="check")
    op.drop_constraint("ck_staff_role", "staff", type_="check")

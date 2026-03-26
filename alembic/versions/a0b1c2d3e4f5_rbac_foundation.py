"""RBAC foundation: staff columns, invitations table, role update

Revision ID: a0b1c2d3e4f5
Revises: 15e78dfeed79
Create Date: 2026-03-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "15e78dfeed79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ROLES = ("pi", "admin", "postdoc", "grad_student", "tech", "undergrad", "visitor")

# Mapping from old roles to new RBAC roles
_OLD_TO_NEW = {
    "PI": "pi",
    "admin": "admin",
    "lab_manager": "admin",
    "researcher": "postdoc",
    "technician": "tech",
    "member": "grad_student",
    "viewer": "visitor",
}

_ROLE_LEVEL = {
    "pi": 0,
    "admin": 1,
    "postdoc": 2,
    "grad_student": 3,
    "tech": 3,
    "undergrad": 4,
    "visitor": 4,
}


def upgrade() -> None:
    # 1. Drop old CHECK constraint on staff.role
    op.drop_constraint("ck_staff_role", "staff", type_="check")

    # 2. Add new columns to staff (with server_default for NOT NULL)
    op.add_column(
        "staff",
        sa.Column("role_level", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "staff",
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("staff.id"), nullable=True),
    )
    op.add_column("staff", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("staff", sa.Column("access_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "staff",
        sa.Column(
            "failed_login_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column("staff", sa.Column("locked_until", sa.DateTime(), nullable=True))

    # 3. Data migration: map old roles to new
    conn = op.get_bind()
    for old_role, new_role in _OLD_TO_NEW.items():
        level = _ROLE_LEVEL[new_role]
        conn.execute(
            sa.text(
                "UPDATE staff SET role = :new_role, role_level = :level "
                "WHERE role = :old_role"
            ),
            {"new_role": new_role, "old_role": old_role, "level": level},
        )
    # Catch any unmapped roles -> default to grad_student
    conn.execute(
        sa.text(
            "UPDATE staff SET role = 'grad_student', role_level = 3 "
            "WHERE role NOT IN :roles"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {"roles": list(NEW_ROLES)},
    )

    # 4. Add new CHECK constraint with 7 roles
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        f"role IN ({','.join(repr(v) for v in NEW_ROLES)})",
    )

    # 5. Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("token", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("staff.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("access_expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # Drop invitations table
    op.drop_table("invitations")

    # Drop new CHECK constraint
    op.drop_constraint("ck_staff_role", "staff", type_="check")

    # Reverse data migration: map new roles back to old
    conn = op.get_bind()
    _NEW_TO_OLD = {v: k for k, v in _OLD_TO_NEW.items()}
    for new_role, old_role in _NEW_TO_OLD.items():
        conn.execute(
            sa.text("UPDATE staff SET role = :old_role WHERE role = :new_role"),
            {"old_role": old_role, "new_role": new_role},
        )

    # Remove new columns
    op.drop_column("staff", "locked_until")
    op.drop_column("staff", "failed_login_count")
    op.drop_column("staff", "access_expires_at")
    op.drop_column("staff", "last_login_at")
    op.drop_column("staff", "invited_by")
    op.drop_column("staff", "role_level")

    # Restore old CHECK constraint
    OLD_ROLES = (
        "admin",
        "researcher",
        "lab_manager",
        "technician",
        "viewer",
        "member",
        "PI",
    )
    op.create_check_constraint(
        "ck_staff_role",
        "staff",
        f"role IN ({','.join(repr(v) for v in OLD_ROLES)})",
    )

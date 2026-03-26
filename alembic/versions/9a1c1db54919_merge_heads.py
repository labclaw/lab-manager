"""merge_heads

Revision ID: 9a1c1db54919
Revises: a0b1c2d3e4f5, a2b3c4d5e6f7, b1c2d3e4f5a6
Create Date: 2026-03-26 13:22:44.388865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9a1c1db54919'
down_revision: Union[str, None] = ('a0b1c2d3e4f5', 'a2b3c4d5e6f7', 'b1c2d3e4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

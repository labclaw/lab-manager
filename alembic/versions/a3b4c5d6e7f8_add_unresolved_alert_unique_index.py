"""add partial unique index on unresolved alerts

Revision ID: a3b4c5d6e7f8
Revises: 0c2125df7c3a
Create Date: 2026-03-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "0c2125df7c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate any existing rows before creating the unique index.
    op.execute(
        """
        DELETE FROM alerts a1 USING alerts a2
        WHERE a1.id > a2.id
          AND a1.entity_type = a2.entity_type
          AND a1.entity_id = a2.entity_id
          AND a1.alert_type = a2.alert_type
          AND NOT a1.is_resolved
          AND NOT a2.is_resolved
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_alerts_unresolved_key
        ON alerts (entity_type, entity_id, alert_type)
        WHERE NOT is_resolved
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_alerts_unresolved_key")

"""Add PubChem enrichment columns to products table.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("molecular_weight", sa.Float(), nullable=True))
    op.add_column(
        "products", sa.Column("molecular_formula", sa.String(200), nullable=True)
    )
    op.add_column("products", sa.Column("smiles", sa.String(2000), nullable=True))
    op.add_column("products", sa.Column("pubchem_cid", sa.Integer(), nullable=True))
    op.create_index("ix_products_pubchem_cid", "products", ["pubchem_cid"])


def downgrade() -> None:
    op.drop_index("ix_products_pubchem_cid", "products")
    op.drop_column("products", "pubchem_cid")
    op.drop_column("products", "smiles")
    op.drop_column("products", "molecular_formula")
    op.drop_column("products", "molecular_weight")

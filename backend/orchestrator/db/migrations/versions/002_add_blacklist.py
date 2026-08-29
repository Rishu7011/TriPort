"""
Migration 002 — Add blacklist table.

Revision ID: 002
Revises: 001
Create Date: 2026-08-29
"""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blacklist",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_number", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("date_of_birth", sa.Text(), nullable=True),
        sa.Column("nationality", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False, server_default="banned"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_blacklist_doc_num", "blacklist", ["document_number"])
    op.create_index("ix_blacklist_full_name", "blacklist", ["full_name"])


def downgrade() -> None:
    op.drop_index("ix_blacklist_full_name", table_name="blacklist")
    op.drop_index("ix_blacklist_doc_num", table_name="blacklist")
    op.drop_table("blacklist")

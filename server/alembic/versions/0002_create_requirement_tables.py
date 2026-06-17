"""create requirement_sources, requirement_plans, change_records tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("original_file_path", sa.String(1000), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "requirement_plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "change_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("change_records")
    op.drop_table("requirement_plans")
    op.drop_table("requirement_sources")

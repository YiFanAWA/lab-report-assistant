"""create outlines, deliverables, deliverable_versions tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22

SPEC 0006 大纲与交付物：新增 3 张表。
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlines",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("sections_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("code_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_outlines_project_id", "outlines", ["project_id"])

    op.create_table(
        "deliverables",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("outline_id", sa.String(32), nullable=False),
        sa.Column("deliverable_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_deliverables_project_id", "deliverables", ["project_id"])
    op.create_index("ix_deliverables_outline_id", "deliverables", ["outline_id"])

    op.create_table(
        "deliverable_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("deliverable_id", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_deliverable_versions_deliverable_id",
        "deliverable_versions",
        ["deliverable_id"],
    )
    op.create_index(
        "ix_deliverable_versions_project_id",
        "deliverable_versions",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deliverable_versions_project_id", table_name="deliverable_versions"
    )
    op.drop_index(
        "ix_deliverable_versions_deliverable_id", table_name="deliverable_versions"
    )
    op.drop_table("deliverable_versions")

    op.drop_index("ix_deliverables_outline_id", table_name="deliverables")
    op.drop_index("ix_deliverables_project_id", table_name="deliverables")
    op.drop_table("deliverables")

    op.drop_index("ix_outlines_project_id", table_name="outlines")
    op.drop_table("outlines")

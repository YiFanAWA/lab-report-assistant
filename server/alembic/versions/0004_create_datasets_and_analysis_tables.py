"""create datasets, dataset_versions, analysis_plans tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("dataset_kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("dataset_id", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("profile_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    op.create_index("ix_dataset_versions_project_id", "dataset_versions", ["project_id"])

    op.create_table(
        "analysis_plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("dataset_id", sa.String(32), nullable=False),
        sa.Column("dataset_version_id", sa.String(32), nullable=False),
        sa.Column("cleaning_plan", sa.Text(), nullable=False),
        sa.Column("analysis_plan", sa.Text(), nullable=False),
        sa.Column("chart_plan", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analysis_plans_project_id", "analysis_plans", ["project_id"])
    op.create_index("ix_analysis_plans_dataset_id", "analysis_plans", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_plans_dataset_id", table_name="analysis_plans")
    op.drop_index("ix_analysis_plans_project_id", table_name="analysis_plans")
    op.drop_table("analysis_plans")

    op.drop_index("ix_dataset_versions_project_id", table_name="dataset_versions")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")

    op.drop_index("ix_datasets_project_id", table_name="datasets")
    op.drop_table("datasets")

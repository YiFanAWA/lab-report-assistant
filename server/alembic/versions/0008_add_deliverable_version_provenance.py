"""add deliverable version provenance fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-23

交付审阅台：为新生成版本保存可追溯来源；历史版本保持可空。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deliverable_versions",
        sa.Column("outline_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("dataset_version_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("dataset_version_ids_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("analysis_plan_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("analysis_plan_ids_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("execution_run_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("execution_run_ids_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("source_word_version_id", sa.String(32), nullable=True),
    )
    op.add_column(
        "deliverable_versions",
        sa.Column("file_sha256", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    for column in (
        "file_sha256",
        "source_word_version_id",
        "execution_run_ids_json",
        "execution_run_id",
        "analysis_plan_ids_json",
        "analysis_plan_id",
        "dataset_version_ids_json",
        "dataset_version_id",
        "outline_version",
    ):
        op.drop_column("deliverable_versions", column)

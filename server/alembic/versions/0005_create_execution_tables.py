"""create code_tasks, execution_runs, execution_artifacts tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("analysis_plan_id", sa.String(32), nullable=False),
        sa.Column("dataset_id", sa.String(32), nullable=False),
        sa.Column("dataset_version_id", sa.String(32), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_code_tasks_project_id", "code_tasks", ["project_id"])
    op.create_index("ix_code_tasks_analysis_plan_id", "code_tasks", ["analysis_plan_id"])

    op.create_table(
        "execution_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("code_task_id", sa.String(32), nullable=False),
        sa.Column("dataset_version_id", sa.String(32), nullable=False),
        sa.Column("code_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=False),
        sa.Column("stderr", sa.Text(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_execution_runs_project_id", "execution_runs", ["project_id"])
    op.create_index("ix_execution_runs_code_task_id", "execution_runs", ["code_task_id"])

    op.create_table(
        "execution_artifacts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("execution_run_id", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_execution_artifacts_execution_run_id", "execution_artifacts", ["execution_run_id"])
    op.create_index("ix_execution_artifacts_project_id", "execution_artifacts", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_artifacts_project_id", table_name="execution_artifacts")
    op.drop_index("ix_execution_artifacts_execution_run_id", table_name="execution_artifacts")
    op.drop_table("execution_artifacts")

    op.drop_index("ix_execution_runs_code_task_id", table_name="execution_runs")
    op.drop_index("ix_execution_runs_project_id", table_name="execution_runs")
    op.drop_table("execution_runs")

    op.drop_index("ix_code_tasks_analysis_plan_id", table_name="code_tasks")
    op.drop_index("ix_code_tasks_project_id", table_name="code_tasks")
    op.drop_table("code_tasks")

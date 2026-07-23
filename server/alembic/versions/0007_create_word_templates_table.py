"""create word_templates table

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-23

SPEC 0010 Word 模板支持：新增 word_templates 表，每项目唯一约束。
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "word_templates",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "project_id", name="uq_word_templates_project_id"
        ),
    )
    op.create_index("ix_word_templates_project_id", "word_templates", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_word_templates_project_id", table_name="word_templates")
    op.drop_table("word_templates")

"""create sources, parsed_documents, evidence_cards, background_jobs tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sources_project_id", "sources", ["project_id"])

    op.create_table(
        "parsed_documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("parsed_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_parsed_documents_source_id", "parsed_documents", ["source_id"])
    op.create_index("ix_parsed_documents_project_id", "parsed_documents", ["project_id"])

    op.create_table(
        "evidence_cards",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("parsed_document_id", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("locator", sa.String(200), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_evidence_cards_project_id", "evidence_cards", ["project_id"])
    op.create_index("ix_evidence_cards_source_id", "evidence_cards", ["source_id"])

    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_background_jobs_project_id", "background_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_project_id", table_name="background_jobs")
    op.drop_table("background_jobs")

    op.drop_index("ix_evidence_cards_source_id", table_name="evidence_cards")
    op.drop_index("ix_evidence_cards_project_id", table_name="evidence_cards")
    op.drop_table("evidence_cards")

    op.drop_index("ix_parsed_documents_project_id", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_source_id", table_name="parsed_documents")
    op.drop_table("parsed_documents")

    op.drop_index("ix_sources_project_id", table_name="sources")
    op.drop_table("sources")

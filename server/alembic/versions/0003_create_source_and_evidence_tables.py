"""create source_records, parsed_documents, evidence_cards tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
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
        "source_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("original_file_path", sa.String(1000), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("collection_status", sa.String(32), nullable=False),
        sa.Column("access_reason", sa.String(1000), nullable=True),
        sa.Column("content_type", sa.String(200), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "parsed_documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("parser_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("parsed_text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("location_map_json", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.String(32), nullable=False),
        sa.Column("parse_error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "evidence_cards",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("parsed_document_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("source_quote", sa.String(2000), nullable=False),
        sa.Column("location_label", sa.String(500), nullable=False),
        sa.Column("relevance_to_requirement", sa.String(1000), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("evidence_cards")
    op.drop_table("parsed_documents")
    op.drop_table("source_records")

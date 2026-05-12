"""add_resumes_table

Revision ID: c3a8b7a6d4e1
Revises: 2bb91f2c6d1e
Create Date: 2026-05-12 17:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.types import Vector


# revision identifiers, used by Alembic.
revision: str = "c3a8b7a6d4e1"
down_revision: Union[str, None] = "2bb91f2c6d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("structural_score", sa.Float(), nullable=True),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("ats_score", sa.Float(), nullable=True),
        sa.Column("optimised_resume_path", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], unique=False)
    op.create_index(
        "uq_resumes_user_primary_active",
        "resumes",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_resumes_user_primary_active", table_name="resumes")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.drop_table("resumes")

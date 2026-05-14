"""add_companies_table_for_jobs

Revision ID: 30ef551b0dbe
Revises: c3a8b7a6d4e1
Create Date: 2026-05-14 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "30ef551b0dbe"
down_revision: Union[str, None] = "c3a8b7a6d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("careers_page_url", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("industry", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("size_range", sa.String(), nullable=True),
        sa.Column("funding_stage", sa.String(), nullable=True),
        sa.Column("hq_location", sa.String(), nullable=True),
        sa.Column("is_india_based", sa.Boolean(), nullable=True),
        sa.Column("tech_stack", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website"),
    )


def downgrade() -> None:
    op.drop_table("companies")

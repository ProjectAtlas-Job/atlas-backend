"""add_hnsw_indexes

Revision ID: 5bc1d85af17c
Revises: d5f1d1e7c2ab
Create Date: 2026-05-15 21:32:14.854893

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5bc1d85af17c'
down_revision: Union[str, None] = 'd5f1d1e7c2ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_postings_embedding "
            "ON job_postings USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resumes_embedding "
            "ON resumes USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_companies_embedding "
            "ON companies USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64);"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_job_postings_embedding;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_resumes_embedding;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_companies_embedding;")

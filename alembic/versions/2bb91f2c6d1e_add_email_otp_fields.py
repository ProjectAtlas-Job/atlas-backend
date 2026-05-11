"""add_email_otp_fields

Revision ID: 2bb91f2c6d1e
Revises: 6f0d9986606a
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2bb91f2c6d1e"
down_revision: Union[str, None] = "6f0d9986606a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_otp_code_hash", sa.String(), nullable=True))
    op.add_column("users", sa.Column("email_otp_expires", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("email_otp_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_otp_sent_at")
    op.drop_column("users", "email_otp_expires")
    op.drop_column("users", "email_otp_code_hash")

"""add_action_logs_for_scraper_tasks

Revision ID: 5b9c2ef12b44
Revises: 9f5ab90d2c41
Create Date: 2026-05-14 22:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b9c2ef12b44"
down_revision: Union[str, None] = "9f5ab90d2c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(op.f("ix_action_logs_action_type"), "action_logs", ["action_type"], unique=False)
    op.create_index(op.f("ix_action_logs_status"), "action_logs", ["status"], unique=False)
    op.create_index(op.f("ix_action_logs_task_id"), "action_logs", ["task_id"], unique=False)
    op.create_index(op.f("ix_action_logs_user_id"), "action_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_action_logs_user_id"), table_name="action_logs")
    op.drop_index(op.f("ix_action_logs_task_id"), table_name="action_logs")
    op.drop_index(op.f("ix_action_logs_status"), table_name="action_logs")
    op.drop_index(op.f("ix_action_logs_action_type"), table_name="action_logs")
    op.drop_table("action_logs")

"""add stt_daily_usage

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stt_daily_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("sessions", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stt_daily_usage")

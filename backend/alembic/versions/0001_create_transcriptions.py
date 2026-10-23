"""create transcriptions table

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("languages", sa.String(length=50), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transcriptions_created_at", "transcriptions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transcriptions_created_at", table_name="transcriptions")
    op.drop_table("transcriptions")

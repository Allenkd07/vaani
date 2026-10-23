"""add owner_id to transcriptions

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Pre-existing rows had no owner; this value can never equal a 64-char hash, so they become unreachable.
UNOWNED = "unowned"


def upgrade() -> None:
    op.add_column("transcriptions", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.execute(sa.text("UPDATE transcriptions SET owner_id = :owner").bindparams(owner=UNOWNED))
    op.alter_column("transcriptions", "owner_id", nullable=False)
    op.drop_index("ix_transcriptions_created_at", table_name="transcriptions")
    op.create_index("ix_transcriptions_owner_created", "transcriptions", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_transcriptions_owner_created", table_name="transcriptions")
    op.create_index("ix_transcriptions_created_at", "transcriptions", ["created_at"])
    op.drop_column("transcriptions", "owner_id")

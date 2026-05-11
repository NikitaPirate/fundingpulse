"""Add ingestion task queue control table

Revision ID: 009
Revises: 008
Create Date: 2026-05-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ingestion_task",
        sa.Column("task_key", sa.Text(), nullable=False),
        sa.Column("pipeline", sa.Text(), nullable=False),
        sa.Column("exchange_name", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ingestion_task_status_check",
        ),
        sa.PrimaryKeyConstraint("task_key"),
    )
    op.create_index(
        "ix_ingestion_task_pending_claim",
        "ingestion_task",
        ["pipeline", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_ingestion_task_active_exchange",
        "ingestion_task",
        ["pipeline", "exchange_name"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_ingestion_task_running_claimed_at",
        "ingestion_task",
        ["pipeline", "claimed_at"],
        unique=False,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ingestion_task_running_claimed_at", table_name="ingestion_task")
    op.drop_index("ix_ingestion_task_active_exchange", table_name="ingestion_task")
    op.drop_index("ix_ingestion_task_pending_claim", table_name="ingestion_task")
    op.drop_table("ingestion_task")

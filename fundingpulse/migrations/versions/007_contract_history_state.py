"""Move historical sync state out of contract

Revision ID: 007
Revises: 006
Create Date: 2026-04-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "contract_history_state",
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("history_synced", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("oldest_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("newest_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contract.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "history_synced = false "
            "OR (oldest_timestamp IS NOT NULL AND newest_timestamp IS NOT NULL)",
            name="contract_history_state_synced_has_bounds",
        ),
        sa.PrimaryKeyConstraint("contract_id"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO contract_history_state (
                contract_id,
                history_synced,
                oldest_timestamp,
                newest_timestamp,
                updated_at
            )
            SELECT
                c.id,
                CASE
                    WHEN c.synced = true AND bounds.oldest_timestamp IS NOT NULL THEN true
                    ELSE false
                END AS history_synced,
                bounds.oldest_timestamp,
                bounds.newest_timestamp,
                NOW() AS updated_at
            FROM contract AS c
            LEFT JOIN (
                SELECT
                    contract_id,
                    MIN(timestamp) AS oldest_timestamp,
                    MAX(timestamp) AS newest_timestamp
                FROM historical_funding_point
                GROUP BY contract_id
            ) AS bounds ON bounds.contract_id = c.id;
            """
        )
    )

    op.drop_column("contract", "synced")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "contract",
        sa.Column("synced", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute(
        sa.text(
            """
            UPDATE contract AS c
            SET synced = chs.history_synced
            FROM contract_history_state AS chs
            WHERE chs.contract_id = c.id;
            """
        )
    )
    op.alter_column("contract", "synced", server_default=None)
    op.drop_table("contract_history_state")

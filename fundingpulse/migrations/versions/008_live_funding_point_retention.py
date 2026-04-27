"""Add retention policy for raw live funding points

Revision ID: 008
Revises: 007
Create Date: 2026-04-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                """
                SELECT remove_retention_policy(
                    'live_funding_point',
                    if_exists => true
                );
                """
            )
        )

    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                """
                SELECT add_retention_policy(
                    'live_funding_point',
                    INTERVAL '6 hours'
                );
                """
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            sa.text(
                """
                SELECT remove_retention_policy(
                    'live_funding_point',
                    if_exists => true
                );
                """
            )
        )

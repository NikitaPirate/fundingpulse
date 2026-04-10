"""Funding helpers for funding rate normalization

Revision ID: 002
Revises: 001
Create Date: 2026-01-29 18:52:28.114331

Creates helper function get_funding_multiplier for normalizing funding rates
across different funding intervals.

Changes:
- get_funding_multiplier(integer, numeric) -> numeric
  Returns multiplier for converting funding rates to target time period
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE FUNCTION get_funding_multiplier(funding_interval INTEGER, target_hours NUMERIC)
        RETURNS NUMERIC AS $$
        BEGIN
            RETURN CASE funding_interval
                WHEN 1 THEN target_hours
                WHEN 2 THEN target_hours / 2.0
                WHEN 4 THEN target_hours / 4.0
                WHEN 8 THEN target_hours / 8.0
                ELSE target_hours / funding_interval
            END;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP FUNCTION IF EXISTS get_funding_multiplier(INTEGER, NUMERIC);"))

"""Smart view for seamless funding data access across time granularities

Revision ID: 005
Revises: 004
Create Date: 2026-01-29 18:52:53.337290

Creates lfp_smart view that provides unified access to funding data across
different time granularities (raw, 5m, 15m, 1h aggregates).

Data Structure Architecture:
- 0-3h:   Raw data (live_funding_point) - second precision
- 3h-3d:  5min aggregates (lfp_5min)
- 3d-7d:  15min aggregates (lfp_15min)
- 7d-30d: 1hour aggregates (lfp_1hour)

The view automatically shifts bucket timestamps to the END of each interval
for consistent time series representation.

Changes:
- Creates lfp_smart view as UNION ALL of 4 data sources
- Each layer has proper time bounds to prevent overlaps/gaps
- Ordered by bucket, contract_id for predictable results
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE VIEW lfp_smart AS
        SELECT bucket, contract_id, avg_funding_rate
        FROM (
            -- Layer 1: Raw data (0-3h) - no aggregation
            SELECT
                timestamp AS bucket,
                contract_id,
                funding_rate AS avg_funding_rate
            FROM live_funding_point
            WHERE timestamp >= NOW() - INTERVAL '3 hours'

            UNION ALL

            -- Layer 2: 5min aggregates (3h-3d) - shifted to interval end
            SELECT
                bucket + INTERVAL '5 minutes' AS bucket,
                contract_id,
                avg_funding_rate
            FROM lfp_5min
            WHERE bucket >= NOW() - INTERVAL '3 days'
              AND bucket < NOW() - INTERVAL '3 hours'

            UNION ALL

            -- Layer 3: 15min aggregates (3d-7d) - shifted to interval end
            SELECT
                bucket + INTERVAL '15 minutes' AS bucket,
                contract_id,
                avg_funding_rate
            FROM lfp_15min
            WHERE bucket >= NOW() - INTERVAL '7 days'
              AND bucket < NOW() - INTERVAL '3 days'

            UNION ALL

            -- Layer 4: 1hour aggregates (7d-30d) - shifted to interval end
            SELECT
                bucket + INTERVAL '1 hour' AS bucket,
                contract_id,
                avg_funding_rate
            FROM lfp_1hour
            WHERE bucket >= NOW() - INTERVAL '30 days'
              AND bucket < NOW() - INTERVAL '7 days'
        ) combined
        ORDER BY bucket, contract_id;
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS lfp_smart CASCADE;"))

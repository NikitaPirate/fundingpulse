"""TimescaleDB continuous aggregates for live funding data optimization

Revision ID: 004
Revises: 003
Create Date: 2026-01-29 18:52:52.915364

Creates TimescaleDB continuous aggregates to optimize data storage and query
performance for live_funding_point table.

Data Structure Architecture:
- 0-3h:   Raw data (live_funding_point) - accessed via smart view
- 5m-3d:  lfp_5min continuous aggregate
- 15m-7d: lfp_15min continuous aggregate
- 1h-30d: lfp_1hour continuous aggregate

Changes:
1. Creates 3 continuous aggregates (lfp_5min, lfp_15min, lfp_1hour)
2. Backfills historical data for required ranges (3d/7d/30d)
3. Sets up refresh policies for automatic updates
4. Sets up retention policies for continuous aggregates

NOTE: Uses autocommit_block() because TimescaleDB functions cannot run
inside transactions. Each operation commits immediately.

TIMESCALEDB MIGRATION BEST PRACTICES:
- DROP IF EXISTS before CREATE makes migration IDEMPOTENT
- autocommit_block() disables transaction wrapping
- Operations CANNOT be rolled back - test locally first
- IF EXISTS + CASCADE enables safe re-runs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # Step 1: Create Continuous Aggregates (WITHOUT DATA)
    # ============================================================

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            DROP MATERIALIZED VIEW IF EXISTS lfp_5min CASCADE;
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CREATE MATERIALIZED VIEW lfp_5min
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('5 minutes', timestamp) AS bucket,
                contract_id,
                AVG(funding_rate) AS avg_funding_rate
            FROM live_funding_point
            GROUP BY time_bucket('5 minutes', timestamp), contract_id
            WITH NO DATA;
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            DROP MATERIALIZED VIEW IF EXISTS lfp_15min CASCADE;
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CREATE MATERIALIZED VIEW lfp_15min
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('15 minutes', timestamp) AS bucket,
                contract_id,
                AVG(funding_rate) AS avg_funding_rate
            FROM live_funding_point
            GROUP BY time_bucket('15 minutes', timestamp), contract_id
            WITH NO DATA;
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            DROP MATERIALIZED VIEW IF EXISTS lfp_1hour CASCADE;
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CREATE MATERIALIZED VIEW lfp_1hour
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', timestamp) AS bucket,
                contract_id,
                AVG(funding_rate) AS avg_funding_rate
            FROM live_funding_point
            GROUP BY time_bucket('1 hour', timestamp), contract_id
            WITH NO DATA;
        """))

    # ============================================================
    # Step 2: Backfill (ONLY REQUIRED RANGES!)
    # ============================================================

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CALL refresh_continuous_aggregate('lfp_5min',
                (NOW() - INTERVAL '3 days')::TIMESTAMP,
                NOW()::TIMESTAMP
            );
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CALL refresh_continuous_aggregate('lfp_15min',
                (NOW() - INTERVAL '7 days')::TIMESTAMP,
                NOW()::TIMESTAMP
            );
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            CALL refresh_continuous_aggregate('lfp_1hour',
                (NOW() - INTERVAL '30 days')::TIMESTAMP,
                NOW()::TIMESTAMP
            );
        """))

    # ============================================================
    # Step 3: Refresh Policies (Auto-Update)
    # ============================================================

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_continuous_aggregate_policy('lfp_5min', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_continuous_aggregate_policy('lfp_5min',
                start_offset => INTERVAL '3 hours',
                end_offset => INTERVAL '5 minutes',
                schedule_interval => INTERVAL '30 minutes'
            );
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_continuous_aggregate_policy('lfp_15min', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_continuous_aggregate_policy('lfp_15min',
                start_offset => INTERVAL '12 hours',
                end_offset => INTERVAL '15 minutes',
                schedule_interval => INTERVAL '1 hour'
            );
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_continuous_aggregate_policy('lfp_1hour', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_continuous_aggregate_policy('lfp_1hour',
                start_offset => INTERVAL '2 days',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '4 hours'
            );
        """))

    # ============================================================
    # Step 4: Retention Policies for Continuous Aggregates
    # ============================================================

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_retention_policy('lfp_5min', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_retention_policy('lfp_5min', INTERVAL '3 days');
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_retention_policy('lfp_15min', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_retention_policy('lfp_15min', INTERVAL '7 days');
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT remove_retention_policy('lfp_1hour', if_exists => true);
        """))

    with op.get_context().autocommit_block():
        op.execute(sa.text("""
            SELECT add_retention_policy('lfp_1hour', INTERVAL '30 days');
        """))


def downgrade() -> None:
    # Remove retention policies
    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_retention_policy('lfp_5min', if_exists => true);"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_retention_policy('lfp_15min', if_exists => true);"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_retention_policy('lfp_1hour', if_exists => true);"))

    # Remove refresh policies
    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_continuous_aggregate_policy('lfp_5min', if_exists => true);"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_continuous_aggregate_policy('lfp_15min', if_exists => true);"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("SELECT remove_continuous_aggregate_policy('lfp_1hour', if_exists => true);"))

    # Drop continuous aggregates
    with op.get_context().autocommit_block():
        op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS lfp_5min CASCADE;"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS lfp_15min CASCADE;"))

    with op.get_context().autocommit_block():
        op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS lfp_1hour CASCADE;"))

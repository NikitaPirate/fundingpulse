"""Contract enriched materialized view with precomputed funding multipliers

Revision ID: 003
Revises: 002
Create Date: 2026-01-29 18:52:52.495557

Creates materialized view contract_enriched with precomputed funding multipliers
for normalizing funding rates to different time periods (1h, 8h, 1d, 365d).

Changes:
1. Creates materialized view contract_enriched (WITH NO DATA)
2. Creates unique index on id (for CONCURRENTLY refresh)
3. Creates indexes on asset_name, quote_name, section_name
4. REFRESH materialized view to populate data

NOTE: Materialized view must be refreshed after creation because pg_dump
exports it with WITH NO DATA.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create materialized view (WITH NO DATA)
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW contract_enriched AS
        SELECT
            c.id,
            c.asset_name,
            c.quote_name,
            c.funding_interval,
            s.name AS section_name,
            c.deprecated,
            get_funding_multiplier(c.funding_interval, 1::NUMERIC) AS multiplier_1h,
            get_funding_multiplier(c.funding_interval, 8::NUMERIC) AS multiplier_8h,
            get_funding_multiplier(c.funding_interval, 24::NUMERIC) AS multiplier_1d,
            get_funding_multiplier(c.funding_interval, 8760::NUMERIC) AS multiplier_365d
        FROM contract c
        JOIN section s ON (c.section_name::TEXT = s.name::TEXT)
        WHERE c.deprecated = false
        WITH NO DATA;
    """))

    # Create unique index on id (required for CONCURRENTLY refresh)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX contract_enriched_id_idx ON contract_enriched (id);
    """))

    # Create additional indexes for common queries
    op.execute(sa.text("""
        CREATE INDEX contract_enriched_asset_name_idx ON contract_enriched (asset_name);
    """))

    op.execute(sa.text("""
        CREATE INDEX contract_enriched_quote_name_idx ON contract_enriched (quote_name);
    """))

    op.execute(sa.text("""
        CREATE INDEX contract_enriched_section_name_idx ON contract_enriched (section_name);
    """))

    # REFRESH to populate data (required after creation with NO DATA)
    op.execute(sa.text("REFRESH MATERIALIZED VIEW contract_enriched;"))


def downgrade() -> None:
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS contract_enriched CASCADE;"))

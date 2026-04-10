"""contract_search_migration

Revision ID: 006
Revises: 005
Create Date: 2026-02-05 16:19:30.726561

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, Sequence[str], None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_quality(
          field_value TEXT,
          search_token TEXT
        ) RETURNS INTEGER AS $$
        DECLARE
          field_lower TEXT;
          token_lower TEXT;
          token_len INTEGER;
          field_len INTEGER;
          sim_score REAL;
        BEGIN
          field_lower := lower(trim(field_value));
          token_lower := lower(trim(search_token));

          IF field_lower = '' OR token_lower = '' THEN
            RETURN 0;
          END IF;

          token_len := length(token_lower);
          field_len := length(field_lower);

          -- Special handling for short tokens (1-2 chars)
          IF token_len <= 2 THEN
            IF field_lower = token_lower THEN
              RETURN 10000;
            END IF;

            IF field_lower LIKE token_lower || '%' THEN
              RETURN 8000 + (2000 * token_len / field_len)::INTEGER;
            END IF;

            IF field_lower ~ ('(^|[^a-z0-9])' || token_lower || '([^a-z0-9]|$)') THEN
              RETURN 5000;
            END IF;

            IF field_lower LIKE '%' || token_lower || '%' THEN
              RETURN 300;
            END IF;

            RETURN 0;
          END IF;

          -- Normal handling for 3+ chars
          IF field_lower = token_lower THEN
            RETURN 10000;
          END IF;

          IF field_lower LIKE token_lower || '%' THEN
            RETURN 5000 + (5000 * token_len / field_len)::INTEGER;
          END IF;

          IF field_lower ~ ('(^|[^a-z0-9])' || token_lower) THEN
            RETURN 2000;
          END IF;

          IF field_lower LIKE '%' || token_lower || '%' THEN
            RETURN 500;
          END IF;

          sim_score := similarity(field_lower, token_lower);

          IF sim_score > 0.2 THEN
            RETURN (sim_score * 300)::INTEGER;
          END IF;

          RETURN 0;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS contract_search_trgm_idx ON contract USING GIN (
          (lower(asset_name) || ' ' || lower(section_name) || ' ' || lower(quote_name))
          gin_trgm_ops
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS contract_search_trgm_idx;")
    op.execute("DROP FUNCTION IF EXISTS match_quality(TEXT, TEXT);")

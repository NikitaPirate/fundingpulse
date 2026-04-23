from logging.config import fileConfig

import alembic_postgresql_enum
import sqlalchemy_timescaledb  # noqa: F401 need for dialect registration
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from fundingpulse.models import (  # noqa: F401
    Asset,
    Contract,
    ContractHistoryState,
    HistoricalFundingPoint,
    LiveFundingPoint,
    Quote,
    Section,
)
from fundingpulse.db_settings import DBSettings

alembic_postgresql_enum.set_configuration(
    alembic_postgresql_enum.Config(force_dialect_support=True)
)

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata


def get_url():
    """Build TimescaleDB connection URL from environment variables."""
    return DBSettings().connection_url


def process_revision_directives(context, revision, directives):
    """Generate sequential revision IDs instead of random hashes.

    Creates revisions like: 001, 002, 003, etc.
    """
    if not directives:
        return

    migration_script = directives[0]

    # Get the script directory and find the current head
    script_dir = ScriptDirectory.from_config(context.config)
    head_revision = script_dir.get_current_head()

    if head_revision is None:
        # First migration
        new_rev_id = 1
    else:
        # Try to parse the last revision as a number
        try:
            last_rev_id = int(head_revision.lstrip("0"))
            new_rev_id = last_rev_id + 1
        except ValueError:
            # Fallback if existing revisions use hash format
            # Count existing migrations
            revisions = list(script_dir.walk_revisions())
            new_rev_id = len(revisions) + 1

    # Format with zero padding (001, 002, 003, etc.)
    migration_script.rev_id = f"{new_rev_id:03d}"


def include_object(object_, name, type_, reflected, compare_to):
    """
    Filter out auto-generated TimescaleDB indexes from autogenerate comparisons.

    TimescaleDB automatically creates indexes for hypertables that should not
    be managed by Alembic migrations.
    """
    return not (
        type_ == "index"
        and name
        in {
            "historical_funding_point_timestamp_idx",
            "live_funding_point_timestamp_idx",
        }
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=process_revision_directives,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Set the sqlalchemy.url from environment before running migrations
    config.set_main_option("sqlalchemy.url", get_url())

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            process_revision_directives=process_revision_directives,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

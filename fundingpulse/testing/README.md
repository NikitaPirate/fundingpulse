# Testing

FundingPulse tests use a real TimescaleDB container for the paths where database
behavior matters. That is intentional: hypertables, materialized views,
continuous aggregates, SQL conflict handling, and time-series queries are part
of the system design, not details that a lightweight fake can represent.

The shared testing package provides fixtures and helpers for those integration
tests without hiding the database boundary.

## What It Provides

- Testcontainers-backed database lifecycle.
- Async SQLAlchemy engine and session fixtures.
- Table truncation helpers for isolated test cases.
- Materialized view refresh helpers for query tests that depend on derived
  views.
- Small data builders for assets, sections, quotes, contracts, and funding
  points.

## Usage

The main test suite imports the shared fixtures from `tests/conftest.py`.
Individual tests then work against real database sessions and use helper
functions only where they make the scenario clearer.

Optional fixture overrides exist for database image, engine/session kwargs, and
tables excluded from truncation. They are test infrastructure knobs, not part of
the runtime application surface.

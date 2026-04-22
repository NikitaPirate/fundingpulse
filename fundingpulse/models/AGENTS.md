# Domain Models

Shared SQLModel models used by both tracker and API services.

## Entity graph

```
Asset (PK: name)  ──┐
Quote (PK: name)  ──┼──> Contract (PK: uuid, UNIQUE: asset_name+section_name+quote_name)
Section (PK: name) ─┘       │
                            ├──> ContractHistoryState (PK/FK: contract_id)
                            ├──> HistoricalFundingPoint (PK: contract_id+timestamp, hypertable)
                            └──> LiveFundingPoint       (PK: contract_id+timestamp, hypertable)
```

## Base classes

- `UUIDModel` — UUID primary key with `gen_random_uuid()` server default.
- `NameModel` — string `name` as primary key. Used by Asset, Section, Quote. Implements `__hash__`/`__eq__` on `name`.
- `BaseFundingPoint` — shared fields for funding points: `timestamp`, `contract_id` (FK to contract), `funding_rate` (float, decimal format). Hash/eq on (contract_id, timestamp).

## Models

**Asset** — crypto asset. `name` (PK), optional `market_cap_rank` (indexed). Has contracts relationship.

**Section** — exchange identity. `name` (PK), `special_fields` (JSON). Has contracts relationship.

**Quote** — quote currency. `name` (PK) only.

**Contract** — the central linking entity. Fields: `asset_name`, `section_name`, `quote_name`, `funding_interval` (hours), `special_fields` (JSON), `deprecated` (bool — no longer listed by exchange). Eagerly loads asset and section via `selectin`; tracker queries explicitly load history state when needed.

**ContractHistoryState** — tracker-owned historical ingestion checkpoint. One row per contract. Fields: `contract_id`, `history_synced` (bool — historical backfill completed), `oldest_timestamp`, `newest_timestamp`, `updated_at`. Invariant: `history_synced=True` requires both timestamp bounds to be present.

**HistoricalFundingPoint** / **LiveFundingPoint** — identical structure, separate tables. Both are TimescaleDB hypertables partitioned by `timestamp`. Composite PK: (contract_id, timestamp).

## TimescaleDB specifics

Hypertable declaration is in model `__table_args__` via `timescaledb_hypertable` dict. The `sqlalchemy-timescaledb` dialect (forked, see `pyproject.toml` uv sources) handles DDL generation. Continuous aggregates and materialized views are created in migrations, not in models.

## Migrations

Alembic in `fundingpulse/migrations/`. Numbered `001_` through `007_`. Key migrations:
- `001` — initial tables and hypertables
- `004` — continuous aggregates (lfp_smart)
- `005` — smart view for live data
- `006` — contract search materialized view
- `007` — contract history state checkpoint table

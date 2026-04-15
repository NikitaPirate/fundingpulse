# FundingPulse

Crypto perpetual futures funding rate tracker. Collects historical and live funding rates from 15 exchanges, stores in TimescaleDB, serves via REST API.

## Architecture

Two Python services sharing a domain model, plus a Next.js frontend. Each has its own AGENTS.md with detailed context:

- **tracker** (`fundingpulse/tracker/AGENTS.md`) — long-running scheduler. Collects funding data from exchanges into the database. Entry: `funding-tracker` CLI.
- **api** (`fundingpulse/api/AGENTS.md`) — FastAPI read-only HTTP API. Serves funding data to consumers. Entry: `uvicorn fundingpulse.api.main:app`.
- **models** (`fundingpulse/models/AGENTS.md`) — shared SQLModel domain models used by both services.
- **migrations** (`fundingpulse/migrations/`) — Alembic migrations (TimescaleDB-aware). Numbered sequentially: `001_`, `002_`, etc.
- **frontend** (`frontend/AGENTS.md`) — Next.js App Router web UI that consumes the API. Separate toolchain (npm, not uv).

## Stack

- Python 3.14, uv (always `uv run`, never `pip`)
- SQLModel + SQLAlchemy 2.0 async, psycopg3
- TimescaleDB (hypertables, continuous aggregates, materialized views)
- APScheduler 3.x for tracker scheduling
- FastAPI + uvicorn for API
- httpx for exchange HTTP calls
- pydantic-settings for configuration (.env)
- ruff + pyright + pre-commit for quality gates

## Key domain concepts

- **Asset** — crypto asset (BTC, ETH). PK is `name`.
- **Section** — exchange identity (binance_usd-m, bybit). PK is `name`. One exchange = one section.
- **Quote** — quote currency (USDT, USDC, USD). PK is `name`.
- **Contract** — unique (asset, section, quote) tuple. Central entity linking everything. Has `funding_interval` (hours) and `synced` flag.
- **HistoricalFundingPoint** — settled funding rate. TimescaleDB hypertable, PK is (contract_id, timestamp).
- **LiveFundingPoint** — unsettled/current rate snapshot. Same structure as historical, separate hypertable.
- **Funding rate format** — decimal: 0.0001 = 0.01%. Stored raw, normalized at query time via `funding_interval`.

## Running

```
uv run funding-tracker                    # tracker (all exchanges)
uv run funding-tracker --exchanges bybit  # tracker (specific exchange)
uv run uvicorn fundingpulse.api.main:app  # API
uv run pytest                             # tests (needs Docker for testcontainers)
```

## Testing

pytest with testcontainers — spins up a real TimescaleDB in Docker. Fixtures in `fundingpulse/testing/`. Tests in `tests/api/`.

## Code quality

Pre-commit runs ruff (lint + format) and pyright. Config in `pyproject.toml`. Migrations excluded from linting.

## Deploy

Docker Compose in `deploy/`. Three services: timescaledb, tracker, api. Migration runs as init container (`db-migrate`). Tracker supports multi-instance sharding via INSTANCE_ID/TOTAL_INSTANCES env vars.

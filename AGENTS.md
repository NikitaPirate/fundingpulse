# FundingPulse

Crypto perpetual futures funding rate tracker. Collects historical and live funding rates from 15 exchanges, stores in TimescaleDB, serves via REST API.

## Architecture

Two Python services sharing a domain model, plus a Next.js frontend. Each has its own AGENTS.md with detailed context:

- **tracker** (`fundingpulse/tracker/AGENTS.md`) — long-running scheduler. Collects funding data from exchanges into the database. Entry: `funding-tracker` CLI.
- **api** (`fundingpulse/api/AGENTS.md`) — FastAPI read-only HTTP API. Serves funding data to consumers. Entry: `uvicorn fundingpulse.api.main:app`.
- **models** (`fundingpulse/models/AGENTS.md`) — shared SQLModel domain models used by both services.
- **migrations** (`fundingpulse/migrations/`) — Alembic migrations (TimescaleDB-aware). Numbered sequentially: `001_`, `002_`, etc.
- **contracts** (`contracts/openapi.json`) — exported OpenAPI artifact shared between FastAPI and the frontend type/mock pipeline.
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
npm run contract:sync                     # export OpenAPI + regenerate frontend API types
npm run frontend:dev:mock                 # frontend with MSW-backed API mocks
npm run frontend:test                     # frontend Vitest suite
```

## Testing

pytest with testcontainers — spins up a real TimescaleDB in Docker. Fixtures in `fundingpulse/testing/`. Tests in `tests/api/`.

## Code quality

Pre-commit runs ruff (lint + format) and pyright. Config in `pyproject.toml`. Migrations excluded from linting.

## Configuration

Single `.env` at the repo root. One loader, one rule for naming.

**Loading.** Each settings module — `fundingpulse/db_settings.py`, `fundingpulse/api/settings.py`, `fundingpulse/tracker/settings.py` — calls `load_dotenv()` at the top. No `env_file=` in `SettingsConfigDict`; settings read only `os.environ`.

**Naming.** Every variable belongs to exactly one namespace:

| Prefix | Owner | Used for |
|---|---|---|
| `DB_*` | shared | DB connection (host/port/user/password/dbname). Single source of truth for both services. |
| `FDA_DB_*` | API | SQLAlchemy engine/session tuning specific to the API. |
| `FDA_CORS_*` | API | CORS middleware. |
| `FT_*` | tracker | Tracker app knobs (exchanges, debug scopes, instance sharding). |
| `FT_DB_*` | tracker | SQLAlchemy engine/session tuning specific to the tracker. |
| `FT_INSTANCE_COUNT` | deploy | Read by supervisord only — fan-out factor for tracker processes. Not a Python setting. |
| `API_PORT` | deploy | Compose host-side port mapping. Not a Python setting. |

Rule: if a value is shared across services → no service prefix. If it's owned by one service → service prefix (`FDA_` / `FT_`). Subsystems inside a service get a sub-prefix (`FDA_DB_`, `FDA_CORS_`, `FT_DB_`).

**Class layout.** Composition, never inheritance between settings classes. Each subsystem is its own `BaseSettings` with one `env_prefix`; the service-level `Settings` is a plain `BaseModel` wiring them together. No `Field(alias=...)`.

## Deploy

Docker Compose in `deploy/`. Three services: timescaledb, tracker, api. Migration runs as init container (`db-migrate`). Tracker supports multi-instance sharding via `FT_INSTANCE_ID` / `FT_TOTAL_INSTANCES`, while deploy fan-out uses `FT_INSTANCE_COUNT`.

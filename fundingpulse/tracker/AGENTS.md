# Tracker Service

Scheduler-based service that collects funding rates from crypto exchanges into TimescaleDB.

## Data flow

```
main.py → bootstrap.py → ExchangeOrchestrator (per exchange)
                              ├── update()      — hourly + on startup
                              │   ├── register_contracts()  — sync contract list from exchange API
                              │   ├── sync_contract()       — backfill full history (unsynced contracts)
                              │   └── update_contract()     — fetch new points since last known
                              └── update_live() — every minute
                                  └── collect_live()        — snapshot current unsettled rates
```

## Key components

**bootstrap.py** — wires everything: resolves exchanges, creates UoW factory, creates APScheduler, registers jobs. Each exchange gets two cron jobs: `{exchange}_update` (hourly) and `{exchange}_live` (every minute, staggered).

**ExchangeOrchestrator** — per-exchange coordinator. `update()` runs contract sync then processes all contracts concurrently (with semaphore). `update_live()` collects current rates. Both are scheduler job targets.

**coordinators/** — stateless functions that implement the actual data operations:
- `register_contracts()` — calls exchange `get_contracts()`, upserts to DB, marks missing as deprecated, signals MV refresher.
- `sync_contract()` — backward pagination: fetches history in batches until exchange returns empty. Marks contract `synced=True` when done.
- `update_contract()` — forward fetch: gets new points after the newest known timestamp. Skips if funding_interval hasn't elapsed.
- `collect_live()` — calls `fetch_live()`, writes LiveFundingPoint records.

**MaterializedViewRefresher** — debounced (10s default) refresh of `contract_enriched` materialized view. Triggered when contracts change, checked every second by scheduler.

## Exchange adapters

All in `exchanges/`. Each extends `BaseExchange` ABC and must implement:
- `EXCHANGE_ID: str` — unique identifier, used as section_name
- `_FETCH_STEP: int` — batch size in hours for history fetching. Derived from API limits and minimum funding interval. Documented per-exchange.
- `_format_symbol()` — convert Contract to exchange-specific symbol string
- `get_contracts()` → `list[ContractInfo]` — fetch available perpetuals
- `_fetch_history()` → `list[FundingPoint]` — fetch history within time window
- `fetch_live()` → `dict[Contract, FundingPoint]` — fetch current rates

Two patterns for `fetch_live`:
1. **Batch API** (most exchanges) — single request returns all rates. Override `fetch_live()` directly.
2. **Individual API** — implement `_fetch_live_single()`, call `fetch_live_parallel()` from utils.py (semaphore-controlled concurrency).

Exchange DTO: `ContractInfo` (asset_name, quote, funding_interval, section_name) and `FundingPoint` (rate, timestamp). These are adapter-internal; coordinators convert to SQLModel entities.

Registry in `exchanges/__init__.py`: `EXCHANGES` dict built at import time with validation.

## Database access

Unit of Work pattern in `db/unit_of_work.py`. Factory function creates UoW instances used as async context managers. Repositories for each model in `db/repositories/`. Sessions are short-lived — opened and closed per DB operation to avoid holding connections during API calls.

## Configuration

`settings.py` — pydantic-settings from .env. Key env vars:
- `EXCHANGES` — comma-separated exchange filter
- `INSTANCE_ID` / `TOTAL_INSTANCES` — for multi-instance sharding (round-robin distribution)
- `DEBUG_EXCHANGES` / `DEBUG_EXCHANGES_LIVE` — per-exchange log level control
- DB connection via shared `DBSettings`

`runtime.py` builds `RuntimeConfig` by merging CLI args and env vars. CLI takes precedence.

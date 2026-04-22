# Tracker Service

Scheduler-based service that collects funding rates from crypto exchanges into TimescaleDB.

## Data flow

```
main.py → DB runtime scope → bootstrap.py → ExchangeOrchestrator (per exchange)
                              ├── update()      — hourly + on startup
                              │   ├── _register_contracts() — sync contract list from exchange API
                              │   ├── _sync_contract()      — backfill full history (history_synced=false)
                              │   └── _update_contract()    — fetch new points since last known
                              └── update_live() — every minute, snapshot current unsettled rates
```

## Key components

**main.py** — owns the top-level DB runtime scope and shared HTTP client, then hands a ready `SessionFactory` to bootstrap.

**bootstrap.py** — wires everything: resolves exchanges, creates APScheduler, registers jobs around the provided `SessionFactory`. Each exchange gets two cron jobs: `{exchange}_update` (hourly) and `{exchange}_live` (every minute, staggered).

**ExchangeOrchestrator** — per-exchange coordinator. `update()` runs contract registration then processes all contracts concurrently (with semaphore). `update_live()` collects current rates. Both are scheduler job targets. All data operations are methods on the orchestrator:
- `_register_contracts()` — calls exchange `get_contracts()`, upserts to DB, marks missing as deprecated, signals MV refresher.
- `_sync_contract()` — backward pagination: fetches history in batches until exchange returns empty. Marks `ContractHistoryState.history_synced=True` when done.
- `_update_contract()` — forward fetch: gets new points after the newest known timestamp. Skips if funding_interval hasn't elapsed.

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

Exchange DTO: `ContractInfo` (asset_name, quote, funding_interval, section_name) and `FundingPoint` (rate, timestamp). These are adapter-internal; orchestrator converts to SQLModel entities.

Registry in `exchanges/__init__.py`: `EXCHANGES` dict built at import time with validation.

## Database access

Uses SQLAlchemy `async_sessionmaker` directly. Session factory is stored as `_db: SessionFactory` and accessed exclusively via `self._db.begin()` (never bare `self._db()`). `.begin()` provides auto-commit on success, auto-rollback on exception. For read-only operations this has zero cost — COMMIT on a clean session is a no-op at the DBAPI level.

Rule: any `select`/`insert`/`text()` goes into query functions in `db/`. Direct session methods (`merge`, `add`) stay inline in business code.

Sessions are short-lived — opened and closed per DB operation to avoid holding connections during API calls.

Historical sync progress is stored in `ContractHistoryState`, not derived from
`historical_funding_point` in the hot path. Each contract has exactly one state
row. The tracker updates funding points and the state bounds in the same
transaction, so crash recovery repeats the last window safely via conflict-ignored inserts.

## Configuration

`settings.py` defines the tracker config surface. The source of truth for variable names is `fundingpulse/tracker/settings.py` plus `.env.example`; shared DB credentials stay in `DB_*`, tracker knobs in `FT_*`, and docker fan-out in `FT_INSTANCE_COUNT`.

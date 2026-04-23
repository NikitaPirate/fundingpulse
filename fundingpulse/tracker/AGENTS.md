# Tracker Service

Scheduler-based service that collects funding rates from crypto exchanges into TimescaleDB.

## Data flow

```
main.py → DB runtime scope → bootstrap.py → ExchangeOrchestrator (per exchange)
                              ├── update()      — hourly + on startup
                              │   ├── contract_registry.register_contracts  — sync contract list
                              │   └── history_sync.run_history_updates      — sync/update history
                              └── update_live() — every minute, snapshot current unsettled rates
                                  └── live_collector.collect_live
```

## Key components

**main.py** — owns the top-level DB runtime scope and shared HTTP client, then hands a ready `SessionFactory` to bootstrap.

**bootstrap.py** — wires everything: resolves exchanges, seeds the `section` rows once, creates APScheduler, registers jobs around the provided `SessionFactory`. Each exchange gets two cron jobs: `{exchange}_update` (hourly) and `{exchange}_live` (every minute, staggered).

**orchestration/** — four siblings that split the per-exchange workflow:
- `exchange_orchestrator.py` — thin facade with `update()` / `update_live()` scheduler entry points. Bundles dependencies (adapter, DB, MV refresher, logger), delegates to the modules below, and logs cycle duration.
- `contract_registry.py` — `register_contracts()`: fetches exchange contracts, ensures assets/quotes, computes an explicit reconciliation plan (`added`, `deprecated`, `reactivated`, `interval_changes`) from ORM `Contract` rows, applies rare lifecycle changes through ORM mutation inside the session, creates history-state rows, and signals the MV refresher only when contracts changed.
- `history_sync.py` — `run_history_updates()` / `process_contracts()`: loads active `ContractWithHistoryState` projections (`Contract` + `ContractHistoryState`), runs a per-contract task that either backfills (`_sync`, backward pagination until empty) or incrementally extends (`_update`, forward fetch gated by `funding_interval`). Both paths persist via `persist_batch()`, which relies on `update_bounds`' SQL-level `LEAST`/`GREATEST` merge. Sync timeout is 10 min, update is 1 min.
- `live_collector.py` — `collect_live()`: fetches live rates, inserts a snapshot, logs success/failure. Errors are logged and swallowed (minute cadence must not stall).
- `section_logger.py` — `LoggerAdapter` that prepends `[section]` to every record; centralises the prefix that was duplicated across the layer.

**MaterializedViewRefresher** — debounced (10s default) refresh of `contract_enriched` materialized view. Triggered when contracts change, checked every second by scheduler.

## Exchange adapters

All in `exchanges/`. Each extends `BaseExchange` ABC and must implement:
- `EXCHANGE_ID: str` — unique identifier, used as section_name
- `_FETCH_STEP: int` — batch size in hours for history fetching. Derived from API limits and minimum funding interval. Documented per-exchange.
- `_format_symbol()` — convert a scalar ORM `Contract` row to exchange-specific symbol string
- `get_contracts()` → `list[ExchangeContractListing]` — fetch available perpetuals
- `_fetch_history()` → `list[FundingPoint]` — fetch history within time window
- `fetch_live()` → `dict[UUID, FundingPoint]` — fetch current rates keyed by contract id

Two patterns for `fetch_live`:
1. **Batch API** (most exchanges) — single request returns all rates. Override `fetch_live()` directly.
2. **Individual API** — implement `_fetch_live_single()`, call `fetch_live_parallel()` from utils.py (semaphore-controlled concurrency).

Exchange DTO: `ExchangeContractListing` (asset_name, quote_name, funding_interval, section_name) and `FundingPoint` (rate, timestamp). These are adapter-internal; orchestrator converts to SQLModel entities.

Registry in `exchanges/__init__.py`: `EXCHANGES` dict built at import time with validation.

## Database access

Uses SQLAlchemy `async_sessionmaker` directly. Open explicit transaction scopes with `.begin()` for writes, read+write units that must be atomic, and multi-step operations whose changes must commit or roll back together. Plain `session_factory()` is fine for short read-only operations.

Rule: any `select`/`insert`/`update`/`delete`/`text()` goes into query functions. Direct session methods (`merge`, `add`) and small lifecycle ORM mutations stay inline in business code when they operate on already loaded rows.

Tracker business logic uses SQLModel ORM rows as scalar data carriers for persisted rows. Shared models intentionally have no ORM relationships, so cross-row composition is represented by explicit query projections such as `ContractWithHistoryState`, never by implicit `contract.history_state` or `asset.contracts` access.

ORM rows may be used after their loading session closes only as carriers of already loaded scalar fields. Tracker sessions must use `expire_on_commit=False`; enabling expiration would make detached scalar reads unsafe.

Sessions are short-lived — opened and closed per DB operation to avoid holding connections or transactions during exchange API calls.

Historical sync progress is stored in `ContractHistoryState`, not derived from
`historical_funding_point` in the hot path. Each contract has exactly one state
row. The tracker updates funding points and the state bounds in the same
transaction, so crash recovery repeats the last window safely via conflict-ignored inserts.

## Configuration

`settings.py` defines the tracker config surface. The source of truth for variable names is `fundingpulse/tracker/settings.py` plus `.env.example`; shared DB credentials stay in `DB_*`, tracker knobs in `FT_*`, and docker fan-out in `FT_INSTANCE_COUNT`.

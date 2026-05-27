# Tracker Service

Scheduler-based service that collects funding rates from crypto exchanges into TimescaleDB.

## Data flow

```
main.py → DB runtime scope → bootstrap.py → ExchangeOrchestrator (per exchange)
                              ├── backfill_history()
                              │   — startup +5m + hourly :05:00
                              │   └── history_backfill.run_history_backfill — historical backfill
                              ├── update_history()
                              │   — immediate + hourly :00:05
                              │   └── history_update.run_history_update     — incremental history
                              └── update_live()
                                  — every minute, snapshot current unsettled rates
                                  └── live_collector.collect_live

                           → contract_registry.run_contract_registry
                              — instance 0 only, all selected exchanges,
                                immediate + minutes 4,9,...,59
```

## Key components

**main.py** — owns the top-level DB runtime scope and shared HTTP client, then hands a ready `SessionFactory` to bootstrap.

**bootstrap.py** — wires everything: resolves exchanges, seeds the `section` rows once, creates APScheduler, registers jobs around the provided `SessionFactory`. Each collection exchange gets `{exchange}_history_backfill` (startup +5m + hourly at :05:00), `{exchange}_history_update` (immediate + hourly at :00:05), and `{exchange}_live` (minute cadence, staggered by second across exchanges). Instance 0 also registers `{exchange}_contract_registry` for every selected exchange plus singleton service jobs.

**orchestration/** — siblings that split the per-exchange workflow:
- `exchange_orchestrator.py` — thin facade with `backfill_history()` / `update_history()` / `update_live()` scheduler entry points. Bundles dependencies (adapter, DB) and delegates to the modules below.
- `contract_registry.py` — `run_contract_registry()` scheduler wrapper and `register_contracts()` reconciliation core. Fetches exchange contracts, ensures assets/quotes, computes an explicit reconciliation plan (`added`, `deprecated`, `reactivated`, `interval_changes`) from ORM `Contract` rows, applies rare lifecycle changes through ORM mutation inside the session, creates history-state rows, emits structured registry events, and signals the MV refresher only when contracts changed.
- `history_backfill.py` — `run_history_backfill()`: structured, scheduler-facing historical backfill workflow. Loads only active unsynced `ContractWithHistoryState` projections, walks them backward with `fetch_history_before()`, persists each batch with state bounds in one transaction, marks `history_synced` only once older history is exhausted, and emits structured events. Whole-job timeout is 59 min.
- `history_update.py` — `run_history_update()`: structured, scheduler-facing incremental history workflow. Loads active `ContractWithHistoryState` projections, fetches after `newest_timestamp + 1s` or `start_of_hour(now) - 1s` when no history exists, persists points and state bounds in one transaction, and emits structured events. Whole-job timeout is 59 min.
- `historical_persistence.py` — shared historical point persistence helper. Inserts settled funding points idempotently and merges `ContractHistoryState` bounds in the same transaction.
- `live_collector.py` — `collect_live()`: fetches live rates, inserts a snapshot, returns `LiveCollectionResult`, and emits structured events with fetch/persist counts and durations. Errors are logged and swallowed (minute cadence must not stall).
- `section_logger.py` — `LoggerAdapter` that prepends `[section]` to every record; centralises the prefix that was duplicated across the layer.

History backfill and history update intentionally keep separate workflow code.
They look similar because the domain operations are adjacent, not because they
share a stable abstraction. Share concrete mechanics such as historical point
persistence; do not introduce a common scheduler/workflow runner unless the
domain policies actually converge.

**MaterializedViewRefresher** — debounced (10s default) refresh of `contract_enriched` materialized view. Triggered when contracts change, checked every second by the instance-0 singleton scheduler.

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

`settings.py` defines the tracker config surface. The source of truth for variable names is `fundingpulse/tracker/settings.py`, shared settings modules, and `.env.example`; shared DB credentials stay in `DB_*`, shared exchange selection is `ENABLED_EXCHANGES`, tracker knobs stay in `FT_*`, and docker fan-out stays in `FT_INSTANCE_COUNT`.

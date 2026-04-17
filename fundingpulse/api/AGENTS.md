# API Service

Read-only FastAPI service serving funding rate data from TimescaleDB.

## Structure

```
api/
├── main.py              — FastAPI app, lifespan, CORS, error handler
├── db.py                — FastAPI session dependency + app.state bridge
├── settings.py          — pydantic-settings for API config + DB runtime builder
├── api/v0/
│   ├── router.py        — v0 router aggregating sub-routers
│   ├── meta.py          — /meta/* endpoints (assets, sections, quotes, contract search)
│   └── funding_data.py  — /funding-data/* endpoints (historical, live, diffs, wall)
├── queries/
│   ├── meta.py              — meta query functions
│   ├── funding_data.py      — funding data query functions
│   ├── funding_sql_composer.py — SQL builder for diff and wall queries
│   └── contract_search.py   — contract search with scoring
└── dto/
    ├── base.py          — BaseResponse wrapper
    ├── enums.py         — NormalizeToInterval enum
    ├── funding_data.py  — response models for funding endpoints
    ├── meta.py          — response models for meta endpoints
    └── errors.py        — error response models
```

## Endpoints (all under /api/v0)

**Meta** (`/meta`):
- `GET /assets` — all asset names sorted by market_cap_rank
- `GET /sections` — all exchange names
- `GET /quotes` — all quote currencies
- `GET /contracts/search?query=` — prefix-aware search with fuzzy fallback
- `GET /contracts/{id}` — single contract metadata

**Funding data** (`/funding-data`):
- `GET /historical_points` — historical rates for one contract
- `GET /live_points` — aggregated live rates for one contract (from `lfp_smart` continuous aggregate)
- `GET /historical_sums` — cumulative historical funding per contract over arbitrary day windows (with 98% completeness threshold)
- `GET /diff/live_differences` — cross-exchange rate comparison using latest live data
- `GET /diff/historical_differences` — cross-exchange rate comparison over time range
- `GET /diff/historical_cumulative_differences` — cumulative funding diffs over time
- `GET /funding-wall` — matrix: assets x exchanges, live or historical, raw or normalized
- `GET /live_latest` — latest live rate per contract for a filter slice
- `GET /historical_latest` — latest settled rate per contract for a filter slice (30d validity window)
- `GET /historical_avg` — average historical funding per contract over arbitrary day windows

The three slice endpoints require `asset_names` or `section_names` (quote-only is rejected), default to `365d` normalization, and return the full contract set from `contract_enriched` with nullable data fields.

## Rate normalization

Funding intervals differ across exchanges (1h, 4h, 8h). `NormalizeToInterval` enum controls normalization: RAW (as-is), 1h, 8h, 1d, 365d. Multiplier = `target_hours / funding_interval`. Applied in SQL, not in Python.

## Query layer

Raw SQL via `sqlalchemy.text()`, not ORM queries. `FundingQueryComposer` builds complex CTEs for diff/wall queries — filter → pair contracts by asset → join funding data → compute differences. Uses TimescaleDB functions (`time_bucket`, `last()`).

Key SQL views:
- `contract_enriched` — materialized view joining contract with asset/section metadata. Refreshed by tracker's MaterializedViewRefresher.
- `lfp_smart` — continuous aggregate over live_funding_point (1-minute buckets with avg).

## Database access

Direct async sessions via `SessionDep` (FastAPI Depends). The app creates one process-scoped `SessionFactory` in lifespan via the shared `fundingpulse.db` runtime and exposes only the session dependency to handlers. No UoW pattern — read-only service doesn't need transaction management.

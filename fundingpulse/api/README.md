# API

The API is the read boundary for FundingPulse. It is a FastAPI service over
TimescaleDB data produced by the tracker. It does not collect exchange data and
does not own write workflows; its job is to expose funding-rate analytics in
stable response shapes for the frontend and other consumers.

Live Swagger UI: [api.quantshark.space/docs](https://api.quantshark.space/docs)

All public routes live under `/api/v0`.

## Endpoint Groups

**Metadata** (`/meta`) exposes the catalog used to build query slices:

- assets ordered by market-cap rank;
- exchanges, represented as sections;
- quote currencies;
- contract search with prefix-aware scoring and fuzzy fallback;
- single-contract metadata lookup.

**Funding data** (`/funding-data`) exposes time-series and comparison views:

- historical points for one contract;
- aggregated live points for one contract;
- latest live or settled rate for a filter slice;
- historical averages and cumulative sums over day windows;
- cross-exchange live and historical differences;
- funding-wall matrices across assets and exchanges.

The API intentionally returns funding data from database views and composed SQL
queries rather than recreating time-series logic in Python.

## Rate Normalization

Exchanges settle funding at different intervals. FundingPulse stores raw rates
and applies normalization at query time using the contract `funding_interval`.

Supported views include raw, 1h, 8h, daily, and annualized normalization.
The multiplier is computed in SQL as:

```text
target_hours / funding_interval
```

This keeps stored data faithful to the exchange while allowing the frontend to
compare contracts on a common interval.

## Query Model

The API uses raw SQL through SQLAlchemy for the query-heavy surface. Complex
responses are built from CTEs, TimescaleDB functions, materialized views, and
continuous aggregate-backed views:

- an enriched contract projection joins contract, asset, exchange, quote, and
  precomputed funding multipliers;
- an aggregate live-funding view provides efficient access to live snapshots.

Handlers stay thin: validation happens at the endpoint boundary, then query
functions own SQL composition and response DTO construction.

## Frontend Contract

The API is the source of truth for the frontend contract:

```bash
npm run contract:sync
```

That command exports `contracts/openapi.json` from the FastAPI app and
regenerates frontend TypeScript types. The frontend consumes generated types
instead of maintaining hand-written API shapes.

## Configuration

Environment variables are namespaced by owner:

| Prefix | Owner | Purpose |
| --- | --- | --- |
| `DB_*` | shared | database connection used by API and tracker |
| `FDA_DB_*` | API | SQLAlchemy engine/session tuning |
| `FDA_CORS_*` | API | CORS middleware |

Settings modules load `.env` into process environment and then read their own
namespaced settings. Shared database credentials remain unprefixed because both
backend services use the same database.

# Frontend

The frontend is a Next.js App Router application for exploring funding-rate
data. It has no database access of its own; it is a typed consumer of the
FastAPI contract exported by the backend.

Live product: [quantshark.space](https://quantshark.space/)

The UI is product-facing rather than decorative: dense tables, time-series
charts, URL-backed filters, and mockable API boundaries for frontend work
without a live backend.

## Product Views

- **Asset Funding** - compares funding behavior for selected assets across
  exchanges and quote currencies.
- **Funding Arbitrage** - ranks cross-exchange funding differences for the same
  asset.
- **Contract Analysis** - focuses on one contract with historical, live, and
  live-vs-historical chart views.

These pages share layout primitives and API runtime helpers, while route-specific
components stay colocated with their route.

## API Contract

The backend exports OpenAPI and the frontend generates TypeScript types from it:

```bash
npm run contract:sync
```

Generated types live under `app/_generated/` and should not be hand-edited.
Route data loaders and client components use those types through the frontend
API helpers.

## Mock Mode

Mock mode uses MSW so the frontend can run without a live backend:

```bash
npm run frontend:dev:mock
```

Mocks live under `frontend/mocks/` and mirror the API surface used by the UI.
This keeps product iteration independent while preserving the backend contract
as the source of truth.

## Commands

From the repository root:

```bash
npm run frontend:dev
npm run frontend:dev:mock
npm run frontend:test
npm run frontend:build
```

From `frontend/`:

```bash
npm run dev
npm run dev:mock
npm run test
npm run build
npm run lint
```

## Design Boundary

The frontend is optimized for scanning and comparison. It avoids marketing-page
composition and keeps data pages open, dense, and aligned. Charts use `uPlot`
because funding series need a real time axis, step-style funding movement, and
desktop pan/zoom behavior.

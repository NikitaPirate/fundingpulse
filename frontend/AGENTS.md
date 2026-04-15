# Frontend

Next.js web UI for FundingPulse. Consumes the FastAPI funding API; no database access of its own.

Separate toolchain: npm, not uv. Local frontend commands live here (`npm run dev` / `dev:mock` / `build` / `start` / `lint` / `test`), but the shared API contract is managed from the repo root via `npm run contract:sync`.

## Stack (load-bearing choices)

- **Next.js App Router** + React + TypeScript. SSR is used for pages with heavy time series.
- **CSS Modules over a CSS-variable token layer.** No Tailwind, no component library as a styling base. Headless primitives (Radix-style) are allowed pointwise if needed. Tokens live in `:root` with a theme slice for dark/light.
- **uPlot for charts.** Required, not a preference — funding series need a real time axis, step-before interpolation, and desktop pan/zoom. High-level React chart libs don't cover this.

These three are deliberate and should not be swapped without discussion.

## Architecture

Route-colocated, not FSD. Code used on one route lives next to it under App Router's private `_` prefix (e.g. `app/<route>/_components/`). Shared code moves up to `app/_components/` or a future `shared/` only when a second real consumer appears — not speculatively.

State lives in the URL. No auth, no persistence, no cross-session state in the current scope.

## Data

Funding data comes from the FastAPI service in `fundingpulse/api/`. The Next backend has no logic of its own beyond SSR and proxying; a real server-side layer is reserved for a future user slice (notifications, saved filter templates) that doesn't belong in the public read-only API. The API is extended to fit the frontend as needed — no backwards-compatibility constraint.

The shared contract artifact lives in `contracts/openapi.json` at the repo root. Frontend API types are generated from it into `app/_generated/api-types.ts`. For frontend-only work without a live backend, use `npm run dev:mock` here or `npm run frontend:dev:mock` from the repo root.

## Conventions

- Keep new code route-colocated by default. Promote to shared on the second real use.
- Style via CSS Modules + tokens. Do not introduce Tailwind or a component library as a styling base.
- Check current Next.js / React docs via the `find-docs` skill before using APIs you're not sure about — model memory drifts fast on Next.js versions.
- Treat `app/_generated/` as generated contract output. Do not hand-edit it.
- Treat `public/mockServiceWorker.js` as a vendor/generated asset for MSW. Do not hand-edit it.
- Contract regeneration depends on the Python/uv backend environment because OpenAPI is exported from FastAPI code, even though the generated TypeScript and tests live under `frontend/`.

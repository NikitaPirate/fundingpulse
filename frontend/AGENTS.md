# Frontend

Next.js web UI for FundingPulse. Consumes the FastAPI funding API; no database access of its own.

Separate toolchain: npm, not uv. `npm run dev` / `build` / `start` / `lint`.

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

## Conventions

- Keep new code route-colocated by default. Promote to shared on the second real use.
- Style via CSS Modules + tokens. Do not introduce Tailwind or a component library as a styling base.
- Check current Next.js / React docs via the `find-docs` skill before using APIs you're not sure about — model memory drifts fast on Next.js versions.

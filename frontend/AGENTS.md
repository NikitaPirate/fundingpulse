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

## Visual Contract

`Funding Arbitrage` is the canonical implemented reference for FundingPulse data pages. New data-heavy pages should first feel visually native to it before they diverge for page-specific needs.

This is not a loose inspiration. If a design decision conflicts with the current `Funding Arbitrage` grammar, the default assumption is that the new decision is wrong unless there is a concrete product reason to break it.

## Style Invariants

- Data pages must read as light structure on open canvas, not as a stack of boxed components.
- Tables must hang in the page flow with lines and spacing, not inside outer cards, panels, or framed shells.
- Headers, filter rows, table meta, and pagination must align to a coherent horizontal rail. Avoid jagged left edges and accidental indentation shifts between sections.
- Filter triggers are light slots. They do not become heavy controls through filled backgrounds, shadows, accent borders, or decorative chrome.
- Overlay surfaces that open above the page, such as dropdown panels and popovers, must be visually opaque enough to block underlying text. Trigger controls themselves should stay visually light unless there is a strong reason otherwise.
- Secondary meta above tables stays as plain text. Do not convert it into chips, pills, badges, or status blocks.
- Empty and error states stay quiet and textual. Do not introduce tinted banners or alert-card styling for routine states.
- The page should preserve desktop-first density. Use horizontal space deliberately before increasing vertical stack height.
- Repeated row content must read as grouped factual data. Do not let inner cell layout visually separate values that belong together, such as `exchange / quote / rate`.
- Active emphasis must reflect real state changes only. Default controls should not look highlighted just because they exist.

## Anti-Patterns

- Do not add outer cards, boxed sections, panel shells, or table wrappers with their own visual surface.
- Do not make filter rows visually heavy with fill, shadow, or ornamental borders.
- Do not add decorative status strips, meta blocks, or top-right fillers with no functional meaning.
- Do not use non-working UI as a placeholder. If a feature does not exist, it should not appear in the interface.
- Do not solve density problems by stacking related inline facts vertically when the desktop layout has horizontal room.
- Do not introduce multiple competing alignment rails across one page.

## Funding Arbitrage Specifics

- `Funding Arbitrage` is a ranked opportunity list, not a generic exploratory data grid.
- User-driven sorting is out of scope unless explicitly added as a real feature. Default order comes from the API.
- `Period = Live` must keep the green live indicator in the control itself.
- Default `Normalization` should remain visually neutral. Accent appears only after the user leaves the default state.

# Silico Agent App

Standalone React + Vite interface for the retrieval-and-scoring HPLC recommendation workflow.

## Dev

Start the method-development backend first:

```bash
cd services/method-development
uv sync --group dev
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

Optional SMILES-name resolution support:

```bash
cd apps/api
uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000
```

Then run the app:

```bash
cd apps/agent
npm install
npm run dev
```

Surrogate frontend playground preview:

```bash
cd apps/agent
npm run dev
```

Then open `http://localhost:4175/agent/surrogate` after signing in to the local preview gate.

Legacy studio surfaces are dev-only:

```bash
cd apps/agent
npm run dev:legacy-studio
```

The dev server runs on `http://localhost:4175`. Vite proxies `/method-dev/*` to `http://localhost:8001` and `/api/*` to `http://localhost:8000`.

From the repo root you can also use:

```bash
npm run dev:agent
npm run build:agent
```

## Current Scope

- staged system -> target -> source -> discovery -> report workflow
- local preview sign-in gate before opening the dashboard, review queue, or studio routes
- app-facing recommendation flow for `local_corpus` and `open_access`
- shared light/dark appearance mode across the workflow
- backend-scaled method output and recommendation ranking display
- `/surrogate` frontend-only playground for the simulated surrogate UI
- transcript-triggered surrogate launch when operators type phrases like `can we simulate this` against an active recommendation
- report-grounded follow-up questions that append after the active run instead of overwriting the original request
- optional SMILES-name resolution via `apps/api`
- deterministic website-demo fallback when the live `method-development` service is unavailable
- local recommendation snapshot recovery with explicit `Live`, `Cached`, and `Demo-safe` result labeling for the current request
- recent-run browsing for locally cached recommendation snapshots inside the report workspace
- analysis-package export from the integrated studio reports view

Legacy routes:

- `/studio` and `/studio/classic` are disabled in the normal build
- set `VITE_AGENT_ENABLE_LEGACY_STUDIO=true` or use `npm run dev:legacy-studio` / `npm run build:legacy-studio` to expose them intentionally in developer workflows

The current sign-in gate is intentionally local-only for preview workflows. It controls browser access to the
agent UI on the current device but does not yet enforce hosted backend authentication.

## Not Yet Surfaced Here

- backend `local_files` recommendation mode
- review-record approval and promotion workflows
- export-package behavior beyond the current placeholder button
- upload artifact caching and interrupted extraction recovery beyond recommendation-report snapshots

## Validation

```bash
npm run build
```

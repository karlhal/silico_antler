# Agent App Guide

## Scope
Applies to `apps/agent` only. Use with the root `../../AGENTS.md`.

## Primary Commands
- Install deps: `npm install`
- Run dev server: `npm run dev`
- Build/type-check: `npm run build`
- Preview build: `npm run preview`

## Must-Read Context
- Agent docs index: [`../../docs/agents/index.md`](../../docs/agents/index.md)
- Architecture boundaries: [`../../docs/agents/architecture-boundaries.md`](../../docs/agents/architecture-boundaries.md)
- Quality gates: [`../../docs/agents/quality-gates.md`](../../docs/agents/quality-gates.md)
- Release/testing: [`../../docs/agents/release-and-testing.md`](../../docs/agents/release-and-testing.md)
- App README: [`./README.md`](./README.md)
- Workflow state: [`./src/hooks/useAgentWorkflow.ts`](./src/hooks/useAgentWorkflow.ts)
- Dashboard UI: [`./src/pages/Dashboard.tsx`](./src/pages/Dashboard.tsx)
- API client: [`./src/lib/api.ts`](./src/lib/api.ts)
- Shared types: [`./src/types/index.ts`](./src/types/index.ts)

## Local Rules
- Keep `local_corpus` and `open_access` as the canonical app-facing source modes; do not reintroduce legacy `local` ambiguity in the UI.
- Treat `apps/api` and `services/method-development` as HTTP dependencies through `/api` and `/method-dev`, not direct source-import targets.
- Render backend recommendation, trust, and scaling payloads directly; avoid rebuilding scoring or scaling logic in the frontend.
- Surface degraded states, truncation, and empty-result causes explicitly in UI state or diagnostics; do not make retrieval or ranking failures look like valid low-result runs.

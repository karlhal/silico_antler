---
status: active
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
applies_to: apps/agent
source_of_truth: docs/agents/execution-plans.md
---

# Liquid Smart Agent Gap Closure

## Goal And Success Criteria
- Compare `apps/agent` against `https://github.com/Niclindm/liquid-smart-agent.git` and separate:
  - features already imported into this repo
  - features present in code but not surfaced from the primary workflow
  - features still absent from this repo
- Ship an initial implementation pass that closes at least the highest-priority UI gap.
- Deliver dark mode for the primary `/` workflow in `apps/agent`.
- Surface the imported studio shell from the main app so the replicated shell is reachable without relying on a hidden route.

## Scope
- `apps/agent` only.
- Theme support for the main recommendation workflow.
- Navigation between the current recommendation workflow and the integrated studio preview.
- Comparison notes for reference-shell capabilities versus the current repo.

## Explicit Non-Goals
- Port every missing shadcn primitive from the reference repo.
- Reintroduce Supabase-only authentication, rate limiting, or edge-function dependencies into the shipped agent workflow.
- Replace the existing recommendation workflow with the studio shell.
- Change API or method-development contracts.

## Decision-Complete Implementation Approach
- Treat the current repo as having two agent surfaces:
  - the production recommendation workflow at `/`
  - the imported studio shell at `/studio`
- Surface the original imported project shell as a separate classic mode at `/studio/classic` instead of leaving those components disconnected from the app.
- Reuse the existing studio theme hook so both surfaces share one persisted theme preference.
- Add dark-mode token overrides for the root dashboard CSS and update any light-only status/banner styles that would break in dark mode.
- Add a clear dashboard action to open the integrated studio preview.
- Add matching studio-header actions to move between the primary workflow, integrated studio, and classic shell.
- Reuse the existing analysis export pipeline inside the integrated studio reports workspace instead of creating a second export implementation.
- Keep routing lightweight and compatible with the existing manual pathname handling in `src/App.tsx`.

## Validation Matrix
- `cd apps/agent && npm run build`
- Manual code inspection for:
  - dashboard theme toggle presence
  - persisted `dark` class application via shared theme hook
  - workflow-to-studio and studio-to-workflow navigation wiring

## Risks And Rollback Strategy
- Risk: dark theme token overrides make status states unreadable.
  - Mitigation: update the light-only notice/detail styles that currently rely on fixed `amber` and `emerald` palette classes.
- Risk: route navigation breaks when the app is mounted under `/agent`.
  - Mitigation: use shared app-aware navigation helpers instead of hardcoded path pushes.
- Rollback:
  - revert the new dashboard theme/navigation wiring
  - keep the existing hidden `/studio` route intact if surfacing it causes regressions

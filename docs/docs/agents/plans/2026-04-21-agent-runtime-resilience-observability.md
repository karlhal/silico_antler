---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development runtime resilience observability
source_of_truth: docs/agents/execution-plans.md
---

# Agent Runtime Resilience And Observability

## Goal and Success Criteria

Make the recommendation runtime more robust, diagnosable, and predictable across live search, extraction, scoring, and fallback paths.

Success means:

- failures are easier to classify and trace
- degraded-mode behavior is explicit to callers
- request budgets, timeouts, and retries are surfaced in a more usable way
- operators can diagnose OpenAlex, fetch, extraction, or retrieval-store failures without reproducing blindly

## Scope

- `services/method-development`
- small companion changes in `apps/agent` only where the UI needs improved status/error semantics

## Explicit Non-Goals

- no migration to a fully asynchronous job queue in the first slice
- no distributed tracing platform requirement
- no ranking-model overhaul
- no hidden silent retries that weaken determinism

## Current State

The service already has useful foundations:

- deterministic recommendation path
- open-access skipped-paper diagnostics
- explicit review and orchestration endpoints
- server-side caps for LLM orchestration budgets
- basic rate limiting on `/recommendation/recommend`

But the runtime still has several hardening opportunities:

- recommendation calls remain mostly single-request synchronous work
- failure semantics are still relatively coarse at the app boundary
- service diagnosis depends heavily on logs and test knowledge
- local Milvus usage still needs workarounds during common dev flows

## Why This Should Happen

The product now lives or dies on whether users trust the runtime path. A brittle but clever pipeline will be discounted. The next backend advantage is not just better extraction. It is better operational behavior.

## Decision-Complete Implementation Approach

### Status semantics stance

Introduce a clearer runtime-status model across recommendation responses and failures:

- completed
- completed_with_degraded_source
- completed_with_demo_fallback
- no_trustworthy_candidates
- upstream_unavailable
- request_invalid

The UI should not need to infer runtime posture from loose strings alone.

### Request identity stance

Add request correlation metadata:

- request id
- runtime mode
- key branch decisions
- bounded step budget summary where relevant

This should appear in logs and optionally in debug-facing response metadata.

### Failure classification stance

Distinguish at least:

- search failure
- fetch failure
- extraction failure
- retrieval-store unavailable
- LLM observer unavailable
- timeout

The point is better triage, not more exposed stack traces.

### Degraded-mode stance

When partial degradation happens:

- make it explicit
- keep deterministic fallbacks when available
- avoid silently replacing live logic with demo logic unless the caller receives a precise notice

### Observability stance

Improve operator insight with:

- structured logs around recommendation stages
- stable counters or metrics for major failure classes
- clearer health and readiness expectations for retrieval store and optional LLM observer
- optional debug mode for local development

### Rate-limit and runtime-budget stance

Revisit current service guardrails:

- confirm whether `5/hour` on `/recommendation/recommend` matches intended demo and operator usage
- keep bounded execution, but report those constraints more clearly
- prevent accidental widening of costly branches without backend approval

## Primary Files And Boundaries

Likely implementation homes:

- `services/method-development/app/recommendations_router.py`
- `services/method-development/app/recommendation_engine.py`
- runtime settings and logging helpers under `services/method-development/app/`
- `apps/agent` only where new status metadata is rendered

Boundary rule:

- method-development owns runtime semantics and diagnostics
- agent consumes those semantics, but does not invent them

## Validation Matrix

When implemented:

- `cd services/method-development && uv run pytest -q`
- targeted recommendation and error-path API tests
- `cd apps/agent && npm run build` if surfaced in UI
- local smoke tests for healthy, degraded, and fallback runs

## Risks and Rollback Strategy

- Risk: too much metadata pollutes the clean recommendation contract.
- Risk: more explicit degraded-mode reporting lowers confidence if phrased poorly.
- Risk: observability additions become local-only and never help production diagnosis.

Rollback:

- keep new metadata additive and optional
- isolate failure-taxonomy changes from scoring changes

## Decision Notes

- 2026-04-20: The runtime already has bounded-orchestration thinking; this plan extends that discipline to recommendation and retrieval paths more broadly.
- 2026-04-20: Better operational clarity is now as valuable as another increment of extraction cleverness.

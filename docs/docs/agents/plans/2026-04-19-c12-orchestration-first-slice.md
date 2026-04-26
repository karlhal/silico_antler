---
status: active
owner: opencode
source_of_truth: docs/agents/execution-plans.md
last_verified: 2026-04-19
applies_to: services/method-development
---

# C12 Orchestration First Slice

## Goal And Success Criteria

- Start Chunk C12 with a lightweight orchestration layer around the existing deterministic method-development steps.
- Expose one backend entrypoint that can coordinate source registration, extraction, review-record creation or reuse, and optional approval.
- Keep retries idempotent enough for repeated calls on the same `source_document_id` without creating duplicate review records by default.
- Leave extraction, validation, and approval internals deterministic and reusable.

## Scope And Non-Goals

Scope:

- Add one orchestration module plus one API route for preparing a review record from an input source document payload.
- Reuse existing registry, extraction, review-record, and retrieval-store logic.
- Add focused tests for success, reuse, blocked approval, and successful approval/materialization.

Non-goals:

- No LLM-driven planning or judgment.
- No background jobs, queues, or async workflow engine.
- No surrogate-model logic or chromatogram simulation.
- No broad rewrite of existing routers or extraction heuristics.

## Decision-Complete Implementation Approach

- Add orchestration schemas for request, step-state reporting, and response payloads.
- Add a small orchestration service that:
  - registers or reuses a source document
  - creates or reuses a review record for the same source document
  - optionally applies entity resolutions and approval
  - ensures approved records are materialized into the retrieval store
- Use `retry_existing=true` by default so repeated calls on the same source document reuse the latest review record.
- Keep orchestration synchronous for the first slice.
- Return step-level statuses instead of failing the whole orchestration when approval is blocked by validation state.
- Add explicit execution-budget guardrails so the orchestrator cannot loop indefinitely:
  - `max_step_attempts` defaults to `1`
  - `max_total_steps` defaults to `5`
  - the response reports `budget`, per-step `attempts_used`, and `cutoff` state when a later step is intentionally skipped
 - When model-backed orchestration is enabled, use Gemini only as a bounded observer layer first; keep extraction and approval decisions deterministic until the demo path is proven stable.

## Validation Matrix

- `cd services/method-development && uv run pytest -q`
- `npm run agent:harness:check`
- Focused new tests:
  - create review record through orchestration
  - reuse source document and review record on retry
  - block approval when the review record is not retrieval-ready
  - approve and materialize when entity resolutions make the record retrieval-ready
  - stop before approval when the explicit orchestration budget is exhausted

## Risks And Rollback Strategy

Risks:

- Reusing an existing review record may return an older extraction snapshot if extraction heuristics change later.
- Approval orchestration could drift from the existing review-status route if the logic is duplicated carelessly.
- The first orchestration route may encourage callers to depend on step-state strings early.

Rollback:

- The new route will be isolated in its own router and module, so it can be removed without disturbing the existing deterministic endpoints.
- Existing source-document, extraction, review-record, and retrieval endpoints remain the primary fallback path.

## Decision Notes

- First slice favors idempotent orchestration reuse over re-running extraction for already-reviewed records.
- If later C12 work needs fresher extraction snapshots, add an explicit refresh mode instead of changing retry semantics silently.
- The anti-loop cutoff is deliberate: this orchestration path should stop and report state rather than spend unbounded time or retries investigating ambiguous records.

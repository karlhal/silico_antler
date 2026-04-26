---
owner: codex
last_verified: 2026-04-21
applies_to: apps/agent-services/method-development
source_of_truth: docs/agents/execution-plans.md
---

# Agent App Relevance And Performance Deep-Dive

- Status: completed
- Owner: codex
- Date: 2026-04-21

## Goal And Success Criteria

Goal:
Deep-dive the `apps/agent` recommendation workflow and its FastAPI backends to identify why the app feels slow, why open-access ranking admits irrelevant papers, and where concrete bugs are already present.

Success criteria:
- Trace the end-to-end path across `apps/agent`, `services/method-development`, and supporting contracts.
- Validate suspected issues with runnable checks instead of chat-only inference.
- Fix low-risk regressions discovered during the audit.
- Leave an in-repo markdown record of findings and next-step improvements.

## Scope And Explicit Non-Goals

In scope:
- Agent workflow latency in `apps/agent`.
- Open-access query generation, screening, extraction, and ranking in `services/method-development`.
- Report payload behavior that affects explainability in the agent UI.
- Reproducible bugs that can be fixed without widening contracts.

Non-goals:
- Re-architecting the extraction stack.
- Changing public HTTP contracts.
- Adding new third-party infrastructure.
- Reworking operator or review-record flows beyond directly relevant bugs.

## Decision-Complete Implementation Approach

1. Read repo-wide and local agent guidance plus the app/service READMEs.
2. Inspect the agent workflow hook, API client, recommendation engine, retrieval store, and open-access client.
3. Run focused validation:
   - `cd apps/agent && npm run build`
   - `cd services/method-development && uv run pytest -q tests/test_recommendation_engine.py tests/test_retrieval_store.py`
4. Patch only the regressions that were clearly low-risk and already covered by tests:
   - Restore higher-precision open-access query generation behavior.
   - Correct degraded-runtime reporting for fetch, extraction, and HTML-to-PDF fallback paths.
   - Remove intentional per-paper backend sleeps.
   - Reduce frontend minimum wait padding after a completed job.
   - Preserve discovery-summary diagnostics in the agent UI metadata layer.
5. Record the broader scoring and retrieval roadmap in a dedicated markdown report.

## Validation Matrix

- `apps/agent`
  - `npm run build`
- `services/method-development`
  - `uv run pytest -q tests/test_recommendation_engine.py tests/test_retrieval_store.py`
- `docs/agents`
  - `npm run agent:harness:check`

## Risks And Rollback Strategy

Risks:
- Query-builder tuning can reshuffle open-access search behavior.
- Lower artificial latency can change the perceived cadence of the stepper UI.
- Marking more runs as degraded can expose warning states more often in the UI.

Rollback:
- Revert the targeted edits in:
  - `services/method-development/app/recommendation_engine.py`
  - `apps/agent/src/hooks/useAgentWorkflow.ts`
- The markdown files can remain even if code changes are reverted because they document the investigation.

## Decision Notes

- The immediate regressions were worth fixing now because the test suite already encoded the intended behavior and was failing.
- Larger relevance/scoring improvements are documented separately to avoid mixing exploratory product decisions with a small patch set.

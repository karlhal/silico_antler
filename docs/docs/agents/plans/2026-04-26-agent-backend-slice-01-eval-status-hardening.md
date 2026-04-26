---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development recommendation eval runtime status
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-23-agent-recommendation-bug-backlog.md
  - ./2026-04-21-open-access-demo-failure-analysis.md
---

# Slice 01: Eval And Runtime Status Hardening

## Goal And Success Criteria

Fix the current backend eval failure and make the recommendation status contract distinguish:

- successful recommendation with degraded sources
- no complete/trustworthy candidate despite trying papers
- upstream search/fetch failure
- extraction failure on individual papers

Success means:

- `run_agent_eval_suite.py --suite core` passes
- degraded source runs with at least one viable candidate report `completed_with_degraded_source`
- runs with fetched papers but no viable candidate report `no_trustworthy_candidates` with useful skip reasons
- no status is silently downgraded or upgraded without branch-decision evidence

## Current Context

On 2026-04-23:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite core --json-output /tmp/silico-agent-eval-core.json
```

Result:

- `11/12` passed
- failed case: `recommendation.open_access_fetch_degraded`
- expected: `runtime.status == completed_with_degraded_source`
- actual: `runtime.status == no_trustworthy_candidates`

Relevant files:

- `services/method-development/run_agent_eval_suite.py`
- `services/method-development/tests/fixtures/agent_eval_dataset.json`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_runtime.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/recommendations_router.py`
- `services/method-development/tests/test_recommendation_engine.py`
- `services/method-development/tests/test_recommendation_api.py`

Key existing behavior:

- `RecommendationRuntimeTracker` is created in `recommend_methods()`.
- `recommend_methods()` accumulates `discovered_papers`, `skipped_papers`, and `recommendation_candidates`.
- open-access candidate fetch/extraction happens in `_build_open_access_recommendation_candidate()`.
- skip diagnostics are represented by `RecommendationSkippedPaper`.
- status is finalized near the end of `recommend_methods()` via `runtime_tracker.success_runtime(...)`.

## Scope

Backend only:

- status classification logic
- eval harness expectations if the current expected outcome is wrong
- tests that pin degraded/no-candidate semantics
- branch-decision and skip-diagnostic preservation

## Explicit Non-Goals

- Do not tune ranking weights.
- Do not change open-access query planning.
- Do not add concurrency.
- Do not alter the app UI in this slice.

## Decision-Complete Implementation Approach

### 1. Reproduce The Failing Case

Run:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite core --json-output /tmp/silico-agent-eval-core.json
jq '.results[] | select(.status=="failed")' /tmp/silico-agent-eval-core.json
```

Inspect the fake client in `run_agent_eval_suite.py`:

- case id: `recommendation.open_access_fetch_degraded`
- returns one successful paper and one failed paper
- failed paper raises in `fetch_source_artifact()`

Determine whether the successful paper actually yields a viable candidate. If yes, status should be `completed_with_degraded_source`. If no, expected status should be `no_trustworthy_candidates`, and the case name/expectation should change to represent no viable candidate after degradation.

### 2. Pin Status Rules In Code

Use these rules:

- `completed`: at least one viable candidate, no degraded source events
- `completed_with_degraded_source`: at least one viable candidate and at least one degraded source event
- `no_trustworthy_candidates`: no viable candidate after screening/fetch/extraction attempts
- `upstream_unavailable`: search/fetch infrastructure fails before meaningful candidate processing can continue
- `request_invalid`: request validation failure

If the tracker currently loses degradation state when no candidates survive, preserve both:

- runtime status should reflect final outcome
- `runtime.degraded` should still be `true`
- branch decisions and skipped papers should explain source degradation

### 3. Strengthen Tests

Add or update tests in `tests/test_recommendation_engine.py` for:

- viable candidate plus one fetch failure -> `completed_with_degraded_source`
- no viable candidate plus fetch/extraction failures -> `no_trustworthy_candidates` and `runtime.degraded is true`
- skipped paper diagnostics include `stage="fetch"` or `stage="extraction"` as applicable

Keep fixture-backed `run_agent_eval_suite.py` aligned with the intended semantics.

### 4. Preserve Agent Contract

Check `recommendations_router.py` compact response behavior:

- `response_detail="agent"` may strip full arrays
- it must preserve `discovery_summary.skipped_papers_preview`
- it must preserve `runtime.status` and `runtime.degraded`

## Validation Matrix

```bash
cd services/method-development
uv run pytest -q tests/test_recommendation_engine.py tests/test_recommendation_api.py
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
```

Optional full backend gate:

```bash
uv run pytest -q
```

## Risks And Rollback Strategy

Risk: changing status semantics can break UI assumptions.

Mitigation:

- preserve schema fields
- only refine values according to documented semantics
- keep skip diagnostics available in `discovery_summary`

Rollback:

- revert status classifier changes while keeping any added tests marked with the current expected behavior for discussion.

## Definition Of Done

- core eval passes
- docs or test names no longer imply a different status contract than the code implements
- one fresh JSON scorecard clearly shows the fixed case

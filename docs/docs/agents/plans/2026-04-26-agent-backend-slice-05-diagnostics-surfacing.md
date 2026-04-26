---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development apps/agent diagnostics evidence trust
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-21-agent-trust-evidence-surfacing.md
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
---

# Slice 05: Diagnostics And Trust Surfacing

## Goal And Success Criteria

Expose enough backend diagnostics in the agent experience for a scientist or operator to understand why a paper was found, skipped, fetched, extracted, rejected, or selected.

Success means:

- the app can answer “why did this candidate win?” from backend data
- the app can answer “why were papers skipped?” from backend data
- `response_detail="agent"` remains compact but does not erase trust-critical summaries
- no frontend-side scoring or inference is introduced

## Current Context

Backend compacting:

- `services/method-development/app/recommendations_router.py` shapes compact `agent` responses
- full `discovered_papers` and `skipped_papers` arrays may be stripped
- `discovery_summary` is expected to preserve counts and previews

Frontend report building:

- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/lib/api.ts`
- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/types/index.ts`

Existing backend fields to surface:

- `runtime.status`
- `runtime.degraded`
- `runtime.branch_decisions`
- `runtime.budget`
- `search_query_used`
- `discovery_summary.discovered_paper_count`
- `discovery_summary.skipped_paper_count`
- `discovery_summary.skipped_papers_preview`
- candidate `decision_trace`
- candidate `query_provenance`
- candidate `score.features`
- candidate `trust`
- candidate `evidence_snippets`
- local-corpus `review_summary`
- local-corpus `match_rationale`

Known issue from prior deep dive:

- compact agent-mode responses previously dropped useful skip diagnostics
- `buildReportMeta()` was updated to read `discovery_summary`, but the UI still does not expose all useful backend context

## Scope

Backend and app contract/rendering:

- preserve compact diagnostics in response shaping
- render query provenance and skip summaries
- render rank/trust/evidence details from backend data
- add tests/build checks for payload and frontend typing

## Explicit Non-Goals

- Do not redesign the full agent UI.
- Do not add frontend score calculation.
- Do not expose full raw paper/evidence arrays by default.
- Do not add a generic chat-over-papers product.

## Decision-Complete Implementation Approach

### 1. Audit Current Response Shape

Use a local recommendation output to inspect fields:

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final LC-MS/MS method for carotenoids in human plasma" \
  --analyte-name "carotenoids" \
  --matrix "human plasma" \
  --require-ms \
  --paper-dir tests/paper_example \
  --json --debug > /tmp/silico-agent-diagnostics-sample.json
```

Inspect:

```bash
jq '{runtime, search_query_used, discovery_summary, recommended_candidate: {title: .recommended_candidate.title, score: .recommended_candidate.score, trust: .recommended_candidate.trust, decision_trace: .recommended_candidate.decision_trace, evidence_snippets: .recommended_candidate.evidence_snippets}}' /tmp/silico-agent-diagnostics-sample.json
```

### 2. Preserve Backend Compact Diagnostics

In `recommendations_router.py`, ensure `response_detail="agent"` keeps:

- runtime status/degraded
- search query used
- discovery counts
- skipped preview with stage/reason/title
- top candidate decision trace
- top candidate query provenance
- score feature breakdown
- trust summary
- short evidence snippets

If payload size is a concern, cap arrays explicitly and mark truncation.

### 3. Add Optional Debug Detail Mode If Needed

If compact `agent` mode cannot carry enough detail, add a conservative option rather than overloading default payload:

- `response_detail="debug"` or an endpoint for job/report detail
- preserve existing `agent` default
- tests must verify both compact and debug shapes

Avoid breaking existing app calls.

### 4. Render Diagnostics In The App

In `apps/agent`, render backend-provided data directly:

- search/query variants used
- screened/fetched/extracted/rejected counts if available
- top skipped paper previews, grouped by stage
- why selected candidate won: strongest score features and decision trace
- trust status and validation caveats
- evidence snippets with source/title context

Do not create a new large operator dashboard in this slice; add compact, inspectable sections in the existing report/detail surfaces.

### 5. Add Tests Or Type Guards

Backend:

- test compact agent response preserves discovery summary and decision trace
- test skipped previews survive when full skipped arrays are omitted

Frontend:

- build must pass
- if there are existing tests for report meta/type mapping, update them

## Validation Matrix

Backend:

```bash
cd services/method-development
uv run pytest -q tests/test_recommendation_api.py tests/test_recommendation_engine.py
uv run python run_agent_eval_suite.py --suite smoke
```

Frontend:

```bash
cd apps/agent
npm run build
```

Manual app smoke if service/UI are run:

```bash
cd services/method-development
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

```bash
cd apps/agent
npm run dev
```

Run a known local fixture/local corpus case and confirm the report shows:

- status
- trust
- evidence
- skipped-paper preview if any
- query/search context for open-access

## Risks And Rollback Strategy

Risk: surfacing too much debug text can make the app feel noisy.

Mitigation:

- show compact summaries by default
- keep detailed lists behind expanders/detail panels
- use backend caps/truncation flags

Risk: app starts inferring ranking logic.

Mitigation:

- render backend `decision_trace` and `score.features`
- do not compute new scores in TypeScript

Rollback:

- revert frontend rendering while keeping backend compact diagnostics tests.

## Definition Of Done

- compact backend payload preserves trust-critical diagnostics
- app build passes
- a fresh demo run can explain selected, skipped, and degraded states without reading server logs

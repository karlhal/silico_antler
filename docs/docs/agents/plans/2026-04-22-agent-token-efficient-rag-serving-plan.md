---
status: completed
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development apps/agent RAG context optimization token efficiency
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-22-agent-multimodal-extraction-rag-architecture.md
  - ./2026-04-21-agent-tool-contracts-and-context-optimization.md
---

# Agent Token-Efficient RAG Serving Plan

## Goal and Success Criteria

Improve retrieval-augmented extraction and recommendation serving so the system spends tokens only where they buy quality, while returning smaller, higher-signal payloads to the app.

Success means:

- fewer full-document or broad-section LLM calls
- more field-targeted extraction from smaller evidence units
- lower average latency and token spend per successful recommendation run
- smaller app-facing payloads without losing trust-critical detail
- runtime telemetry can show where tokens and latency are actually being spent

## Scope

- open-access fetch, screening, extraction, and evidence handling in `services/method-development`
- compact app-facing recommendation payloads consumed by `apps/agent`
- runtime instrumentation related to context size, budget, and payload size

## Explicit Non-Goals

- no generic “chat over papers” product
- no immediate full multimodal figure/table pipeline in this slice
- no removal of evidence visibility from the app
- no move of ranking logic into the frontend

## Current State

The codebase already has some good efficiency decisions:

- app-facing recommendation calls already request `response_detail: "agent"` so the backend omits echoed requests and large paper lists
- open-access candidates are screened before full extraction
- evidence snippets can be vetted down to a smaller display quote

The main remaining waste points are upstream:

- open-access search can still fan out broadly before extraction
- `_extract_via_llm()` in `services/method-development/app/hplc_text_extraction.py` concatenates relevant sections or the first few pages into one large `context_text` block
- extraction is still document- or section-centric rather than evidence-unit-centric
- runtime summaries track budgets like search count, but do not yet expose token, cost, or payload-size telemetry

## Decision-Complete Implementation Approach

### Serving stance

The system should move from “retrieve a paper, send a lot of text, hope extraction works” toward “retrieve the smallest useful evidence unit, then escalate only if confidence stays low.”

### Stage 1: request planning and search budget

Introduce a structured run planner before search:

- classify request specificity
- decide query count
- decide max search budget
- decide whether open-access search needs broad exploration or narrow confirmation

Rules:

- specific analyte + matrix requests should use fewer, tighter queries
- vague requests can use broader search, but only with a capped follow-up budget
- the budget decision should be visible in runtime metadata

### Stage 2: evidence-unit retrieval

Create smaller retrieval units before LLM extraction:

- section fragments
- method paragraphs
- table-adjacent text fragments
- snippet candidates tied to exact source metadata

Each unit should carry:

- section label
- page number when available
- source kind
- lightweight feature tags such as detector, matrix, column, and runtime cues

This becomes the RAG layer used by extraction, explanation, and future review tooling.

### Stage 3: field-targeted extraction

Replace one broad extraction prompt with a ladder:

1. deterministic extraction from regex and schema heuristics
2. targeted LLM extraction only for unresolved fields
3. escalation to broader context only when field-level confidence remains low

Targeted extraction workers should focus on specific questions:

- column and system
- mobile phase and additives
- gradient and runtime
- detector and ionization clues
- entity linkage and analyte identity

This keeps tokens focused on missing decisions, not already-known text.

### Stage 4: cache and reuse

Cache at the right granularity:

- fetched source artifact by DOI or canonical URL
- normalized evidence units
- extraction outputs by source hash and extraction version
- vetted display snippets

The system should avoid paying LLM cost repeatedly for the same paper unless extraction logic or source content changed.

### Stage 5: payload compaction

Keep the app-facing contract intentionally small by default.

Default agent payload rules:

- include top candidates and the selected recommendation
- include only a short evidence preview set
- include summary counts for skipped papers and deeper diagnostics
- keep large evidence packs behind follow-up endpoints or operator/detail modes if needed

The current `agent` detail mode is the right direction and should be extended, not abandoned.

### Stage 6: token and latency telemetry

Add stage-level telemetry for:

- prompt input tokens
- completion tokens
- estimated cost
- evidence-unit counts
- payload size returned to the app
- cache hit / miss rates

Without this, “token efficiency” stays aspirational and untestable.

## Rollout Phases

### Phase 1: telemetry and budget visibility

- instrument token, latency, and payload metrics
- expose search-budget decisions and cache outcomes

### Phase 2: evidence-unit index

- split source text into reusable evidence units
- add metadata needed for field-targeted retrieval

### Phase 3: targeted extraction ladder

- preserve heuristic extraction as the fast path
- add field-specific LLM fallback only for unresolved or conflicting fields

### Phase 4: contract tightening

- trim default agent payloads further where the app does not need full arrays
- preserve richer operator/debug detail behind explicit detail modes

## Validation Matrix

- `cd services/method-development && uv run pytest -q`
- targeted extraction tests proving field-targeted fallbacks preserve or improve extraction quality
- contract tests verifying `response_detail: "agent"` remains compact and stable
- `cd apps/agent && npm run build`

## Verification Evidence

- 2026-04-21: `cd services/method-development && uv run pytest -q tests/test_recommendation_engine.py` passed (`21 passed`)
- 2026-04-21: `cd services/method-development && uv run pytest -q tests/test_hplc_extraction.py tests/test_recommendation_api.py` passed (`29 passed`)
- 2026-04-21: `cd apps/agent && npm run build` passed

## Risks and Rollback Strategy

- Risk: smaller evidence units lose context needed for correct extraction.
- Risk: token optimization hides important provenance from the app.
- Risk: cache invalidation becomes harder than the token savings are worth.

Rollback strategy:

- keep a broad-context extraction fallback during rollout
- treat compact payload changes as additive until the app proves it does not rely on omitted fields
- version extraction caches so prompt or heuristic changes can invalidate cleanly

## Decision Notes

- 2026-04-21: this plan is narrower than the multimodal RAG architecture doc; it is about near-term serving efficiency, not the full long-horizon research stack
- 2026-04-21: the current backend already has the right instinct with `response_detail: "agent"`; the next gain is upstream context reduction before extraction
- 2026-04-21: token efficiency should be treated as a measurable runtime property, not just prompt tightening
- 2026-04-21: implementation completed with request planning, evidence-unit telemetry, targeted extraction caching, and compact agent payload shaping validated in backend tests and the agent build

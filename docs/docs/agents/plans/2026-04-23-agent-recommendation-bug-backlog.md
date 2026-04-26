---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development apps/agent bug backlog recommendation engine
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-23-agent-app-relevance-and-performance.md
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
---

# Agent Recommendation Bug Backlog

## Purpose

Track the remaining correctness, latency, and quality defects in the recommendation path after the 2026-04-21 deep-dive.

Severity meanings:

- `P1`: directly harms recommendation quality, operator trust, or production latency
- `P2`: materially degrades usefulness or debuggability, but can ship temporarily
- `P3`: worthwhile cleanup or observability work

## P1 Issues

### P1. No Per-Run HTTP Client Reuse

Status:

- completed 2026-04-21 via run-scoped `OpenAccessPaperClient.open_run()` reuse in the recommendation engine

Files:

- `services/method-development/app/open_access_client.py`

Symptom:

- every search and fetch creates a new `httpx.Client`

Why it matters:

- unnecessary connection setup and redirect overhead
- slower live runs

Fix direction:

- create one reusable client per recommendation run and pass it through search and fetch operations

Acceptance criteria:

- a single run reuses one client for all OpenAlex and fetch calls
- live benchmark shows reduced median runtime

### P1. Open-Access Dedupe Is Too Weak

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- candidates are deduped by `(doi, paper_id, title)` as one combined key

Why it matters:

- the same paper can survive under alternate hosts or title variants

Fix direction:

- canonical DOI first
- normalized landing page URL second
- normalized PDF URL third
- normalized title fallback last

Acceptance criteria:

- known duplicate-host cases collapse to one candidate before fetch

### P1. Screening Is Still Too Lexical For Clinical Queries

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- title and abstract overlap still do most of the shortlist work

Why it matters:

- plant, food, pigment, and broad compositional papers still leak into the shortlist

Fix direction:

- add a bounded reranker or stronger deterministic matrix ontology rules before fetch

Acceptance criteria:

- reviewed bad-paper fixtures are screened out before fetch in clinical-plasma scenarios

### P1. Serial Fetch And Extraction Dominate Latency

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- even after removing artificial sleeps, live runs remain serial

Why it matters:

- latency scales linearly with shortlisted paper count

Fix direction:

- add bounded concurrency
- stop once enough viable candidates are found

Acceptance criteria:

- live run latency improves without increasing failure rate materially

## P2 Issues

### P2. Ranking Still Double-Counts Textual Relevance

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- `matrix_fit`, `literature_specificity`, and parts of `target_chemistry_fit` all reuse overlapping descriptor-text logic

Why it matters:

- mediocre text-relevant papers can be amplified artificially

Fix direction:

- separate retrieval relevance from final fit
- reduce lexical feature overlap in the final score

Acceptance criteria:

- score features have clearer, less correlated meanings

### P2. Trust Prior Exists But Does Not Affect Ranking

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- `review_trust_prior` is computed but has zero weight in the current ranking weights

Why it matters:

- explanation surface implies more than the ranker actually uses

Fix direction:

- either assign a bounded weight or remove it from ranking explanations

Acceptance criteria:

- every displayed ranking feature has meaningful ranking semantics

### P2. Agent Mode Still Truncates Debuggability Too Aggressively

Files:

- `services/method-development/app/recommendations_router.py`
- `apps/agent/src/pages/Dashboard.tsx`

Symptom:

- agent mode returns only top three candidates and summary previews

Why it matters:

- good for payload size, weak for debugging ranking tails

Fix direction:

- keep compact default behavior, but add a richer debug detail mode or on-demand follow-up endpoint

Acceptance criteria:

- operator-grade diagnostics are accessible without switching the app to a different product mode entirely

### P2. Query Provenance Is Not Surfaced

Files:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_schemas.py`
- `apps/agent/src/pages/Dashboard.tsx`

Symptom:

- the app cannot show which query variant surfaced each paper

Why it matters:

- impossible to debug whether query planning or screening caused a bad shortlist

Fix direction:

- attach `query_provenance` to candidates and runtime diagnostics

Acceptance criteria:

- the report workspace can show which query found the top candidate

## P3 Issues

### P3. Screening Reasons Are Free-Text Only

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- skip reasons and screen reasons are human-readable strings only

Why it matters:

- harder to aggregate, analyze, and regression-test

Fix direction:

- add structured reason codes alongside free text

Acceptance criteria:

- runtime telemetry can bucket skip reasons by code

### P3. No Explicit Search-Family Diversity Rule

Files:

- `services/method-development/app/recommendation_engine.py`

Symptom:

- shortlisted papers can still cluster too tightly around one topic family

Why it matters:

- extraction budget gets spent on near-duplicates

Fix direction:

- add topic or source diversity caps before full extraction

Acceptance criteria:

- shortlist contains fewer near-duplicate candidates in common query classes

## Recommended Order

1. per-run client reuse
2. stronger dedupe
3. bounded fetch and extraction concurrency
4. query provenance
5. reranking and matrix ontology improvements
6. score refresh
7. richer debug surfaces

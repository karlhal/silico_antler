---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent services/method-development evaluation proof quality
source_of_truth: docs/agents/execution-plans.md
---

# Agent Evals And Proof Spec

## Goal and Success Criteria

Define how the agent app and method-development service prove they work for the hackathon build and how future multimodal/RAG work should be measured later.

Success means:

- the pitch build has explicit acceptance criteria
- recommendation, upload, review, and reranking behavior are testable end to end
- demo resilience is validated intentionally
- future RAG/extraction work has measurable targets instead of vague ambition

## Scope

- app-level acceptance scenarios
- service-level contract and behavior checks
- review-to-corpus reranking proof
- upload-to-extraction proof
- demo resilience proof
- future multimodal and evidence-retrieval metrics

## Explicit Non-Goals

- no large benchmark creation in Wave 1
- no public leaderboard or research-paper style evaluation package
- no investor-facing KPI layer in this doc

## Current State

The repo already contains useful evaluation assets:

- `services/method-development/run_agent_eval_suite.py`
- paper-example extraction review utilities
- recommendation and retrieval tests
- Milvus retrieval tests

What is missing is a single proof framework that covers the actual product story:

- scientist gets a useful recommendation
- user can upload a paper
- operator can review and promote a record
- a later run benefits from promoted corpus knowledge
- the desktop app survives flaky network conditions without feeling broken

## Decision-Complete Implementation Approach

## Proof Layers

### Layer 1: Core recommendation proof

Prove that the product can generate and present a usable recommendation.

Required cases:

- open-access recommendation run succeeds
- local-corpus recommendation run succeeds
- ranked top candidate is stable for known fixture cases
- trust/evidence payload required by the app is present

### Layer 2: Upload and extraction proof

Prove that a user can bring a new source into the system.

Required cases:

- register HTML source document
- register PDF source document
- create review record from uploaded source
- run C12 preparation flow on uploaded source
- preserve extraction and validation outputs

### Layer 3: Review and corpus-growth proof

Prove that operator review materially changes future retrieval behavior.

Required cases:

- review record is created
- entity-resolution can make a record retrieval-ready
- approval freezes reviewed state
- promotion materializes the record into the local corpus
- later local-corpus retrieval can surface the promoted record
- demotion removes it from active reuse

### Layer 4: Demo resilience proof

Prove that the product remains usable when live dependencies degrade.

Required cases:

- healthy startup enters live mode
- unhealthy startup enters cached or demo-safe mode with explicit label
- prior successful recommendation can be recovered from cache
- upload attempt failure preserves local file context and allows retry
- degraded live result is labeled as degraded, not mistaken for full success

### Layer 5: Future RAG/multimodal proof

Define metrics now so later architecture work is measurable.

Required future metric families:

- modality classification accuracy
- extraction completeness by modality type
- entity-linkage accuracy
- evidence-grounding precision
- retrieval support quality at evidence-unit level
- recommendation lift from richer evidence indexing

## Acceptance Scenarios

### Scenario A: Scientist recommendation success

Given:

- valid system specs
- valid target chemistry
- available hosted services

Expect:

- ranked recommendation output
- visible trust/evidence state
- exportable result

### Scenario B: Upload-to-review success

Given:

- a supported source document

Expect:

- successful source registration
- review record preparation
- visible extraction and validation state
- send-to-review or operator review path available

### Scenario C: Review-to-corpus reranking success

Given:

- an approved and promoted review record

Expect:

- local-corpus retrieval and recommendation flow can surface that reviewed record
- review posture and corpus origin are visible in the app

### Scenario D: Demo resilience success

Given:

- unavailable or degraded live dependency

Expect:

- cached or demo-safe path selected intentionally
- result origin clearly labeled
- user still has a sensible next action

## Recommended Implementation Hooks

### Existing harness to extend

Extend `run_agent_eval_suite.py` with cases for:

- upload registration
- review creation
- approval/promotion roundtrip
- cached/demo-safe desktop-mode semantics represented at the contract layer where possible

### App-level test hooks

When desktop work starts, add smoke coverage for:

- startup config load
- health mode selection
- cached snapshot recovery
- upload initiation and retry path

### Fixture strategy

Keep a compact set of high-signal fixtures:

- one strong open-access recommendation case
- one degraded/fetch-failure case
- one uploadable source case
- one review-to-corpus reranking case

## Interfaces / Contracts / Types Affected

Potential additions:

- test fixtures for upload requests
- cached snapshot test fixtures
- richer eval output capturing result origin and review/corpus state

The proof framework assumes:

- canonical recommendation routes
- canonical source-document routes
- canonical review-record routes
- stable trust/review fields in response payloads

## Validation Matrix

For this documentation wave:

- `npm run agent:harness:check`

When implemented:

- `cd apps/agent && npm run build`
- `cd services/method-development && uv run pytest -q`
- `cd services/method-development && uv run python run_agent_eval_suite.py --suite smoke`
- desktop smoke checks once the shell exists

## Risks and Rollback

- Risk: evaluation focuses on backend slices but misses the real product story.
- Risk: demo resilience is treated informally and fails under live conditions.
- Risk: future RAG work ships without measurable benefit to recommendation quality or trust.

Rollback:

- keep the acceptance scenarios fixed around the product flow
- add research metrics only when they connect back to recommendation and trust outcomes

## Decision Notes

- 2026-04-21: Proof must cover the real hackathon story, not just backend unit behavior.
- 2026-04-21: Review-to-corpus reranking is a core product proof point.
- 2026-04-21: Future multimodal/RAG work is considered successful only if it improves trust, extraction quality, or recommendation quality in measurable ways.

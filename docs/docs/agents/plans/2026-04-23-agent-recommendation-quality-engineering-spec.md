---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development apps/agent recommendation quality latency ranking
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-23-agent-app-relevance-and-performance.md
  - ./2026-04-22-agent-ranking-scoring-retrieval-refresh.md
  - ./2026-04-22-agent-token-efficient-rag-serving-plan.md
  - ./2026-04-23-agent-recommendation-prompt-pack.md
  - ./2026-04-23-agent-recommendation-bug-backlog.md
---

# Agent Recommendation Quality Engineering Spec

## Goal And Success Criteria

Ship a recommendation-quality refresh for the agent app that materially improves:

- open-access relevance before extraction
- recommendation latency for live runs
- ranking quality for top-1 and top-3 recommendations
- auditability of why a paper was shortlisted, skipped, or selected

Success means:

- median `open_access` run latency drops by at least 35% on the smoke eval suite
- at least 50% fewer obviously irrelevant papers are fetched for the current problem classes
- top-1 recommendation quality improves on the reviewed golden cases
- runtime metadata is good enough for the app to explain search, skip, and ranking behavior without inventing frontend logic

## Product Problem Statement

The current system has three distinct issues that are getting conflated:

1. Retrieval recall and paper screening are too lexical.
2. Latency is dominated by serial fetch and extraction.
3. Final ranking still mixes retrieval, viability, and fit signals too loosely.

The implementation needs to separate those stages instead of tuning one giant heuristic block.

## Scope

Primary surfaces:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/open_access_client.py`
- `services/method-development/app/recommendation_context_optimizer.py`
- `services/method-development/app/recommendation_runtime.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/hplc_text_extraction.py`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`

## Explicit Non-Goals

- no frontend-side scoring or ranking duplication
- no opaque LLM-only final ranking in the serving path
- no de novo method generation in this slice
- no public API contract rewrite unless versioned

## Required Design Decisions

### 1. Separate The Pipeline Into Five Decisions

The serving path must become:

1. request normalization
2. open-access query planning
3. pre-fetch candidate screening and reranking
4. post-fetch viability gating
5. deterministic final ranking

Each stage must emit its own rationale.

### 2. Keep Final Ranking Deterministic

The final returned ranking must remain deterministic and explainable.

Allowed LLM use:

- query planning
- title/abstract candidate reranking
- cheap method-bearing evidence sniffing
- unresolved field extraction

Not allowed:

- an unconstrained LLM judge deciding the final winner directly from full candidate objects

### 3. Treat Open-Access Runs As A Budgeted Search Program

Each run must carry an explicit budget:

- query count
- search budget
- shortlist size
- fetch concurrency
- extraction concurrency
- stop condition

This budget must be visible in runtime metadata.

## Proposed Serving Architecture

### Stage A: Request Normalization

Inputs:

- `request_text`
- `analyte_name`
- `target_smiles`
- `impurity_smiles`
- `matrix_hint`
- `system_specs`
- `require_mass_spectrometry`

Outputs:

- normalized analyte aliases
- matrix family label
- retrieval mode class
- search intent class

Implementation notes:

- matrix hints should map into ontology buckets such as `clinical_plasma`, `clinical_serum`, `food_extract`, `plant_tissue`, `organic_solution`
- analyte family expansions should be deterministic when known
- this stage should not require an LLM

### Stage B: Query Planning

Goal:

- produce 3 to 5 search queries with different retrieval intent

Required query intents:

1. exact literature-style title query
2. analyte plus matrix plus method anchor
3. family-expanded analyte variant
4. matrix-relaxed fallback

Optional fifth query:

- request-class-specific clinical or bioanalytical intent repair query

Implementation:

- deterministic query builder stays as the baseline
- optional LLM query planner runs behind a feature flag and returns bounded JSON only

### Stage C: Candidate Screening And Reranking

Goal:

- shortlist only papers that are likely to contain a final usable method

Required inputs:

- title
- abstract
- year
- source host
- query provenance
- matrix family
- method mode requirements

Required outputs:

- `shortlist_score`
- `final_method_confidence`
- `matrix_match_confidence`
- `screen_reason`
- `drop_reason` when rejected

Implementation:

- keep deterministic lexical scoring as a baseline
- add a bounded reranker stage that consumes only title and abstract level inputs
- preserve deterministic fallback whenever the LLM stage fails or is disabled

### Stage D: Fetch, Evidence Sniff, And Extraction

Goal:

- avoid paying full extraction cost for papers that clearly do not contain an extractable final method

Required flow:

1. fetch shortlisted artifacts
2. build compact evidence units
3. run cheap method-bearing evidence sniff
4. only escalate to full extraction if the evidence sniff clears the threshold

Implementation:

- reuse one `httpx` client per run
- fetch with bounded concurrency
- run extraction with smaller bounded concurrency than fetch
- stop early once enough viable candidates are found

### Stage E: Deterministic Final Ranking

Final ranking must operate only on candidates that passed viability gating.

Required feature groups:

- retrieval relevance
- target chemistry fit
- impurity compatibility
- system fit
- detector compatibility
- matrix fit
- runtime fit
- extraction completeness
- evidence quality
- trust prior

Required rule:

- retrieval relevance must not be conflated with final scientific fit

## New Runtime Metadata Requirements

Add the following to runtime or candidate metadata:

- `query_provenance`: which query variant surfaced the paper
- `screening_model`: `deterministic` or `llm_reranker`
- `screening_reasons`
- `method_bearing_sniff_confidence`
- `fetch_attempt_count`
- `fallback_path`: `none`, `html_to_pdf`, `alternate_host`, etc.
- `candidate_stage_timings`

The agent UI should render this directly, not reconstruct it.

## Recommended Config Flags

Additive, default-off or conservative by default:

- `SILICO_METHOD_DEVELOPMENT_ENABLE_QUERY_PLANNER`
- `SILICO_METHOD_DEVELOPMENT_ENABLE_CANDIDATE_RERANKER`
- `SILICO_METHOD_DEVELOPMENT_ENABLE_METHOD_SNIFF`
- `SILICO_METHOD_DEVELOPMENT_FETCH_CONCURRENCY`
- `SILICO_METHOD_DEVELOPMENT_EXTRACTION_CONCURRENCY`
- `SILICO_METHOD_DEVELOPMENT_SHORTLIST_SIZE`
- `SILICO_METHOD_DEVELOPMENT_TARGET_VIABLE_CANDIDATES`

## PR Breakdown

### PR 1: Retrieval Planner And Dedupe

Files:

- `recommendation_engine.py`
- `recommendation_schemas.py`
- `recommendation_runtime.py`

Scope:

- strengthen query planning
- add per-query provenance
- fix canonical DOI and URL dedupe
- expose search budget decisions clearly

Acceptance criteria:

- duplicate papers from alternate hosts are collapsed reliably
- runtime metadata shows which query variant surfaced each shortlisted candidate
- query-builder and screening tests pass

### PR 2: Candidate Reranker

Files:

- `recommendation_engine.py`
- `gemini_orchestration_client.py` or equivalent client wrapper
- `recommendation_schemas.py`

Scope:

- add optional title and abstract reranker behind a feature flag
- emit structured screen reasons
- keep deterministic fallback

Acceptance criteria:

- reranker never breaks the run on malformed output
- output is schema-validated
- broad chemistry or plant-context papers are downgraded for clinical plasma requests

### PR 3: Fetch Reuse, Concurrency, And Evidence Sniff

Files:

- `open_access_client.py`
- `recommendation_engine.py`
- `recommendation_context_optimizer.py`
- `hplc_text_extraction.py`

Scope:

- single reusable client per run
- bounded concurrency for fetch and extraction
- lightweight method-bearing evidence sniff prior to full extraction

Acceptance criteria:

- median live run time drops materially in local profiling
- blocked publisher pages no longer stall the whole run linearly
- runs still stop early after enough viable candidates are found

### PR 4: Ranking Refresh

Files:

- `recommendation_engine.py`
- `retrieval_store.py`
- `recommendation_schemas.py`

Scope:

- split retrieval relevance from final ranking fit
- reduce double-counting across lexical features
- make trust prior meaningful or remove it from ranking explanations

Acceptance criteria:

- ranking explanations map cleanly to weighted features
- pairwise ordering tests become easier to write and reason about
- golden-case regressions are measurable

### PR 5: Agent Diagnostics Surfaces

Files:

- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`
- backend compact response shaping if needed

Scope:

- show query provenance
- show screened versus fetched versus extracted counts
- show skip previews and ranking differentiators without switching to operator mode

Acceptance criteria:

- the report workspace can answer “why this was skipped” and “why this won”
- the app still uses backend-provided data directly

## Validation Matrix

### Backend

Run on each PR:

```bash
cd services/method-development
uv run pytest -q tests/test_recommendation_engine.py tests/test_retrieval_store.py
```

Before merging the full slice:

```bash
cd services/method-development
uv run pytest -q
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
```

### Frontend

```bash
cd apps/agent
npm run build
```

### Docs Harness

```bash
cd /Users/nick/silico_website/silico
npm run agent:harness:check
```

## Rollout Strategy

Rollout order:

1. ship retrieval planner and dedupe improvements without LLM dependency
2. ship reranker behind a flag
3. ship method sniff behind a flag
4. enable concurrency conservatively
5. recalibrate deterministic final ranking after the new shortlist distribution is stable

Required telemetry gate before broad enablement:

- success rate
- degraded rate
- no-trustworthy-candidates rate
- average papers fetched per run
- average extracted papers per run
- median and p95 runtime

## Risks And Rollback Strategy

Risks:

- reranking may become too strict and hurt recall
- concurrency may stress flaky publisher endpoints
- method sniff may wrongly suppress papers that contain methods in awkward layouts
- score refresh may reshuffle trusted local-corpus ordering unexpectedly

Rollback:

- each new stage stays behind its own flag
- deterministic baseline must remain available
- ranking-weight changes should be reversible without schema changes

## Decision Notes

- the highest-ROI improvements are shortlist quality and fetch/extract concurrency, not cosmetic frontend work
- final ranking must remain deterministic even if earlier retrieval stages use prompts
- diagnostics must be surfaced in the agent mode contract or the app cannot explain the pipeline well enough

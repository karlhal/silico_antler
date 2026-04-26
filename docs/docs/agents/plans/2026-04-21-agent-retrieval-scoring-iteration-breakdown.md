---
status: active
owner: platform
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development retrieval-scoring iteration
source_of_truth: docs/agents/execution-plans.md
source_spec: ../../AI HPLC Method Development Specification.md
source_report: ../../agent-app-implementation-report.md
---

# Agent Retrieval And Scoring Iteration Plan

## Goal and Success Criteria

Build the next useful iteration of the agent app as a **high-trust retrieval and scoring product** for prior-literature HPLC method recommendation.

Success means the product can:

- collect the system and chemistry inputs actually required for ranking
- search either the curated local corpus or open-access literature through a consistent app-facing workflow
- rank prior methods using explicit system, analyte, matrix, practical, and confidence signals
- scale recommended methods consistently across source modes
- show enough evidence, provenance, and caveats for a scientist to trust the output as a starting point
- grow stronger over time as reviewed literature methods are promoted into the local corpus

The product should answer:

`What prior literature methods best fit my system and target, and why should I trust them?`

It should not try to answer:

`What entirely new optimal method should I invent from first principles?`

## Trust Requirement

Every user-facing recommendation in this iteration must make trust legible.

Minimum expectation:

- source identity and citation
- source mode used
- score breakdown
- rationale text
- scaling notes
- evidence snippets or provenance summary
- validation or review state where available

## Scope

This plan covers the next retrieval/scoring-focused round for:

- `apps/agent` as the primary user-facing surface
- `services/method-development` as the primary recommendation, retrieval, extraction, and trust backend
- `apps/api` only where needed to support chemistry helper flows already referenced by the app, such as SMILES name resolution

Primary implementation homes:

- `apps/agent` for workflow UI, input parity, trust presentation, and source-mode clarity
- `services/method-development` for recommendation contracts, scoring, retrieval integration, scaling, provenance, review-backed promotion, and extraction quality

## Current Status

Based on [`docs/agent-app-implementation-report.md`](../../agent-app-implementation-report.md):

- the app already has a strong staged workflow shell
- the open-access recommendation path is the most complete end-to-end flow
- the app's local mode is currently a retrieval-corpus search hidden behind the label `local`
- the app does not expose the chemistry-native inputs that local retrieval actually depends on
- local and open-access paths currently use different scaling implementations
- backend provenance, review, and orchestration capabilities are significantly ahead of what the UI surfaces
- repo boundary docs now treat `apps/agent` as a first-class app boundary with a documented build gate

## Explicit Non-Goals

Do not treat these as first-pass tasks in this round:

- surrogate ML or XGraphBoost implementation
- PINN / LSS / retention-coefficient modeling
- Bayesian optimization of gradients
- simulated chromatogram generation
- figure-to-structure extraction
- R-group reconstruction from structure tables
- full multimodal planner/worker orchestration
- broad review UI for every backend-only operator workflow
- report/export polish beyond what is needed to support retrieval trust and handoff

This round is about making the **retrieval and scoring agent** excellent, not about reviving the full autonomous HPLC AI roadmap.

## Decision-Complete Implementation Approach

### Product Stance

The agent app should become a **single retrieval-and-scoring experience** with two evidence sources:

1. `local_corpus`
2. `open_access`

The user-facing product should not expose two fundamentally different backend abstractions under the same label.

### Source-Mode Stance

Adopt these canonical backend meanings:

- `local_corpus`: search the approved/seeded retrieval corpus and rank prior methods
- `open_access`: search and extract candidate methods from live open-access papers
- `local_files`: keep this as a backend or CLI capability for direct paper-file recommendation work, but do not treat it as the same thing as `local_corpus`

Compatibility rule:

- keep accepting legacy `local` in backend adapters where needed during migration
- the app should move to the canonical names and stop depending on legacy ambiguity

### Recommendation Contract Stance

The app should use **one recommendation report shape** for both source modes.

Concrete rule:

- `POST /recommendation/recommend` becomes the primary app-facing discovery contract
- `/retrieval/query` remains available as a lower-level backend capability and testable primitive, not the main app contract

### Scoring Stance

Use explicit, inspectable score dimensions:

- system match
- analyte match
- matrix fit
- practical fit
- extraction confidence or review confidence
- literature relevance

For `local_corpus`, scoring should be recommendation-style, not raw similarity-only ranking.

For `open_access`, keep ranking deterministic and evidence-based. Do not introduce LLM-truth-based scoring.

### Scaling Stance

There must be one canonical scaling implementation for user-facing recommendations.

Concrete rule:

- move all user-facing scaling to the backend recommendation layer
- the app renders scaled output and notes; it does not recompute its own source-mode-specific formulas

### Impurity Stance

Impurity-aware ranking is required where the data is trustworthy.

Concrete rule:

- `local_corpus`: full target + impurity scoring is required
- `open_access`: accept impurity inputs and pass them through request contracts, but only use impurity-aware ranking when entity linkage is confident enough; otherwise label the result as target-focused ranking with impurity notes rather than pretending full mixture scoring

### Trust And Provenance Stance

A user must be able to tell:

- what matched well
- what was inferred
- what was scaled
- what is review-backed vs seeded vs newly extracted
- what still needs manual verification

### Corpus Growth Stance

Open-access extraction work should improve the future local corpus over time.

Concrete rule:

- high-quality reviewed records should be easy to promote into the local recommendation corpus
- the app does not need full review tooling in this round, but the backend must keep this pathway clean and visible

## Dependency Backbone

The chunks depend on each other in this order:

1. acceptance harness and golden cases
2. discovery contract and source-mode normalization
3. chemistry-native input completeness
4. local corpus recommendation engine
5. shared scaling engine
6. evidence and trust surfacing
7. impurity-aware ranking
8. open-access extraction and ranking hardening
9. review-backed corpus promotion
10. app boundary docs and quality gates

This order is deliberate:

- first lock what "good" means
- then remove source-mode ambiguity
- then expose the right inputs
- then make local corpus ranking recommendation-grade
- then unify scaling and trust presentation
- only afterward deepen open-access quality and corpus-growth loops

## Chunk Registry

| Chunk | Status | Name | Primary Boundary | Depends On | Outcome |
| --- | --- | --- | --- | --- | --- |
| G1 | Completed | Recommendation Evaluation Harness | `services/method-development`, `apps/agent` | none | Golden cases define ranking, trust, and scaling expectations |
| G2 | Completed | Discovery Contract Normalization | `services/method-development`, `apps/agent` | G1 | One app-facing recommendation flow across source modes |
| G3 | Completed | Chemistry-Native Input Completeness | `apps/agent`, `apps/api` | G2 | UI collects the data needed for local and impurity-aware ranking |
| G4 | Completed | Local Corpus Recommendation Engine | `services/method-development` | G1, G2 | Local corpus mode returns recommendation-grade ranked candidates |
| G5 | Completed | Shared Scaling Engine | `services/method-development`, `apps/agent` | G2, G4 | One scaling implementation and one recommendation payload |
| G6 | Proposed | Evidence And Trust Surfacing | `services/method-development`, `apps/agent` | G4, G5 | Users can inspect evidence, confidence, review state, and rationale |
| G7 | Completed | Impurity-Aware Ranking | `apps/agent`, `services/method-development` | G3, G4, G6 | Target + impurity scoring works end to end where trustworthy |
| G8 | Completed | Open-Access Extraction And Ranking Hardening | `services/method-development` | G1, G2, G6 | Live literature discovery becomes more reliable and less noisy |
| G9 | Completed | Review-Backed Corpus Promotion | `services/method-development` | G4, G6, G8 | Strong open-access findings can feed future local recommendations |
| G10 | Completed | Agent App Boundary Normalization | `apps/agent`, repo docs | G2, G6 | App docs, maps, and quality gates match the actual product |

## Recommended Execution Order

### G1 - Recommendation Evaluation Harness

Status:

- completed

Purpose:

- define what "good retrieval and scoring behavior" means before changing heuristics, contracts, or UI flows

Deliverables:

- deterministic golden cases for:
  - local corpus recommendation ordering
  - open-access recommendation ordering
  - score breakdown expectations
  - scaling output expectations
  - evidence and rationale presence
- regression tests for source-mode semantics so `local_corpus`, `open_access`, and `local_files` cannot silently blur together again
- a compact acceptance matrix in the plan or adjacent test docs that future chunks can point to

Likely files:

- `services/method-development/tests/test_recommendation_engine.py`
- new focused recommendation API tests under `services/method-development/tests/`
- optional app contract smoke tests if a lightweight frontend test surface is introduced

Non-goals:

- no scoring or UI behavior changes yet
- no extraction heuristic expansion yet

Validation:

- `cd services/method-development && uv run pytest -q tests/test_recommendation_engine.py`
- any new focused recommendation API tests
- `cd apps/agent && npm run build`

Completion signal:

- later chunks can change logic while proving they preserved or improved ranking/trust outcomes against named cases

Current slice landed:

- fixture-backed golden cases now cover:
  - open-access recommendation baseline
  - local-file recommendation baseline
  - local-corpus exact-match baseline
  - local-corpus target-plus-impurity baseline
- recommendation acceptance coverage currently lives in:
  - `services/method-development/tests/fixtures/recommendation_golden_cases.json`
  - `services/method-development/tests/test_recommendation_golden_cases.py`

Prompt to use later:

```text
Implement Chunk G1 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Create a recommendation evaluation harness for the agent app retrieval/scoring iteration.

Context:
- Source report: `docs/agent-app-implementation-report.md`
- Existing recommendation logic: `services/method-development/app/recommendation_engine.py`
- Existing app contract: `apps/agent/src/lib/api.ts`

Do:
- add deterministic golden cases for both local-corpus and open-access recommendation flows
- assert ranking order, score breakdown presence, scaling output shape, and evidence/rationale presence
- add regression coverage for canonical source-mode semantics
- keep fixtures small and explainable

Do not:
- refactor the recommendation engine yet
- change app behavior yet

Definition of done:
- the repo has a clear acceptance harness for future retrieval/scoring work
- later chunks can prove quality changes against named cases instead of intuition
```

### G2 - Discovery Contract Normalization

Status:

- completed

Purpose:

- eliminate the current ambiguity where the app's `local` mode means retrieval corpus search while the backend's `local` recommendation mode means local files

Deliverables:

- canonical source-mode names:
  - `local_corpus`
  - `open_access`
  - `local_files`
- one app-facing recommendation contract that supports both `local_corpus` and `open_access`
- compatibility handling for legacy `local` where needed during migration
- app-side updates so the dashboard uses the normalized source-mode vocabulary

Likely files:

- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendations_router.py`
- `apps/agent/src/types/index.ts`
- `apps/agent/src/lib/api.ts`
- `apps/agent/src/hooks/useAgentWorkflow.ts`

Non-goals:

- no new ranking logic yet beyond contract normalization
- no UI chemistry-input work yet

Validation:

- G1 acceptance cases
- focused request/response schema tests
- `cd apps/agent && npm run build`

Completion signal:

- the app no longer depends on overloaded `local` semantics
- there is one clear discovery contract for the app

Current slice landed:

- backend recommendation requests now accept canonical `local_files`, `local_corpus`, and `open_access`, while preserving legacy `local` as a compatibility alias
- `/recommendation/recommend` has route-level coverage for canonical `local_corpus`, legacy `local`, and local-corpus validation failure behavior
- the app workflow uses the normalized source names and the app API layer no longer exposes the lower-level retrieval helper as part of the main discovery path
- recommendation golden cases now encode canonical `local_files` semantics instead of the old overloaded `local` label

Prompt to use later:

```text
Implement Chunk G2 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Normalize discovery contracts and source-mode semantics across the agent app and method-development backend.

Context:
- Current mismatch is documented in `docs/agent-app-implementation-report.md`
- Existing schemas live in `services/method-development/app/recommendation_schemas.py`
- Existing app source selection lives in `apps/agent/src/hooks/useAgentWorkflow.ts`

Do:
- introduce canonical source modes `local_corpus`, `open_access`, and `local_files`
- keep backward compatibility where needed for legacy `local`
- make `POST /recommendation/recommend` the primary app-facing discovery contract
- update app types/client code to use the canonical semantics

Do not:
- add new scoring heuristics yet
- expand the UI inputs yet

Definition of done:
- source-mode naming is no longer ambiguous
- the app and backend agree on what each source mode means
```

### G3 - Chemistry-Native Input Completeness

Status:

- completed

Purpose:

- expose the chemistry and constraint inputs the backend already expects, so the app can stop relying on hidden demo state

Deliverables:

- visible target SMILES field in the app
- impurity SMILES input list in the app
- optional name-resolution helper using `/api/v1/chemistry/smiles/resolve-name`
- actual custom text inputs when `Other` is selected for manufacturer, chemistry, or matrix
- validation rules that block local-corpus runs when required chemistry inputs are missing

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/types/index.ts`
- `apps/agent/src/lib/api.ts`
- optional light touch to `apps/api` only if the existing SMILES helper needs contract cleanup

Non-goals:

- no molecular sketcher or structure-drawing UI
- no automatic compound canonicalization beyond the existing helper

Validation:

- `cd apps/agent && npm run build`
- focused app interaction tests if a frontend test surface exists
- manual local-corpus smoke path with and without SMILES

Completion signal:

- local-corpus mode is no longer secretly dependent on `loadDemoData()`
- the UI can collect target + impurity chemistry explicitly

Current slice landed:

- the agent app now exposes a visible target SMILES input and repeatable impurity SMILES rows
- the app can resolve target and impurity names through `/api/v1/chemistry/smiles/resolve-name`
- selecting `Other` for manufacturer, stationary phase, or matrix now reveals the required custom text field instead of silently dropping context
- the recommendation payload now passes target SMILES, impurity SMILES, and the effective custom manufacturer, chemistry, and matrix values
- local-corpus discovery is now blocked in the UI when target SMILES is missing, and the source card makes that requirement explicit

Prompt to use later:

```text
Implement Chunk G3 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Expose the chemistry-native inputs required for strong retrieval and scoring in the agent app.

Context:
- Current gaps are listed in `docs/agent-app-implementation-report.md`
- UI state lives in `apps/agent/src/hooks/useAgentWorkflow.ts`
- Main form rendering lives in `apps/agent/src/pages/Dashboard.tsx`
- SMILES name resolution helper already exists in `apps/agent/src/lib/api.ts`

Do:
- add target SMILES input
- add impurity SMILES inputs
- add real custom-entry inputs for `Other` selections
- optionally use the existing SMILES-name helper for UX support
- add validation so local-corpus runs cannot start without the chemistry data they need

Do not:
- add new backend ranking logic yet
- add a chemistry drawing tool

Definition of done:
- a user can enter the chemistry data required for local corpus search and impurity-aware ranking without hidden demo shortcuts
```

### G4 - Local Corpus Recommendation Engine

Status:

- completed

Purpose:

- make local corpus mode recommendation-grade instead of similarity-only

Deliverables:

- backend recommendation branch for `local_corpus` that:
  - starts from retrieval-store matches
  - applies recommendation-style system/analyte/matrix/practical scoring
  - returns the same report/candidate shape used by open-access mode
- inclusion of `match_rationale` and `review_summary` inside local-corpus recommendation candidates
- app migration so local mode uses the recommendation contract instead of directly calling `/retrieval/query`

Likely files:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/retrieval_store.py`
- `services/method-development/app/main.py` only if thin adapter changes are needed
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/lib/api.ts`

Non-goals:

- no open-access extraction changes yet
- no corpus schema rewrite

Validation:

- G1 local-corpus acceptance cases
- retrieval + recommendation focused tests in `services/method-development/tests/`
- `cd apps/agent && npm run build`

Completion signal:

- local-corpus mode produces recommendation candidates, not a separate lower-trust result shape

Current slice landed:

- `local_corpus` candidates now use recommendation-style system, analyte, matrix, practical, extraction-confidence, and literature-relevance scoring instead of mostly exposing raw retrieval score
- local-corpus recommendation candidates now include retrieval `match_rationale` and `review_summary` alongside the existing extraction and scaling payload
- focused tests now prove that recommendation scoring can reorder exact molecular matches by better system and practical fit instead of preserving retrieval-order ties
- acceptance coverage now includes a local-corpus recommendation case, not just raw retrieval-store ranking cases

Prompt to use later:

```text
Implement Chunk G4 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Turn local corpus mode into a recommendation-grade ranking path that matches the open-access report shape.

Context:
- Current local-mode mismatch is documented in `docs/agent-app-implementation-report.md`
- Retrieval primitives live in `services/method-development/app/retrieval_store.py`
- Recommendation logic lives in `services/method-development/app/recommendation_engine.py`

Do:
- add a `local_corpus` recommendation branch that starts from retrieval matches
- score candidates using explicit system, analyte, matrix, and practical-fit logic
- return the same report shape as open-access mode
- include retrieval `match_rationale` and `review_summary` in the local recommendation candidates
- update the app to consume the unified recommendation contract

Do not:
- rewrite corpus storage
- expand open-access heuristics yet

Definition of done:
- the app's local mode is a real recommendation experience and no longer a thin similarity lookup bolted into the UI
```

### G5 - Shared Scaling Engine

Status:

- completed

Purpose:

- remove the current split-brain scaling logic and establish one canonical user-facing scaling implementation

Deliverables:

- one backend scaling utility used by both `local_corpus` and `open_access` recommendation branches
- consistent scaled fields:
  - flow rate
  - injection volume
  - runtime
  - gradient profile when available
  - scaling notes and warnings
- app-side removal of local recomputation logic; the UI becomes render-only for scaled methods

Likely files:

- `services/method-development/app/recommendation_engine.py`
- optional new scaling utility module under `services/method-development/app/`
- `services/method-development/app/recommendation_schemas.py`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`

Non-goals:

- no mechanistic pressure simulator
- no PINN/LSS model work

Validation:

- G1 scaling acceptance cases
- focused unit tests for same input producing same scaled outputs regardless of source mode
- `cd apps/agent && npm run build`

Completion signal:

- source-mode choice no longer changes the scaling formula

Current slice landed:

- scaling moved into a dedicated backend utility in `services/method-development/app/method_scaling.py`
- `open_access`, `local_files`, and `local_corpus` now all emit the same `recommended_method` shape with runtime, gradient, notes, and warnings
- focused tests now prove equivalent source methods produce identical scaled outputs across local-files and local-corpus recommendation branches
- the app no longer fabricates fallback scaled values or concatenates notes into a lossy string; it renders backend scaling payloads directly

Prompt to use later:

```text
Implement Chunk G5 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Create one canonical scaling engine for user-facing recommendations across local-corpus and open-access modes.

Context:
- Current split scaling behavior is documented in `docs/agent-app-implementation-report.md`
- Backend scaling currently lives in `services/method-development/app/recommendation_engine.py`
- UI-side scaling currently lives in `apps/agent/src/hooks/useAgentWorkflow.ts`

Do:
- move user-facing scaling to a single backend path
- return consistent scaled fields and notes in the recommendation payload
- remove UI-side scaling recomputation
- add tests proving both source modes use the same scaling behavior

Do not:
- add advanced pressure or retention modeling
- change the underlying recommendation contract shape except as needed for consistency

Definition of done:
- scaled recommendations are generated by one source of truth and rendered consistently in the app
```

### G6 - Evidence And Trust Surfacing

Status:

- completed

Purpose:

- make ranking legible and trustworthy instead of opaque

Deliverables:

- recommendation candidate payload extensions for:
  - evidence snippets
  - source kind
  - validation status
  - issue counts or warning summaries
  - review summary
  - score breakdown display data
- app report UI that shows:
  - score dimensions
  - why this method ranked here
  - what is review-backed vs seeded vs newly extracted
  - what still needs manual verification

Likely files:

- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/recommendation_engine.py`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`

Non-goals:

- no full backend review console in the app
- no exhaustive provenance browser in this round

Validation:

- G1 trust/evidence acceptance cases
- targeted frontend checks for rendering score breakdowns and evidence blocks
- `cd apps/agent && npm run build`

Completion signal:

- users can tell not just what ranked first, but why and how much manual trust is still required

Prompt to use later:

```text
Implement Chunk G6 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Surface evidence, confidence, and trust signals in the recommendation payload and agent app UI.

Context:
- Backend provenance and review state already exist but are mostly not shown in `apps/agent`
- Current report gaps are documented in `docs/agent-app-implementation-report.md`

Do:
- extend recommendation payloads with score breakdowns, evidence snippets, review summary, and validation/trust metadata
- update the app report view to render those signals clearly
- make it obvious what was matched, what was inferred, and what needs manual verification

Do not:
- build a full review management UI
- flood the user with raw backend internals

Definition of done:
- the recommendation UI shows enough trust context that a scientist can judge whether to try the method
```

### G7 - Impurity-Aware Ranking

Status:

- completed

Purpose:

- support mixture-aware retrieval and scoring wherever the data is trustworthy enough

Deliverables:

- app-side impurity collection and request plumbing
- `local_corpus` recommendation scoring that uses target + impurity contributions explicitly
- UI explanation of when impurity-aware ranking is active
- `open_access` fallback rule:
  - accept impurity inputs
  - use them only when entity linkage is confident enough
  - otherwise label the run as target-focused ranking with impurity notes

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/retrieval_store.py`

Non-goals:

- no attempt to force impurity scoring in open-access mode when the extracted chemistry is not trustworthy

Validation:

- G1 impurity-aware acceptance cases
- focused backend tests for target + impurity contribution math
- `cd apps/agent && npm run build`

Completion signal:

- local-corpus mode can genuinely rank methods for mixtures, not just single targets

Current slice landed:

- recommendation payloads now expose explicit ranking context so the app can distinguish target-only, mixture-aware, and target-only fallback runs
- the agent app report now labels the ranking mode and explains when impurity-aware scoring was active vs skipped for trust reasons
- `open_access` and `local_files` now report an honest target-only fallback whenever impurity inputs are present but extracted entity linkage is not trustworthy enough
- `MilvusRetrievalStore` now applies the same target-plus-impurity aggregate scoring pattern as the seeded retrieval store instead of dropping impurity contributions
- focused backend tests now cover ranking-context behavior and Milvus mixture-aware retrieval, and `apps/agent` builds cleanly with the new contract

Prompt to use later:

```text
Implement Chunk G7 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Add end-to-end impurity-aware ranking where the recommendation data is trustworthy enough.

Context:
- Retrieval already supports impurity scoring in `services/method-development/app/retrieval_store.py`
- The current app always sends empty impurity lists
- Open-access entity linkage is still less trustworthy than local review-backed corpus data

Do:
- add impurity inputs to the app and send them through the recommendation contract
- implement impurity-aware recommendation scoring for `local_corpus`
- clearly label when impurity-aware ranking is active
- keep `open_access` target-focused unless entity linkage is confident enough, and label that fallback honestly

Do not:
- fake impurity scoring for weakly linked open-access extractions

Definition of done:
- mixture-aware ranking works in the local corpus path and the app explains the ranking mode clearly
```

### G8 - Open-Access Extraction And Ranking Hardening

Status:

- completed

Purpose:

- improve live literature recommendation quality without drifting into deferred multimodal or ML work

Deliverables:

- stronger search-query construction and candidate filtering
- better handling of HTML-first vs PDF fallback and per-paper failures
- improved final-method selection heuristics for:
  - chromatography-system candidates
  - mobile-phase candidates
  - final vs trial/comparison gradients
  - timing candidates
- expanded golden fixtures and prompt-style evaluations for known representative papers

Likely files:

- `services/method-development/app/open_access_client.py`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/hplc_text_extraction.py`
- `services/method-development/tests/`
- `services/method-development/run_paper_example_evaluation.py`

Non-goals:

- no figure parsing
- no OCR-first scanned-PDF expansion unless a concrete blocker appears
- no LLM-truth-based extraction scoring

Validation:

- G1 open-access acceptance cases
- `cd services/method-development && uv run pytest -q`
- paper-example evaluation scripts as appropriate

Completion signal:

- the open-access path yields fewer junk candidates, better final-method picks, and clearer failure modes

Current slice landed:

- request-aware open-access search queries now condense analyte, matrix, and mode terms instead of forwarding the raw UI sentence as-is
- open-access discovery now oversamples OpenAlex results, screens them for analyte/matrix/chromatography relevance, and reports screened-out papers explicitly
- HTML fetch now falls back to PDF not only on transport errors but also on thin or blocked landing pages, and the recommendation report now preserves per-paper skip diagnostics for screening, fetch, and extraction failures
- extraction heuristics now include stronger final-vs-trial cues for selected/optimized method language and better compact-PDF normalization for live-paper parsing
- regression coverage now includes request screening, fetch/extraction skip reporting, HTML-to-PDF fallback, and an additional prompt-style paper-example review case focused on ignoring optimization-only trial conditions
- live agent-app debugging notes, landed fixes, and remaining exploration items are captured in `docs/agents/plans/2026-04-21-open-access-demo-failure-analysis.md`

Prompt to use later:

```text
Implement Chunk G8 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Harden the open-access recommendation path so it produces stronger and more reliable prior-literature recommendations.

Context:
- Current open-access path is the strongest end-to-end flow but still has extraction and candidate-quality gaps
- Relevant code lives in `services/method-development/app/open_access_client.py`, `services/method-development/app/recommendation_engine.py`, and `services/method-development/app/hplc_text_extraction.py`

Do:
- improve query building and candidate filtering
- improve HTML/PDF fetch fallback and skip reporting
- strengthen final-method selection heuristics for system, mobile phase, gradient, and timing candidates
- expand golden fixtures and regression coverage for known papers

Do not:
- add multimodal figure extraction
- add ML-based ranking

Definition of done:
- the open-access path is more reliable, more explainable, and better aligned with final-method extraction rather than trial-condition noise
```

### G9 - Review-Backed Corpus Promotion

Status:

- completed

Purpose:

- make strong open-access findings improve future local recommendations instead of remaining isolated one-off discoveries

Deliverables:

- a clean reviewed-record promotion path into the local recommendation corpus
- recommendation behavior that preserves and surfaces seeded vs review-backed distinctions
- light operator documentation or CLI support for approving/promoting strong records
- optional tie-break or preference rules that favor review-backed records when total scores are comparable

Likely files:

- `services/method-development/app/review_records_router.py`
- `services/method-development/app/review_record_materialization.py`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/README.md`

Non-goals:

- no full multi-user review application
- no end-user approval UI in `apps/agent`

Validation:

- focused review-record and materialization tests
- local-corpus recommendation tests showing review-backed records surface correctly

Completion signal:

- a good open-access extraction can become a better future local-corpus recommendation source

Current slice landed:

- review records now persist explicit local-corpus promotion state instead of treating approval as an invisible side effect
- the backend exposes `POST /review-records/{review_record_id}/promotion` so operators can promote or remove approved records without rebuilding the review record
- service startup and orchestration now sync only promoted review-backed snapshots into the retrieval corpus
- local-corpus recommendation payloads now surface seeded vs review-promoted provenance explicitly and prefer review-backed records when scores are effectively tied
- focused API, persistence, retrieval, recommendation, and orchestration tests cover approve-without-promote, promote/unpromote, startup rehydration, and near-tie review-backed preference

Prompt to use later:

```text
Implement Chunk G9 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Make reviewed open-access findings strengthen the future local recommendation corpus.

Context:
- Review records and approval/materialization already exist in the method-development backend
- The app currently benefits only indirectly from that backend capability

Do:
- clean up the promotion path from reviewed extraction to local corpus recommendation use
- preserve seeded vs review-backed provenance distinctions in recommendation payloads
- add light operator-facing docs or CLI guidance for promotion workflows
- optionally prefer review-backed records when scores are near-tied

Do not:
- build a full approval UI in the app

Definition of done:
- the system can learn from prior reviewed literature work by promoting good records into future recommendation runs
```

### G10 - Agent App Boundary Normalization

Status:

- completed

Purpose:

- make the repo documentation and quality gates reflect the fact that `apps/agent` is now a real product boundary

Deliverables:

- `apps/agent/README.md`
- `apps/agent/AGENTS.md`
- root doc updates so `apps/agent` appears in:
  - `AGENTS.md`
  - `README.md`
  - `docs/architecture/repo-structure.md`
  - `docs/agents/architecture-boundaries.md`
  - `docs/agents/quality-gates.md`
  - `docs/agents/release-and-testing.md` if applicable
- explicit quality gate for the agent app, currently `cd apps/agent && npm run build`

Likely files:

- repo root docs listed above
- `apps/agent/README.md`
- `apps/agent/AGENTS.md`

Non-goals:

- no release automation buildout beyond documenting the current gate

Validation:

- `cd apps/agent && npm run build`
- `npm run agent:harness:check`

Completion signal:

- future agents can discover and validate the agent app without relying on chat-only context

Current slice landed:

- added `apps/agent/README.md` and `apps/agent/AGENTS.md` for local runtime, boundary, and validation guidance
- updated root maps and architecture docs so `apps/agent` is discoverable alongside the other first-class app boundaries
- documented `cd apps/agent && npm run build` as the explicit quality gate in repo guidance
- updated release/testing guidance to record the current build-only validation path without inventing new release automation

Prompt to use later:

```text
Implement Chunk G10 from `docs/agents/plans/2026-04-21-agent-retrieval-scoring-iteration-breakdown.md`.

Goal:
Normalize repo docs and quality gates so `apps/agent` is treated as a first-class app boundary.

Context:
- Current repo-level omissions are documented in `docs/agent-app-implementation-report.md`
- `apps/agent` currently has no local `README.md` or `AGENTS.md`

Do:
- add local docs for `apps/agent`
- update the root maps and quality-gate docs to include the agent app
- document the current build gate for the app

Do not:
- change runtime behavior
- invent release automation that does not exist yet

Definition of done:
- another engineer or agent can discover the app boundary, its expectations, and its validation command from repo docs alone
```

## Validation Matrix

Baseline checks for this plan's implementation chunks:

- `cd apps/agent && npm run build`
- `cd services/method-development && uv run pytest -q`
- focused recommendation tests under `services/method-development/tests/`
- `npm run agent:harness:check` when plan/docs files change

Note:

- as of drafting this plan, `agent:harness:check` is already blocked by a separate pre-existing plan file missing required frontmatter keys:
  - `docs/agents/plans/2026-04-20-open-access-live-extraction.md`

That unrelated doc issue should be cleared or explicitly accounted for when using harness status as a merge gate.

## Risks and Rollback Strategy

Risks:

- source-mode normalization can break the CLI or app if backward compatibility is handled carelessly
- moving local mode onto the recommendation contract can introduce ranking regressions if similarity primitives are not preserved
- unifying scaling can visibly change outputs that current demos rely on
- showing more trust metadata can overwhelm the app if surfaced without hierarchy
- impurity-aware ranking can become misleading if applied to weakly linked open-access chemistry

Rollback:

- keep `/retrieval/query` stable as a low-level fallback while the app migrates to the unified recommendation contract
- preserve legacy source-mode aliases during the migration window
- gate major ranking/scaling changes behind the G1 acceptance cases
- keep new trust payload fields additive until the app fully consumes them

## Decision Notes

- This round explicitly prioritizes **retrieval quality, scoring quality, and trust clarity** over new scientific ambition.
- The app should converge on one recommendation contract, not continue supporting parallel user-facing abstractions for local vs open-access.
- Open-access impurity support must be honest: if the chemistry linkage is weak, the UI must say so instead of implying confident mixture-aware ranking.
- Report/export polish is intentionally deferred unless it materially supports retrieval trust or handoff during one of the chunks above.

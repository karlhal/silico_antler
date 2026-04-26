# Agent App Implementation Status Report

As of 2026-04-22.

## Executive Summary

The current "agent app" is a **retrieval and recommendation MVP**, not the full autonomous HPLC method-development platform described in [`docs/AI HPLC Method Development Specification.md`](./AI%20HPLC%20Method%20Development%20Specification.md).

Today the implemented product splits into two layers:

- `apps/agent`: a standalone React + Vite interface with a staged "agent" workflow and report view.
- `services/method-development`: a FastAPI backend that provides retrieval, open-access paper discovery, text-first HPLC extraction, deterministic validation, review-record workflows, and a recommendation endpoint.

The most important product truth is:

- The **UI is real and builds successfully**.
- The **recommendation backend is real and tested** for its current retrieval/extraction/scoring path.
- The **full autonomous spec is not implemented**. The current system does not ship multimodal molecular extraction, surrogate ML, Bayesian optimization, or simulated chromatograms.
- Several features exist as **backend-only capability** or **prototype/stub wiring** that are not yet first-class in the app.

### Status Vocabulary

- `implemented in UI`: the user can exercise the feature from `apps/agent`.
- `implemented in backend only`: the backend supports it, but the app does not surface it.
- `prototype/stub`: partial wiring, dead-end flow, or placeholder surface.
- `documented but not implemented`: present in docs/roadmaps, contradicted by current code.
- `deferred from original spec`: explicitly outside the current MVP or still absent.

### Gap Vocabulary

- `UI gap`: backend exists, app does not expose it or exposes it incompletely.
- `backend gap`: app assumes behavior the backend does not fully provide.
- `doc gap`: repo docs do not match the current app/backend shape.
- `spec-deferred`: missing because the product intentionally stopped at a narrower MVP.

## Current Product Stance

The repo has already narrowed the original platform ambition into a staged retrieval-first product:

- The original spec describes an end-to-end agentic platform with multimodal extraction, physics-informed prediction, and optimization.
- [`docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`](./agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md) explicitly reframes the MVP as a **retrieval system first**, not a full autonomous method-development platform.
- [`docs/product/method-discovery-design.md`](./product/method-discovery-design.md) further refines the product around: "what worked for others on systems like yours?"
- [`docs/design-system-evolution-report.md`](./design-system-evolution-report.md) then layers a dedicated `apps/agent` interface on top of that narrower product.

In practice, the current app is best understood as:

1. collect system constraints and separation intent
2. choose a source path
3. either search a retrieval corpus or run open-access recommendation discovery
4. rank candidate methods
5. show a scaled recommendation report

That is materially useful, but it is still far short of the original autonomous platform.

## Architecture Path

### Runtime Path

The current app/runtime path is:

`apps/agent` -> Vite dev proxy -> `/api` on `localhost:8000` and `/method-dev` on `localhost:8001` -> backend routers

Current relevant files:

- UI shell and view composition: `apps/agent/src/pages/Dashboard.tsx`
- client-side workflow state: `apps/agent/src/hooks/useAgentWorkflow.ts`
- HTTP client: `apps/agent/src/lib/api.ts`
- type definitions: `apps/agent/src/types/index.ts`
- dev proxy: `apps/agent/vite.config.ts`
- method-development app wiring: `services/method-development/app/main.py`
- recommendation router: `services/method-development/app/recommendations_router.py`
- retrieval API: `services/method-development/app/main.py`

### Important Runtime Notes

- The app proxies `/method-dev/*` to the method-development service on port `8001` and rewrites the prefix away before hitting the FastAPI service.
- The app also proxies `/api/*` to `apps/api` on port `8000`.
- The current dashboard flow actively uses `/method-dev` for discovery/recommendation.
- The `/api` proxy is currently only relevant to a dormant `resolveSmilesName` helper in `apps/agent/src/lib/api.ts`; the dashboard does not call it.

### App Boundary Documentation Status

Core repo docs now treat `apps/agent` as a first-class boundary:

- `AGENTS.md` includes `apps/agent` in the instruction chain, monorepo map, task routing, and quality gates.
- `README.md` includes `apps/agent` in the repository structure and local-development guidance.
- `docs/architecture/repo-structure.md` and `docs/agents/architecture-boundaries.md` include the app boundary explicitly.
- `docs/agents/quality-gates.md` and `docs/agents/release-and-testing.md` document `cd apps/agent && npm run build` as the current validation gate.
- `apps/agent` now has local `README.md` and `AGENTS.md` files.

This closes the earlier repo-level discoverability gap. The remaining limitation is release maturity: the app has a documented build gate, but no dedicated release automation yet.

## Feature Inventory

| Feature | Original design intent | Current implementation | Where implemented | Status | Notes / gaps |
| --- | --- | --- | --- | --- | --- |
| Staged 5-step agent UI | Guided "agent" workflow from system context to evidence-backed recommendation | The UI runs a staged flow across system setup, target setup, source selection, discovery, and final report/failure states | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/hooks/useAgentWorkflow.ts` | `implemented in UI` | The phase model is real. The UI is a strong presentation layer over narrower backend capabilities. |
| System specification capture | Collect column, solvents, detectors, and lab constraints | UI captures manufacturer, chemistry, length, ID, particle size, solvents, detectors | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/types/index.ts` | `implemented in UI` | Good MVP coverage. `instrument_modes` and `max_pressure_bar` exist in backend schemas but are not surfaced in the app. `UI gap`. |
| Target capture | Capture request, analyte, matrix, SMILES, impurities, runtime, detection constraints | UI captures natural-language request, analyte name, target SMILES, impurity SMILES rows, matrix, max runtime, and MS requirement | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/types/index.ts` | `implemented in UI` | The app now exposes the chemistry-native inputs needed for local-corpus retrieval and impurity-aware ranking. `Other` matrix paths are also wired. |
| Source selection | Let user choose evidence source before discovery | UI offers `local_corpus` vs `open_access` and routes both through the recommendation contract | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/lib/api.ts` | `implemented in UI` | This is now a real recommendation-mode branch point. `local_files` remains a backend/operator mode and is not exposed in the app. |
| Open-access discovery | Query live literature, extract methods, rank recommendations | UI calls `POST /method-dev/recommendation/recommend`; backend now builds a request-aware search query, screens OpenAlex hits for method relevance, fetches HTML/PDF with fallback, ingests, extracts, scores, and returns candidates plus skip diagnostics | `apps/agent/src/lib/api.ts`, `services/method-development/app/recommendation_engine.py`, `services/method-development/app/open_access_client.py`, `services/method-development/app/recommendations_router.py` | `implemented in UI` | This remains the most complete end-to-end app path today. The remaining gap is richer UI surfacing of backend evidence and skip diagnostics. |
| Local repository retrieval | Search local/curated HPLC records for similar molecules | UI `local_corpus` mode calls `POST /method-dev/recommendation/recommend` with `source_mode="local_corpus"`; backend begins from retrieval-store matches and then applies recommendation scoring | `apps/agent/src/lib/api.ts`, `services/method-development/app/recommendation_engine.py`, `services/method-development/app/retrieval_store.py`, `services/method-development/app/milvus_retrieval_store.py` | `implemented in UI` | This is no longer a thin raw retrieval lookup. The remaining gap is trust surfacing, not access to the mode itself. |
| Recommendation ranking | Rank methods by fit to system, target, and practical constraints | Backend computes a multi-factor score: system match, analyte match, matrix fit, practical fit, extraction confidence, literature relevance; `local_corpus` now uses the same recommendation-grade shape instead of raw retrieval ordering | `services/method-development/app/recommendation_engine.py`, `services/method-development/app/recommendation_schemas.py` | `implemented in UI` | Local exact-match ties can now be broken by better system and practical fit. |
| Physics-based scaling | Scale literature methods to the user's hardware | One backend scaling utility now serves `open_access`, `local_files`, and `local_corpus`; the app renders scaled output, gradients, notes, and warnings without recomputing formulas | `services/method-development/app/method_scaling.py`, `services/method-development/app/recommendation_engine.py`, `services/method-development/app/recommendation_schemas.py`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/pages/Dashboard.tsx` | `implemented in UI` | The previous source-mode scaling mismatch has been removed. Remaining work is higher-fidelity modeling, not formula drift. |
| Provenance / evidence visibility | Show why the recommendation is trustworthy | Backend returns evidence-rich extraction objects, `match_rationale`, validation, and review summaries | `services/method-development/app/hplc_extraction_schemas.py`, `services/method-development/app/retrieval_store.py`, `services/method-development/app/main.py` | `implemented in backend only` | The UI currently shows citation, score, and rationale, but not raw evidence snippets, validation issues, `match_rationale`, or `review_summary`. `UI gap`. |
| Review records | Preserve extraction provenance and review state | Backend can create, list, fetch, approve, and explicitly promote/unpromote review records into the future local corpus | `services/method-development/app/review_records_router.py`, `services/method-development/app/review_record_store.py`, `services/method-development/app/review_record_materialization.py` | `implemented in backend only` | Not surfaced in `apps/agent`. |
| C12 orchestration | Wrap registration, extraction, review, and approval in one workflow | Backend exposes synchronous orchestration with bounded budgets and optional Gemini observer summary | `services/method-development/app/c12_orchestration.py`, `services/method-development/app/c12_orchestration_router.py` | `implemented in backend only` | No current UI path uses it. |
| Milvus-backed retrieval | Scale chemical similarity search beyond in-memory retrieval | `MilvusRetrievalStore` is present and is the default when `USE_MILVUS` is truthy; retrieval API and local-corpus recommendations can use it | `services/method-development/app/milvus_retrieval_store.py`, `services/method-development/app/main.py` | `implemented in backend only` | The scalable retrieval backend now applies the same mixture-aware aggregate scoring and rationale shape as the seeded in-memory store. |
| Demo data path | Provide one-click demo for fast product walkthroughs | `Quick Demo` seeds system specs plus visible target SMILES and impurity inputs | `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/pages/Dashboard.tsx` | `implemented in UI` | Still useful for operator demos, but local corpus mode no longer depends on hidden chemistry state. |
| Export behavior | Let user take the recommendation out of the app | The report view includes an `Export Package` button with no click handler | `apps/agent/src/pages/Dashboard.tsx` | `prototype/stub` | Presentational only. No exported artifact or backend integration exists. |
| SMILES input and resolution | Allow molecule-native queries and identity help | The dashboard now exposes target SMILES plus on-demand name resolution; the API client calls `/api/v1/chemistry/smiles/resolve-name` | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/lib/api.ts`, `apps/api/app/main.py` | `implemented in UI` | Resolution is optional UX help, not a hard dependency for running discovery. |
| Impurity handling | Support target + impurity ranking and mixture-aware retrieval | The app sends impurity SMILES into recommendation requests, the report labels whether ranking was mixture-aware or target-only, `local_corpus` uses explicit target + impurity contributions, and open-access runs fall back honestly when impurity linkage is not trustworthy | `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `services/method-development/app/recommendation_engine.py`, `services/method-development/app/recommendation_schemas.py`, `services/method-development/app/retrieval_store.py`, `services/method-development/app/milvus_retrieval_store.py` | `implemented in UI` | Trustworthy impurity-aware behavior is now explicit and end-to-end for `local_corpus`; open-access remains intentionally target-focused until entity linkage is strong enough to justify impurity scoring. |
| Chromatogram simulation | Show simulated chromatograms and predicted separation quality | No chromatogram simulation exists in the current app or backend | n/a | `deferred from original spec` | The original spec calls for simulated chromatograms; current MVP stops at ranked/scaled methods. |
| Surrogate ML / Bayesian optimization | Predict novel methods and optimize gradients | No XGraphBoost/PINN/LSS/Bayesian optimization implementation exists | n/a | `deferred from original spec` | Explicitly outside the retrieval-first MVP. |
| Multimodal figure / R-group extraction | Extract molecules and substitutions from figures/tables | No implemented image-to-structure or R-group reconstruction path is present in the current product surface | n/a | `deferred from original spec` | The extraction stack is text-first; the MVP plan explicitly deferred these deeper multimodal features. |

## Detailed Subsystem Notes

### 1. UI Workflow and State Machine

The agent app is a well-defined UI shell with real product logic, not just a mockup.

Key implementation points:

- `useAgentWorkflow()` in `apps/agent/src/hooks/useAgentWorkflow.ts` owns the workflow state.
- The hook defines the initial research timeline:
  - query papers
  - extract methods
  - match system constraints
  - apply physics scaling
  - final rank
- The dashboard renders those states through a cinematic deck/report layout in `apps/agent/src/pages/Dashboard.tsx`.
- `loadDemoData()` pre-fills a realistic caffeine/theobromine/paracetamol demo, including the same visible target-SMILES and impurity fields a user can now enter manually.

What is fully implemented in the UI:

- staged navigation from system -> target -> source
- open-access vs local branch selection
- discovery progress states
- failure state and retry flow
- ranked recommendation report
- scaled-method side panel

What is only partially implemented in the UI:

- the UI still does not expose backend evidence snippets, validation issues, `match_rationale`, or `review_summary`
- `local_files` remains backend-only and is not offered in the source picker
- `resolveSmilesName()` is now wired for target and impurity UX help, but chemistry resolution is still optional rather than integrated into a richer molecule workflow
- `orchestrateDiscovery()` is a simulated stub in the API client and unused by the dashboard
- `Export Package` is a dead button

This makes the app **strong as a guided UI**, but still **partial as a chemistry-native operator tool**.

### 2. Source Mode Split: Two Different Products Behind One Toggle

The `local` and `open_access` branches do not point to the same backend workflow.

#### `open_access`

`open_access` calls:

- `POST /method-dev/recommendation/recommend`

This backend path:

1. builds a search query
2. oversamples OpenAlex candidates and screens them for analyte, matrix, and chromatography relevance
3. fetches HTML first, then falls back to PDF when the landing page is blocked, thin, or unavailable
4. ingests and text-extracts the paper
5. skips extraction failures explicitly instead of failing the whole search
6. scores candidate methods against the request
7. returns ranked candidates plus scaled output and per-paper skip diagnostics

This is the most coherent "agent" behavior in the current product.

#### `local_corpus`

`local_corpus` now calls:

- `POST /method-dev/recommendation/recommend`

This backend path:

1. queries the retrieval corpus for the target SMILES plus optional impurities
2. converts the matched retrieval records into recommendation candidates
3. applies recommendation scoring over system, analyte, matrix, practical, confidence, and literature signals
4. applies the shared backend scaling engine
5. returns the same report shape used by open-access mode

That means:

- the app's local mode is now a real recommendation path, not a raw retrieval-only surface
- it still depends on a valid `targetSmiles`
- the UI now collects that input directly
- it is still distinct from the backend's file-based `local_files` mode, which remains operator-only

So the "Local Repository" card in the app and the "local" recommendation backend mode are currently different concepts with the same label. That is one of the most important implementation mismatches in the current product.

### 3. Recommendation Backend

The recommendation backend is narrower than the original spec, but it is not trivial. It has a real deterministic pipeline.

Current path in `services/method-development/app/recommendation_engine.py`:

1. build a search query from request text + analyte + matrix + HPLC vs LC-MS/MS phrasing
2. fetch local source artifacts or OpenAlex candidates
3. ingest HTML or PDF
4. call `extract_minimal_hplc()`
5. score the extracted method
6. scale the method for the user's system
7. return a ranked `MethodRecommendationReport`

Current score dimensions:

- system match
- analyte match
- matrix fit
- practical fit
- extraction confidence
- literature relevance

This is materially aligned with [`docs/product/method-discovery-design.md`](./product/method-discovery-design.md), which explicitly reframes the product around system fit, analyte fit, matrix fit, and practical fit.

Important implementation notes:

- `open_access_client.py` prefers HTML landing pages over PDFs when possible.
- `recommendation_schemas.py` defines a clear request/report contract for the recommendation loop.
- The recommendation route comment in `recommendations_router.py` says the path uses "OpenAlex and Gemini," but the current `recommend_methods()` implementation uses **OpenAlex + deterministic extraction/scoring**, not Gemini. That is a `doc gap`.

### 4. Scaling Logic Is Now Canonical

The current product now uses one user-facing scaling implementation across recommendation modes.

#### Backend scaling utility

In `services/method-development/app/method_scaling.py`:

- flow scales with column ID squared
- runtime scales with column length ratio when runtime is available
- gradient point times scale with column length ratio when a gradient exists
- injection volume scales with approximate column volume using a documented default source injection assumption
- scaling notes explain what changed
- scaling warnings call out missing runtime details or particle-size backpressure risk

#### App rendering behavior

In `apps/agent/src/hooks/useAgentWorkflow.ts` and `apps/agent/src/pages/Dashboard.tsx`:

- the app no longer computes source-mode-specific scaling formulas
- the app renders the backend `recommended_method` payload directly
- gradient steps, scaling notes, and scaling warnings are displayed when present

That resolves the earlier split-brain scaling mismatch. The remaining gap is not consistency; it is the limited physical sophistication of the current heuristic scaler compared with the original spec's future modeling ambitions.

### 5. Retrieval, Validation, Review, and Orchestration Are Mostly Backend-Only

The method-development service is further along than the app UI suggests.

Backend capabilities already present:

- retrieval schema and corpus search
- approved and promoted review-backed records
- text-first HPLC extraction
- validation heuristics on record drafts
- review-record creation, listing, fetching, approval, and corpus promotion
- C12 orchestration over registration -> extraction -> review -> optional approval
- optional Gemini observer summary on top of deterministic orchestration

Key endpoints:

- `POST /recommendation/recommend`
- `POST /retrieval/query`
- `POST /source-documents/`
- `GET /source-documents/{source_document_id}`
- `POST /source-documents/{source_document_id}/extract-hplc`
- `POST /source-documents/{source_document_id}/review-records`
- `GET /review-records`
- `GET /review-records/{review_record_id}`
- `POST /review-records/{review_record_id}/status`
- `POST /review-records/{review_record_id}/promotion`
- `POST /c12/review-records/orchestrate`

These are important because they show where the product is headed:

- the backend already contains a reviewable extraction/approval model
- the UI currently skips all of that and presents only the final recommendation slice

So the backend is ahead of the app in scientific workflow depth.

## Spec Mapping Against the Original HPLC Specification

| Spec phase | Original design intent | Current state | Assessment |
| --- | --- | --- | --- |
| Agentic literature extraction pipeline | Planner/observer/specialist agent DAG over multimodal scientific literature | Current extraction is text-first and deterministic. C12 orchestration exists, but it is synchronous and bounded, not a rich planner/worker DAG. | `partially implemented`, but only as a narrow deterministic backend slice. |
| Entity resolution | Map molecules, aliases, and retention times reliably to the right compounds | Local-identifier anchoring and molecular-entity drafts exist in extraction schemas and backend notes, but full SMILES linkage remains incomplete. | `implemented in backend only` for heuristic anchoring; not complete versus the spec. |
| Validation agent | Hard physical/chemical constraints reject bad methods | Deterministic validation exists for flow/pressure risk, pH compatibility, duplicate retention conflicts, unresolved entities, and generic anchors | `implemented in backend only` as an MVP heuristic validator, not the full spec's chemical conscience. |
| Retrieval / vector search | Search a large corpus of agent-extracted historical methods by chemistry similarity | Retrieval API exists; seeded corpus exists; Milvus backend exists; promoted review-backed records re-enter the corpus; the app now uses this through `local_corpus` recommendation mode | `implemented in backend` and `implemented in UI` for the retrieval-first MVP surface. |
| Physics-informed scaling or modeling | Use rigorous physical scaling and later ML/PINN/LSS models to predict behavior | Practical deterministic scaling now runs from one canonical backend utility; no PINN, no XGraphBoost, no LSS coefficient prediction | Scaling is `implemented in backend/UI render-only`; predictive modeling is `deferred from original spec`. |
| Optimization / chromatogram output | Mutate gradients, optimize separation, and render simulated chromatograms | No optimization engine or chromatogram simulation is currently present | `deferred from original spec`. |
| Final user-facing recommendations | Provide ranked, evidence-backed methods fitted to the user's system | The app does this today for both open-access and local-corpus recommendation modes, but evidence/review detail is still only partially surfaced in the UI | `implemented in UI`, but only for retrieval/recommendation MVP scope. |

### Overall Spec Alignment

The product is best described as:

- **well aligned with the retrieval-first reinterpretation of the spec**
- **partially aligned with the original literature-extraction architecture**
- **not yet aligned with the original predictive/optimization half of the spec**

## Interfaces Consumed by the App

### UI-Consumed Today

#### `POST /method-dev/recommendation/recommend`

Purpose:

- run the higher-level recommendation loop over `open_access` or `local_corpus`

Current app use:

- called by both source cards in `useAgentWorkflow()`
- app sends request text, analyte name, target SMILES, impurity SMILES, matrix, system specs, MS requirement, and max runtime
- app sets `source_mode` to either `open_access` or `local_corpus`

Important nuance:

- the backend also supports `local_files`, but the app does not expose that operator-oriented mode
- local-corpus recommendations now start from retrieval matches and then flow through the same recommendation/scaling contract as open-access results

#### Vite proxy behavior

Defined in `apps/agent/vite.config.ts`:

- `/api` -> `http://localhost:8000`
- `/method-dev` -> `http://localhost:8001`, rewritten before request dispatch

Important nuance:

- `package.json` runs `vite --port 4175`, while `vite.config.ts` sets `server.port = 5175`
- the CLI flag wins in local development, so the effective dev server port is `4175`

### Backend Capability Present but Not Wired Into the App

#### `POST /method-dev/retrieval/query`

Purpose:

- search the retrieval corpus directly for a target SMILES plus optional impurities

Current app use:

- not called by the app anymore

Important nuance:

- this remains a useful lower-level backend contract for testing, debugging, and corpus inspection
- local-corpus recommendation mode now consumes retrieval indirectly through the recommendation engine instead of calling this route from the UI
- this is not a runtime bug, but it is a distinction the docs need to keep explicit

### Backend Capability Available but Not Wired Into the App

- `POST /source-documents/{source_document_id}/extract-hplc`
- review-record lifecycle endpoints
- `POST /c12/review-records/orchestrate`

These interfaces matter because they represent the actual scientific-workflow backbone behind the retrieval MVP, even though the app currently jumps directly to a simpler recommendation/report experience.

## Documentation Gaps and Mismatches

### Repo-Level Doc Status

The earlier repo-level doc gap around `apps/agent` boundary discovery is now closed:

1. `apps/agent` appears in the root repo maps and architecture docs.
2. The current quality gate is documented as `cd apps/agent && npm run build`.
3. Local `apps/agent/README.md` and `apps/agent/AGENTS.md` now exist.

### Code vs Doc Mismatches

1. [`docs/design-system-evolution-report.md`](./design-system-evolution-report.md) says "Other..." logic was added to all dropdowns for custom professional inputs.
   - Current code includes `Other` values and custom type fields.
   - Current UI does **not** render the actual custom-entry controls.
   - Classification: `documented but not implemented`.

2. `services/method-development/app/recommendations_router.py` says the recommendation path executes "OpenAlex and Gemini."
   - Current code uses OpenAlex plus deterministic extraction/scoring.
   - Gemini is used on the C12 observer branch, not on the recommendation path.
   - Classification: `doc gap`.

3. The app presents `local_corpus` and `open_access` as parallel source choices.
   - both map to the recommendation engine
   - `local_files` still exists only as a backend/CLI mode
   - Classification: `doc gap` because several earlier docs still describe the pre-G2 contract split.

4. The app appears to support chemistry-native querying through types and client helpers.
   - `targetSmiles`, impurity inputs, and `resolveSmilesName` now exist in the live dashboard.
   - Open-access ranking still does not deeply use impurity-aware reasoning.
   - Classification: `implemented in UI` with a remaining `backend gap` for non-local-corpus impurity logic.

5. The app exposes one report CTA:
   - `Export Package`
   - It is currently inert.
   - Classification: `prototype/stub`.

### Architecture Mismatch Worth Watching

The biggest remaining implementation mismatch is now trust surfacing rather than ranking or scaling:

- the backend recommendation payload can explain retrieval rationale, review state, validation posture, and evidence
- the app currently shows a much thinner surface: title, citation, score, rationale, and scaled-method details

This is now a product legibility gap more than a scientific-computation gap.

## What Is Shippable Now

### Credibly Shippable

- the standalone `apps/agent` interface itself
- the staged UI workflow
- the open-access recommendation path
- ranked recommendation display
- scaled-method presentation
- the backend retrieval/recommendation/extraction foundation

### Shippable with Clear Caveats

- local-corpus recommendation mode, but without full evidence and review-state surfacing in the UI
- Milvus-backed retrieval, but only as backend infrastructure rather than a visible product capability

### Not Yet Shippable as Claimed in the Original Spec

- autonomous multimodal agentic literature extraction
- figure-to-structure and R-group extraction
- full provenance/review workflows in the app
- chromatogram simulation
- surrogate ML prediction and optimization

## Verification Appendix

Verification run for this report:

- `cd /Users/nick/silico_website/silico/apps/agent && npm run build`
  - result: passed
  - note: Vite emitted deprecation warnings about `esbuild` / `optimizeDeps.esbuildOptions` coming from the React plugin, but the production build completed successfully

- `cd /Users/nick/silico_website/silico/services/method-development && uv run pytest -q tests/test_recommendation_engine.py tests/test_open_access_client.py tests/test_recommendation_cli.py`
  - result: `7 passed`

These checks support the report's claims that:

- the agent UI currently builds
- the recommendation/open-access/CLI backend slice is passing in the service boundary

## Source Notes

Primary code sources reviewed:

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/lib/api.ts`
- `apps/agent/src/types/index.ts`
- `apps/agent/vite.config.ts`
- `services/method-development/app/main.py`
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/open_access_client.py`
- `services/method-development/app/retrieval_store.py`
- `services/method-development/app/milvus_retrieval_store.py`
- `services/method-development/app/hplc_extraction_schemas.py`
- `services/method-development/app/hplc_record_validation.py`
- `services/method-development/app/review_records_router.py`
- `services/method-development/app/c12_orchestration.py`
- `services/method-development/app/c12_orchestration_router.py`
- `services/method-development/app/source_documents_router.py`
- `apps/api/app/main.py`

Primary documentation sources reviewed:

- `docs/AI HPLC Method Development Specification.md`
- `docs/product/method-discovery-design.md`
- `docs/design-system-evolution-report.md`
- `docs/method-development-implementation-report.md`
- `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- `docs/agents/plans/2026-04-18-hplc-retrieval-session-summary.md`
- `docs/agents/plans/2026-04-19-c12-orchestration-first-slice.md`
- `AGENTS.md`
- `README.md`
- `docs/architecture/repo-structure.md`
- `docs/agents/architecture-boundaries.md`
- `docs/agents/quality-gates.md`
- `docs/agents/release-and-testing.md`

---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent services/method-development apps/api product UX planning
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ../architecture-boundaries.md
  - ../quality-gates.md
  - ../../apps/agent/README.md
  - ../../services/method-development/README.md
---

# Agent Life Science Capability Integration Plan

## Goal and Success Criteria

Bring the useful parts of Codex's life-science research skills into the Silico agent as product capabilities for HPLC method recommendation, without copying Codex skill files or binding the app to Codex-only tooling.

Success means:

- analyte and impurity entities are normalized against public chemistry sources before recommendation search
- recommendation reports expose compound context, source provenance, and lookup caveats
- open-access literature search uses normalized names, synonyms, and identifiers when available
- skipped, failed, or low-confidence external lookups are visible in backend diagnostics and frontend UI
- `apps/agent` continues to consume `services/method-development` and `apps/api` only through HTTP contracts
- public-source connectors are typed, tested, timeout-bounded, and do not silently change ranking behavior

## Scope

This plan covers a first production-oriented slice:

- public chemistry context for target analyte and impurities
- recommendation search-query enrichment from normalized compound context
- response contract additions for compound context and external evidence diagnostics
- frontend report surfaces for compound intelligence and source-search trace

Primary implementation areas:

- `services/method-development`: owns recommendation-time orchestration, public-source clients, schema additions, tests, and diagnostics
- `apps/agent`: renders the new contract fields and degraded states
- `apps/api`: remains the existing SMILES-name lookup service unless a later decision moves that capability into `services/method-development`

## Explicit Non-Goals

- no direct copying of Codex plugin skill files into runtime application code
- no product dependency on Codex MCP tools, subagents, or local plugin cache paths
- no broad biology assistant in the HPLC agent
- no genetics, clinical-trials, omics, or protein-structure workflows in this first slice
- no direct source imports across app/service boundaries
- no hidden ranking boost from external sources without surfaced rationale and tests
- no credentialed, paywalled, or terms-sensitive scraping

## Current State

The product already has related foundations:

- `apps/agent/src/lib/api.ts` calls `/method-dev/recommendation/*` and `/api/v1/chemistry/smiles/resolve`
- `apps/agent/src/types/index.ts` models recommendation trust, retrieval rationale, source documents, and scaled methods
- `services/method-development/app/open_access_client.py` searches OpenAlex, ranks open-access locations, and fetches source artifacts
- `services/method-development/app/recommendation_engine.py` screens open-access candidates, extracts methods, ranks recommendations, and surfaces skipped work through runtime diagnostics
- `apps/api/app/smiles_lookup.py` already resolves SMILES names through PubChem

The gap is that compound normalization is not yet a first-class recommendation artifact, and open-access search does not yet use a structured compound-context layer that the UI can inspect.

## Decision-Complete Implementation Approach

### Product Decision

Translate Codex life-science skills into Silico-specific capabilities, not copied skills.

The agent should feel like it has chemistry-aware research tools because the backend performs deterministic, typed lookups and exposes what happened. It should not embed generic life-science skill prompts in the frontend or backend.

### Capability Boundary

Create a small capability layer in `services/method-development`:

- `compound_context_client.py`: public-source lookups for compound identity and metadata
- `compound_context_schemas.py`: typed source records, warnings, and normalized compound context
- `compound_context.py`: orchestration and merge policy across available lookup sources

Initial sources:

- PubChem PUG REST for name, synonyms, formula, exact/average mass, CID, and canonical identifiers
- optional ChEMBL search for `chembl_id` and coarse molecule metadata only if it can be implemented with bounded latency and useful diagnostics

Keep source clients independent and testable. The orchestrator owns merging, truncation, and warnings.

### Backend Contract Additions

Extend recommendation schemas with:

- `CompoundContext`
  - `input_label`
  - `input_smiles`
  - `resolved_name`
  - `canonical_smiles`
  - `source_ids`
  - `formula`
  - `molecular_weight`
  - `synonyms`
  - `lookup_sources`
  - `warnings`
  - `confidence`
- `ExternalEvidenceTrace`
  - `query_terms_used`
  - `source_clients_attempted`
  - `source_clients_succeeded`
  - `source_clients_failed`
  - `truncation_warnings`
  - `skipped_reason_counts`

Add these fields to `MethodRecommendationReport` as optional additive fields so existing consumers remain compatible:

- `target_compound_context?: CompoundContext | null`
- `impurity_compound_contexts?: CompoundContext[]`
- `external_evidence_trace?: ExternalEvidenceTrace | null`

### Recommendation Flow Changes

Phase 1: normalize compounds before search.

- Build compound context from `analyte_name`, `target_smiles`, and `impurity_smiles`.
- Prefer user-provided names and SMILES as authoritative inputs.
- Never overwrite a user-visible analyte label without preserving the original input.
- Timebox external lookups and surface timeout warnings.

Phase 2: enrich open-access search.

- Generate search terms from resolved name, high-confidence synonyms, matrix, detector, and HPLC-specific terms.
- Keep existing OpenAlex client and screening pipeline.
- Record the exact query terms used in `external_evidence_trace`.
- Avoid broad synonym expansion when it would create noisy searches; cap synonyms and expose truncation.

Phase 3: expose context to ranking without hiding behavior.

- Use normalized context only for retrieval/search enrichment in the first implementation.
- Do not add ranking boosts until there are tests proving better behavior.
- If ranking later uses compound context, add score-breakdown fields and UI rationale.

### Frontend UX Additions

Add report surfaces in `apps/agent`:

- Compound intelligence panel:
  - target name, formula, molecular weight, key synonyms, source badges
  - impurity context list when impurities were supplied
  - warning states for ambiguous, missing, timeout, or partial lookups
- Source search trace:
  - query terms used
  - public sources attempted
  - skipped or failed source counts
  - clear distinction between recommendation evidence and auxiliary compound metadata

Keep the UI sober and inspectable. This is evidence and trust presentation, not a separate life-science chatbot.

## Implementation Phases

### Phase 0: Contract Design

- Add schema types in `services/method-development`.
- Mirror TypeScript types in `apps/agent/src/types/index.ts`.
- Add representative JSON fixtures for reports with full, partial, and failed compound context.
- Decide whether PubChem lookup stays shared through `apps/api` or is duplicated as a method-development client.

Preferred decision: implement recommendation-time PubChem lookups inside `services/method-development` to avoid coupling the method-development backend to `apps/api` during recommendation runs. Keep `apps/api` SMILES resolution for interactive app typing.

### Phase 1: PubChem Compound Context

- Implement bounded PubChem PUG REST client with explicit timeouts.
- Resolve by SMILES when available; fall back to name when only analyte text is available.
- Return compact metadata only.
- Add tests for success, not found, timeout/error, malformed payload, and truncation.

### Phase 2: Recommendation Integration

- Invoke compound context orchestration in recommendation flow before open-access planning.
- Feed selected names/synonyms into search-query planning.
- Add trace fields showing which terms were used and which were rejected.
- Preserve current behavior when lookups fail.

### Phase 3: Agent Report UI

- Add optional rendering for compound context and evidence trace.
- Make degraded states explicit in the report.
- Keep existing report behavior unchanged when new fields are absent.

### Phase 4: Optional ChEMBL Slice

- Add ChEMBL molecule search only if PubChem context is stable.
- Treat ChEMBL as auxiliary metadata, not primary identity resolution.
- Expose ChEMBL failures separately from PubChem failures.

### Phase 5: Evaluation and Tuning

- Create test cases comparing old vs enriched search queries for common HPLC analytes.
- Confirm the enrichment improves candidate relevance without suppressing usable open-access sources.
- Add diagnostics for cases where synonym expansion increases noise.

## Validation Matrix

Documentation-only plan creation:

- `npm run agent:harness:check`

Backend implementation:

- `cd services/method-development && uv run pytest -q`
- targeted tests for compound context client/orchestrator and recommendation schema serialization

Frontend implementation:

- `cd apps/agent && npm run build`
- UI smoke check with reports containing full, partial, and missing compound context

Cross-boundary contract changes:

- method-development tests
- agent build
- update `apps/agent/README.md` or service docs if new response fields or env settings become user-facing

## Risks and Rollback Strategy

Risk: public-source lookups add latency to recommendation runs.

Mitigation:

- use short per-source timeouts
- make lookup failures non-fatal
- include trace warnings
- preserve current search behavior when context is unavailable

Risk: synonym expansion makes open-access search noisier.

Mitigation:

- cap synonyms
- prefer exact resolved names and HPLC-specific terms
- record accepted and rejected query terms
- keep ranking logic unchanged in the first slice

Risk: UI users confuse auxiliary compound metadata with direct method evidence.

Mitigation:

- label compound context separately from recommendation evidence
- keep source badges and warnings visible
- avoid implying method validity from metadata-only sources

Risk: duplicating PubChem lookup creates drift with `apps/api`.

Mitigation:

- keep both clients small and source-specific
- document ownership: app typing resolution stays in `apps/api`; recommendation-time evidence context lives in `services/method-development`
- consider later consolidation only through a stable HTTP contract or shared neutral package

Rollback:

- keep response fields additive and optional
- gate compound-context lookup behind a service setting if latency or quality is unacceptable
- disable query enrichment while preserving report rendering for stored responses

## Decision Notes

- 2026-04-23: do not copy Codex life-science skill files into the app; translate the useful public-source lookup behaviors into product-owned backend code
- 2026-04-23: first slice is chemistry and literature-search support for HPLC, not a general life-science research assistant
- 2026-04-23: recommendation-time compound context belongs in `services/method-development`; interactive SMILES-name typing can remain in `apps/api`
- 2026-04-23: compound context may enrich search queries initially, but should not affect ranking scores until tested and surfaced in score rationale
- 2026-04-23: implemented the PubChem compound-context slice through `services/method-development`, additive report fields, open-access query enrichment, and `apps/agent` report rendering; optional ChEMBL and broader evaluation/tuning remain future work

## Verification Evidence

- 2026-04-23: `cd services/method-development && uv run pytest -q` passed: 162 tests, 1 third-party deprecation warning.
- 2026-04-23: `cd apps/agent && npm run build` passed with existing Vite chunk-size/deprecation warnings.
- 2026-04-23: `npm run agent:harness:check` passed after implementation notes were added.

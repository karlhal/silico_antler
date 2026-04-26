---
status: active
owner: platform
last_verified: 2026-04-19
last_updated: 2026-04-19
applies_to: services/method-development retrieval MVP
source_of_truth: docs/agents/execution-plans.md
source_spec: ../../AI HPLC Method Development Specification.md
---

# HPLC Retrieval MVP Chunk Plan

## Goal and Success Criteria

Build the first useful slice of the HPLC product as a retrieval system, not a full autonomous method-development platform.

Success means the product can:

- accept a target SMILES and optional impurity SMILES
- normalize the chemistry inputs reliably
- search a corpus of structured historical HPLC method records
- rank the most relevant prior methods
- return enough evidence and provenance for a human scientist to use the output as a starting point

## Provenance Requirement

Every retrieved method record should carry source traceability.

Minimum expectation:

- source document identity
- source type such as PDF, HTML, manual, or seeded
- page numbers where extraction evidence came from when available
- short evidence snippets showing the supporting text

This starts at the schema layer in C1, should be captured during ingestion and extraction, and should be surfaced in retrieval responses by the time C4 and C9 are complete.

## Scope

This plan covers the retrieval-first MVP described by `docs/AI HPLC Method Development Specification.md`, split into prompt-sized implementation chunks.

Primary implementation home:

- `services/method-development` for hosted retrieval APIs, retrieval schemas, corpus storage, and ingestion/extraction entrypoints

Secondary future integration point:

- `apps/sidecar` only later, if desktop needs a remote-provider path or a local/offline retrieval mode

## Current Status

- Repo boundary created at `services/method-development`
- C1 is implemented in `services/method-development/app/retrieval_schemas.py`
- C2 is implemented in `services/method-development/app/chemistry.py`
- C3 is implemented in `services/method-development/app/retrieval_store.py`
- C4 is implemented in `services/method-development/app/main.py`
- Service skeleton exists in `services/method-development/app/main.py`
- C1 tests exist in `services/method-development/tests/test_retrieval_schemas.py`
- C2 tests exist in `services/method-development/tests/test_chemistry.py`
- C3 tests exist in `services/method-development/tests/test_retrieval_store.py`
- C4 tests exist in `services/method-development/tests/test_retrieval_api.py`
- Service smoke tests exist in `services/method-development/tests/test_service.py`
- Validation completed:
  - `cd services/method-development && uv run pytest -q` -> 27 passed
  - `cd apps/api && uv run pytest -q` -> 20 passed
  - `npm run agent:harness:check` -> passed
- External framework evaluation written at `docs/agents/plans/2026-04-18-chemical-extraction-framework-evaluation.md`

## Explicit Non-Goals

Do not treat these as first-pass tasks:

- full multimodal agent orchestration
- image-to-structure extraction from figures
- R-group reconstruction from structure tables
- full enterprise ASM interoperability
- Milvus-specific production vector infrastructure
- surrogate ML / XGraphBoost implementation
- PINN / LSS physics layer
- Bayesian optimization of gradients
- simulated chromatogram UI
- simultaneous RP-LC and HILIC support in the first implementation
- wholesale adoption or forking of LoA or ChemEAGLE as the product base

The first version should answer:

"What historically similar methods exist, and what conditions did they use?"

It should not yet answer:

"What is the globally optimal novel method for this mixture?"

## Decision-Complete Implementation Approach

### Product Stance

The retrieval MVP is intentionally staged:

1. make retrieval useful with manually seeded or curated records
2. add ingestion and extraction afterward
3. add provenance and validation before claiming strong reliability
4. only later add agentic orchestration
5. only after enough validated data exists, explore ML prediction

### External Framework Stance

Based on `docs/agents/plans/2026-04-18-chemical-extraction-framework-evaluation.md`:

- do not adopt or fork `LoA` or `ChemEAGLE` as the product foundation
- keep the product core bespoke in `services/method-development`
- borrow selected patterns only

Concrete implications for this plan:

- C2-C4 remain fully bespoke service code
- C5-C6 should borrow LoA-style ideas such as schema-driven extraction jobs, resumability, local-doc processing, and explicit verification passes
- C8 should remain deterministic and rules-based, not LLM-truth-based
- C12 should borrow ChemEAGLE-style planner / specialist / observer structure only after the deterministic extraction modules already exist and are tested

### Why `services/method-development` Goes First

- retrieval, ingestion, extraction, and validation form a separate scientific backend boundary from the public API
- `apps/api` remains focused on presets, showcase, contact, analytics, and lightweight public endpoints
- `apps/sidecar` already contains local chemistry/inference foundations, but retrieval should not depend on the private local runtime
- remote retrieval can later be consumed by desktop through sidecar/provider integration without collapsing service boundaries

### Dependency Backbone

The chunks depend on each other in this order:

1. domain schema
2. chemistry normalization and fingerprints
3. retrieval storage and search
4. retrieval API
5. source document registration and raw text extraction
6. text-native HPLC extraction
7. entity anchoring
8. validation
9. provenance and reviewability
10. mixture-aware ranking
11. expanded extraction coverage
12. optional agentic orchestration

Retrieval becomes valuable by chunk 4. Extraction automation begins at chunk 5. Trust and quality hardening happen in chunks 8 and 9.

## Chunk Registry

| Chunk | Status | Name | Primary Boundary | Depends On | Outcome |
| --- | --- | --- | --- | --- | --- |
| C1 | Implemented | Retrieval Domain Schema | `services/method-development` | none | Stable HPLC retrieval contract |
| C2 | Implemented | Chemistry Normalization Utilities | `services/method-development` | C1 | Canonical SMILES + fingerprints |
| C3 | Implemented | Seeded Retrieval Store | `services/method-development` | C1, C2 | Searchable curated method corpus |
| C4 | Implemented | Retrieval Query API | `services/method-development` | C3 | HTTP endpoint for ranked retrieval |
| C5 | Implemented | Source Document Registry | `services/method-development` | C1 | Register and read PDFs/HTML into raw text |
| C6 | Implemented | Minimal Text HPLC Extraction | `services/method-development` | C5 | First structured records from easy documents |
| C7 | Implemented | Entity Anchoring | `services/method-development` | C6 | Link identifiers, molecules, and retention times |
| C8 | Implemented | Validation Layer | `services/method-development` | C6, C7 | Reject implausible or malformed records |
| C9 | In Progress | Provenance and Reviewability | `services/method-development` | C8 | Evidence-backed retrieval records |
| C10 | Implemented | Mixture-Aware Ranking | `services/method-development` | C4, C8, C9 | Rank methods for target + impurity sets |
| C11 | In Progress | Extraction Coverage Expansion | `services/method-development` | C8 | Better tables, OCR, supplements |
| C12 | In Progress | Agentic Orchestration Layer | `services/method-development` | C6-C11 | Planner/retry loop over extraction steps |

## Recommended Execution Order

### C1 - Retrieval Domain Schema

Status:

- implemented

Purpose:

- define the stable record shape before any extraction or retrieval code exists

Deliverables:

- Pydantic models for source documents, molecular entities, chromatography system, method parameters, gradient profile, provenance, and validation state
- a reduced MVP schema inspired by the full spec, not the full spec itself
- clear required vs optional fields

Likely files:

- `services/method-development/app/schemas.py` or `services/method-development/app/retrieval_schemas.py`
- `services/method-development/tests/test_retrieval_schemas.py`

Non-goals:

- no endpoint yet
- no extraction logic yet
- no vector DB work yet

Validation:

- unit tests for schema validation and bounds
- implemented files:
  - `services/method-development/app/retrieval_schemas.py`
  - `services/method-development/tests/test_retrieval_schemas.py`
  - `services/method-development/tests/test_service.py`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 8 passed

Completion signal:

- later chunks can store and return a method record without inventing fields ad hoc

Prompt to use later:

```text
Implement Chunk C1 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Build the retrieval domain schema for the HPLC retrieval MVP in `services/method-development`.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- Existing service entrypoint: `services/method-development/app/main.py`
- Existing retrieval schema module: `services/method-development/app/retrieval_schemas.py`

Do:
- add a reduced-but-stable set of Pydantic models for retrieval records
- model source document metadata, molecule entries, chromatography system, method parameters, gradient points, provenance, and validation state
- keep fields aligned with retrieval MVP needs, not the full future ML platform
- add focused tests for bounds and validation behavior

Do not:
- add endpoints
- add extraction logic
- add storage or search
- add surrogate-model fields

Definition of done:
- the schema is concrete enough for storage and API responses in later chunks
- tests cover required fields and validation failures
```

### C2 - Chemistry Normalization Utilities

Status:

- implemented

Purpose:

- create a trustworthy chemistry identity layer before ranking or indexing anything

Deliverables:

- canonical SMILES normalization
- invalid SMILES handling
- Morgan/ECFP fingerprint generation
- small helper functions for future ranking and filters

Likely files:

- new `services/method-development/app/chemistry.py`
- `services/method-development/pyproject.toml` if chemistry dependencies are added
- new chemistry-focused tests in `services/method-development/tests/`

Non-goals:

- no retrieval endpoint yet
- no document extraction yet
- no descriptor-heavy ML work

Validation:

- tests for valid/invalid SMILES
- deterministic fingerprint generation
- implemented files:
  - `services/method-development/app/chemistry.py`
  - `services/method-development/tests/test_chemistry.py`
  - `services/method-development/pyproject.toml`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 16 passed

Completion signal:

- any future chunk can convert user SMILES into a stable normalized representation and comparable fingerprint

Prompt to use later:

```text
Implement Chunk C2 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add chemistry normalization utilities for the retrieval MVP in `services/method-development`.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- Reuse existing service conventions in `services/method-development/app/`

Do:
- add utilities for canonical SMILES normalization
- generate deterministic Morgan/ECFP fingerprints
- return explicit errors for invalid SMILES
- add unit tests for valid and invalid inputs

Do not:
- add retrieval storage
- add endpoints
- add extraction or ML code

Definition of done:
- later chunks can call one module to normalize query molecules and build similarity-ready fingerprints
```

### C3 - Seeded Retrieval Store

Status:

- implemented

Purpose:

- prove retrieval value before building extraction automation

Deliverables:

- a small curated store of structured method records
- storage and load path for those records
- Tanimoto-based similarity ranking against target molecules
- return top matching method records

Likely files:

- new retrieval storage/search module in `services/method-development/app/`
- small seed dataset under `services/method-development/app/` or `services/method-development/tests/fixtures/`
- tests for ranking order and empty results

Non-goals:

- no PDF parsing yet
- no extraction from literature yet
- no production vector DB requirement

Validation:

- tests that known seeded molecules retrieve expected records
- implemented files:
  - `services/method-development/app/retrieval_store.py`
  - `services/method-development/app/data/seed_methods.json`
  - `services/method-development/tests/test_retrieval_store.py`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 23 passed

Completion signal:

- the product can already answer retrieval questions from a hand-curated corpus

Prompt to use later:

```text
Implement Chunk C3 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Build a seeded retrieval store for the HPLC retrieval MVP in `services/method-development`.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- Schema chunk C1 and chemistry chunk C2 are the foundation

Do:
- add a small curated set of retrieval records using the retrieval schema
- implement storage/load helpers
- implement Tanimoto similarity ranking over normalized fingerprints
- add tests for result ranking and no-match behavior

Do not:
- add endpoints yet
- parse PDFs
- introduce Milvus or external DB infrastructure

Definition of done:
- the system can retrieve the most similar historical records from a local seeded corpus
```

### C4 - Retrieval Query API

Status:

- implemented

Purpose:

- turn the retrieval engine into a usable product surface

Deliverables:

- API request/response models for retrieval
- endpoint for target SMILES and optional impurity SMILES
- ranked results with scores and evidence fields
- API tests

Likely files:

- `services/method-development/app/main.py`
- retrieval schema module
- retrieval service module
- `services/method-development/tests/`

Non-goals:

- no document ingestion yet
- no automated extraction yet

Validation:

- FastAPI endpoint tests for valid, invalid, and empty queries
- implemented files:
  - `services/method-development/app/main.py`
  - `services/method-development/app/retrieval_schemas.py`
  - `services/method-development/tests/test_retrieval_api.py`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 27 passed

Completion signal:

- retrieval is externally usable over HTTP

Prompt to use later:

```text
Implement Chunk C4 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Expose the HPLC retrieval engine through `services/method-development`.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- Existing FastAPI app: `services/method-development/app/main.py`

Do:
- add a retrieval request/response contract
- add an endpoint that accepts target SMILES and optional impurity SMILES
- return ranked retrieval matches with similarity scores and structured method details
- add API tests covering success, invalid SMILES, and empty results

Do not:
- build PDF ingestion
- add extraction logic
- add ML recommendation logic

Definition of done:
- a caller can submit chemistry inputs and receive ranked method records over HTTP
```

### C5 - Source Document Registry

Status:

- implemented

Purpose:

- create the first ingestion boundary for future automated extraction

Deliverables:

- register source documents and basic metadata
- load raw text from PDF/HTML
- identify likely experimental/method sections at a coarse level
- preserve page-level traceability where the parsing path supports it
- keep the ingestion job format compatible with a future LoA-style resumable, schema-driven workflow without depending on LoA code directly

Source-shape research notes:

- representative open-access article formats were reviewed to shape the C5 ingestion boundary around real journal sources rather than generic documents
- reviewed samples:
  - PLOS One: `https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0229990`
  - Scientific Reports: `https://www.nature.com/articles/s41598-024-78415-1`
  - MDPI / IJMS: `https://www.mdpi.com/1422-0067/17/10/1719`
- PLOS HTML exposes clean section headings plus figure, table, and supplement links
- Scientific Reports HTML is structured but less uniform and is paired with a reliable downloadable PDF path
- MDPI provides highly machine-readable HTML plus PDF/XML/Epub download surfaces

Implementation stance:

- support both publisher HTML and PDF in C5
- treat HTML as first-class because journal HTML often exposes cleaner section structure than PDF
- keep PDF first-class for page traceability, supplements, and publisher variation
- capture text, coarse sections, and table placeholders now
- leave schema hooks for figures, images, and supplements without parsing them yet
- optimize first for born-digital journal PDFs and structured publisher HTML

Recommended MVP parser path:

- `pdfplumber` for PDF
- `beautifulsoup4` + `lxml` for HTML
- normalize all sources into one internal document shape with source metadata, pages, sections, text blocks, and placeholders for tables/figures/supplements

Likely files:

- new ingestion module under `services/method-development/app/`
- schema additions for source documents
- tests using small fixtures

Non-goals:

- no full extraction of HPLC fields yet
- no figure parsing
- no broad OCR or scanned-PDF support yet

Validation:

- tests proving documents can be registered and text can be extracted or loaded
- implemented files:
  - `services/method-development/app/source_document_schemas.py`
  - `services/method-development/app/source_document_ingestion.py`
  - `services/method-development/app/source_document_registry.py`
  - `services/method-development/app/source_documents_router.py`
  - `services/method-development/tests/test_source_document_ingestion.py`
  - `services/method-development/tests/test_source_document_api.py`
  - `services/method-development/tests/fixtures/sample_hplc_article.html`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 36 passed

Completion signal:

- later extraction chunks have a consistent raw document input format

Prompt to use later:

```text
Implement Chunk C5 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add a source document registry and raw text ingestion foundation for the retrieval MVP.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- add models and services for registering source documents
- load raw text from PDF or HTML inputs using a constrained MVP path
- capture coarse section-level metadata useful for later extraction
- preserve placeholders for tables, figures, and supplements without parsing figure/image content yet
- add focused ingestion tests

Do not:
- parse molecular graphics
- add broad OCR or scanned-PDF handling yet
- extract final HPLC records yet
- add review UI

Definition of done:
- later chunks can consume a registered source document and its normalized raw text consistently across publisher HTML and born-digital PDFs
```

### C6 - Minimal Text HPLC Extraction

Status:

- implemented

Purpose:

- extract useful structured records from easy, text-native papers before attempting harder multimodal work

Deliverables:

- extraction of column details, flow rate, temperature, mobile phases, retention times, and simple gradient statements
- transformation into the retrieval schema
- extraction confidence flags where fields are partial or ambiguous
- source pages and evidence snippets attached to extracted records whenever available
- keep the extraction step boundaries modular so later planner/observer orchestration can wrap them cleanly

Non-goals:

- no image extraction
- no complex table reconstruction
- no R-group expansion

Validation:

- tests against small fixtures representing easy papers or text samples
- current implementation status:
  - added `services/method-development/app/hplc_extraction_schemas.py`
  - added `services/method-development/app/hplc_text_extraction.py`
  - added `services/method-development/app/hplc_extraction_router.py`
  - added `POST /source-documents/{source_document_id}/extract-hplc`
  - extraction now returns retrieval-schema-aligned method components (`ChromatographySystem`, `MethodParameters`) when text coverage is sufficient, plus retention-time observations, evidence snippets, extraction confidence, chromatography-system candidates, mobile-phase candidates, mobile-phase detail candidates, gradient candidates, timing candidates, anchored entity candidates, molecular-entity drafts with reusable lookup keys, and a safe retrieval-record draft that remains blocked on later anchoring work
  - full retrieval-record assembly is still blocked on later anchoring work because `molecular_entities` are not yet mapped into a trustworthy final record shape
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 58 passed

Completion signal:

- the system can turn at least some real method text into structured retrieval records

Prompt to use later:

```text
Implement Chunk C6 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add minimal text-native HPLC extraction for the retrieval MVP.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- Source document registry from C5 is the input boundary

Do:
- extract text-native HPLC fields from simple method descriptions
- support column details, flow rate, temperature, mobile phases, retention times, and simple gradients
- convert extracted data into the retrieval schema
- add tests using small realistic fixtures

Do not:
- parse images
- solve table OCR broadly
- add orchestration agents

Definition of done:
- at least some easy papers can become structured retrieval records automatically
```

### C7 - Entity Anchoring

Status:

- implemented

Purpose:

- reduce the biggest extraction failure mode: wrong retention time mapped to wrong molecule

Deliverables:

- local identifier matching such as `4a`, `intermediate 2`, or `API`
- proximity- and section-based anchoring rules
- unresolved-state handling when the system is unsure

Non-goals:

- no image-based structure reconstruction

Validation:

- tests covering correct and ambiguous identifier-to-method mappings
- current implementation status:
  - local identifier anchoring covers labels such as `compound 4a`, `intermediate 2`, `API`, named peaks, and named products
  - proximity and section context are used through sentence-level extraction, section weighting, timing overlap, and lightweight co-reference merging for generic aliases such as `target compound`, `desired isomer`, and `main peak`
  - unresolved-state handling is explicit via `anchored_entity_candidates`, `molecular_entity_drafts`, placeholder SMILES strings, linkage lookup keys, linkage notes, and validation warnings for generic unresolved anchors
  - record drafts now carry anchored entities and molecular-entity drafts instead of collapsing ambiguous cases into a fake final record
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 58 passed

Completion signal:

- extracted records are less likely to assign method parameters to the wrong compound

Prompt to use later:

```text
Implement Chunk C7 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add entity anchoring so extracted retention times and method details map to the correct compounds.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- add identifier anchoring rules for local compound labels
- use proximity and section context to attach parameters to compounds
- flag unresolved or ambiguous mappings explicitly
- add tests for both successful and ambiguous cases

Do not:
- implement image-to-graph extraction
- add ML scoring

Definition of done:
- extracted structured records carry compound-to-method mappings with explicit confidence or ambiguity state
```

### C8 - Validation Layer

Status:

- implemented

Purpose:

- prevent obviously bad extraction from polluting the retrieval corpus

Deliverables:

- schema bounds checks
- simple pressure sanity checks
- simple pH/stationary-phase compatibility heuristics
- duplicate/conflict detection
- validation report attached to records

Non-goals:

- no full physical model
- no overclaiming of correctness

Validation:

- tests for rejected impossible records and accepted reasonable ones
- current implementation status:
  - added `services/method-development/app/hplc_record_validation.py`
  - validation now runs automatically against `record_draft`
  - current checks cover simple flow/pressure sanity, stationary-phase vs pH heuristics, duplicate/conflict detection for selected retention assignments, unresolved molecular-entity linkage warnings, and generic-anchor unresolved warnings
  - validation output is attached to `record_draft.validation` and also drives `retrieval_record_ready`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 58 passed

Completion signal:

- automated extraction can be filtered before being used for retrieval

Prompt to use later:

```text
Implement Chunk C8 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add a validation layer for extracted HPLC retrieval records.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- add schema-bound validation rules
- add simple pressure sanity heuristics
- add simple stationary-phase and pH compatibility checks
- attach validation output to records
- add focused tests for accepted and rejected cases

Do not:
- implement a full thermodynamic simulator
- add optimization logic

Definition of done:
- bad extraction results can be flagged or rejected before entering the retrieval corpus
```

### C9 - Provenance and Reviewability

Status:

- in progress

Purpose:

- make retrieval trustworthy enough for real use
- ensure users can inspect where a method came from and which page or snippet supports it

Deliverables:

- source snippets, page references, extraction confidence, and validation notes
- retrieval results that show why a record matched
- record states such as draft, approved, rejected if needed

Non-goals:

- no polished UI required

Validation:

- tests for provenance fields being present in stored and returned records
- current implementation status:
  - added `services/method-development/app/review_record_schemas.py`
  - added `services/method-development/app/review_record_store.py`
  - added `services/method-development/app/review_records_router.py`
  - review-record snapshots can now be created from extracted source documents and preserve provenance, validation, evidence snippets, and record drafts end to end
  - lightweight review states now exist via `draft`, `approved`, and `rejected`, with approval blocked unless a record is retrieval-ready
  - approved review records now flow into the retrieval corpus slice and retrieval query results surface review summaries alongside matched records
  - retrieval query results now also expose a structured `match_rationale` so callers can see whether a hit is an exact or similarity match, which entity matched, and which provenance snippet best explains the record
  - approved review records now persist with a frozen retrieval-record snapshot plus review summary so startup rehydration does not have to recompute the approved artifact from mutable review drafts
  - review records now persist to a runtime JSON file and approved review records are rehydrated into the retrieval corpus on service startup
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 68 passed

Completion signal:

- humans can inspect evidence behind retrieved records

Prompt to use later:

```text
Implement Chunk C9 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add provenance and reviewability to the retrieval MVP.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- store source snippets, page references, confidence, and validation notes
- return evidence fields in retrieval responses
- keep the implementation backend-focused and lightweight
- add tests that prove provenance is preserved end to end

Do not:
- build a full frontend review app
- add surrogate-model features

Definition of done:
- a scientist can inspect why a retrieved record exists and why it matched
```

### C10 - Mixture-Aware Ranking

Status:

- implemented

Purpose:

- move from single-molecule similarity toward practical method-development assistance

Deliverables:

- rank methods using target plus impurity set similarity
- aggregate or weighted scoring logic
- optional penalties for methods that only match the target but ignore impurities

Non-goals:

- no claim of true separation prediction

Validation:

- tests for ranking behavior across target-only vs mixture-aware queries
- current implementation status:
  - `POST /retrieval/query` now switches to `target_plus_impurities` ranking mode when impurity SMILES are provided
  - retrieval ranking now uses a deterministic aggregate score of `0.7 * target_score + 0.3 * average_impurity_score`
  - the primary `matched_entity` remains the best target match, while `match_rationale` now carries impurity-match details, target score, and aggregate score for explanation
  - focused tests now cover both store-level and API-level ranking changes for mixture queries using synthetic multi-analyte records
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 71 passed

Notes before starting:

- `C9` is already useful enough to support retrieval trust and review flows, but it can still be extended later without blocking `C10`
- likely future `C9` additions:
  - richer review-record detail payloads that expose more frozen evidence and selected-field provenance without requiring clients to inspect the full extraction snapshot
  - better provenance summarization for retrieval hits, such as field-level evidence bundles for matched molecule, column, mobile phase, and timing selections
  - more durable review audit metadata if reviewer identity, timestamps, or manual evidence annotations become necessary
  - optional lightweight review-search or filtering endpoints once approved-record volume grows

Completion signal:

- retrieval results are more useful for real mixtures

Prompt to use later:

```text
Implement Chunk C10 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Make retrieval ranking mixture-aware for target plus impurity inputs.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- extend retrieval ranking to use both target and impurity molecules
- document and implement a clear aggregate scoring rule
- add tests proving the ranking changes in expected ways for mixture queries

Do not:
- implement retention-time prediction
- add chromatogram simulation

Definition of done:
- retrieval results better reflect real method-development use cases involving mixtures
```

### C11 - Extraction Coverage Expansion

Status:

- in progress

Purpose:

- increase recall incrementally without redesigning the MVP

Deliverables:

- better table handling
- OCR path for scanned PDFs
- supplementary-info support

Non-goals:

- no broad figure-to-structure ambition yet

Validation:

- tests or fixtures per added extraction mode
- current implementation status:
  - started a narrow table-handling slice by extracting retention-time observations from captioned in-document tables when analyte and retention-time rows are explicit in HTML-derived text
  - multicolumn gradient tables are now parsed more explicitly from header-aware table rows, allowing step/time/%A/%B layouts without flattening the wrong numeric columns into the gradient profile
  - table-derived retention observations now feed the existing anchoring and draft-building path without changing the retrieval schema
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 73 passed

Completion signal:

- more literature can be converted into structured retrieval records

Prompt to use later:

```text
Implement Chunk C11 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Expand extraction coverage for the retrieval MVP beyond easy text-only papers.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- improve extraction for tables, scanned text, or supplementary sources in a narrowly scoped way
- keep the new coverage incremental and test-backed

Do not:
- attempt full chemical figure understanding
- introduce planner/observer orchestration yet

Definition of done:
- extraction coverage grows measurably while staying compatible with the existing schema and validation pipeline
```

### C12 - Agentic Orchestration Layer

Status:

- in progress

Purpose:

- add retries, planning, and step coordination only after extraction components already exist and are testable

Deliverables:

- planner/retry loop
- step-level observation and failure handling
- structured state transitions across extraction steps
- architecture may borrow ChemEAGLE-style planner / observer patterns, but should wrap existing bespoke extraction modules instead of replacing them

Non-goals:

- no attempt to replace validation with LLM judgment
- no surrogate model yet

Validation:

- tests for retry/fallback behavior around extraction steps
- current implementation status:
  - added a first synchronous orchestration route at `POST /c12/review-records/orchestrate`
  - the first slice wraps source registration, review-record creation or reuse, optional entity-resolution application, and optional approval/materialization around the existing deterministic modules
  - retry behavior now reuses the latest review record for a source document by default instead of forcing clients to coordinate repeated multi-call flows
  - step responses now include explicit state, attempt counts, and execution-budget cutoff reporting so the orchestrator has a hard stop instead of open-ended retries
  - an optional Gemini-backed observer branch can now summarize orchestration outcomes when enabled, but extraction and approval decisions remain deterministic
  - a written execution plan for this slice lives at `docs/agents/plans/2026-04-19-c12-orchestration-first-slice.md`
- latest verification:
  - `cd services/method-development && uv run pytest -q` -> 78 passed

Completion signal:

- the extraction pipeline can recover from partial failures without manual rewiring

Prompt to use later:

```text
Implement Chunk C12 from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Goal:
Add agentic orchestration around the existing extraction pipeline only after the underlying deterministic steps exist.

Context:
- Product spec: `docs/AI HPLC Method Development Specification.md`
- Plan: `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`

Do:
- add orchestration, retries, and structured step-state handling around existing extraction modules
- keep validation deterministic and separate from orchestration
- add tests around failure recovery and retry behavior

Do not:
- implement surrogate-model prediction
- add optimization or chromatogram simulation

Definition of done:
- the extraction workflow can coordinate multiple steps and recover from expected failures cleanly
```

## What To Skip Until Much Later

These are explicitly not early-prompt work:

- physics-informed retention-time prediction
- XGraphBoost or related hybrid ML
- Bayesian optimization of gradients
- fully automated baseline-separation recommendation
- chromatogram rendering based on predicted retention
- production-scale vector infra chosen too early

## Validation Matrix

For docs-only changes to this plan:

- `npm run agent:harness:check`

When implementing future chunks:

- Method-development-focused chunks: `cd services/method-development && uv run pytest -q`
- if a chunk changes docs under `docs/agents` or instruction files: `npm run agent:harness:check`
- if any future chunk crosses into sidecar contracts: also run `cd apps/sidecar && uv run pytest -q`

## Risks and Rollback Strategy

### Risks

- the source spec is much broader than the first useful product
- entity anchoring is the hardest early extraction problem
- gradient parsing from literature will be messy even in text-only mode
- early automation may look accurate while still silently mismapping compounds
- pushing into ML too early will hide data-quality problems rather than solve them

### Rollback Strategy

- if automated extraction quality is poor, fall back to manually seeded and human-reviewed retrieval records
- if a broader storage/search design becomes heavy too early, keep the seeded corpus in-process until query behavior is stable
- if document parsing becomes noisy, keep ingestion and extraction separated so the retrieval core still works with curated records

## Recommended Starting Point

Start with C1, then C2, then C3, then C4.

That sequence yields the first externally usable retrieval MVP without waiting on literature parsing quality.

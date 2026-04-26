---
status: completed
owner: platform
last_verified: 2026-04-19
last_updated: 2026-04-19
applies_to: services/method-development
source_of_truth: docs/agents/execution-plans.md
---

# HPLC Retrieval Session Summary

## What Was Done

- Created a new backend boundary at `services/method-development`
- Added local guidance and service docs:
  - `services/method-development/AGENTS.md`
  - `services/method-development/README.md`
  - `services/method-development/app/README.md`
  - `services/method-development/tests/README.md`
- Added a new FastAPI service skeleton:
  - `services/method-development/pyproject.toml`
  - `services/method-development/app/main.py`

## MVP Chunks Completed

- `C1` Retrieval schema
  - `services/method-development/app/retrieval_schemas.py`
  - `services/method-development/tests/test_retrieval_schemas.py`
- `C2` Chemistry normalization and fingerprints
  - `services/method-development/app/chemistry.py`
  - `services/method-development/tests/test_chemistry.py`
- `C3` Seeded retrieval store
  - `services/method-development/app/retrieval_store.py`
  - `services/method-development/app/data/seed_methods.json`
  - `services/method-development/tests/test_retrieval_store.py`
- `C4` Retrieval API
  - `services/method-development/app/main.py`
  - `services/method-development/tests/test_retrieval_api.py`
- `C5` Source document registry
  - `services/method-development/app/source_document_schemas.py`
  - `services/method-development/app/source_document_ingestion.py`
  - `services/method-development/app/source_document_registry.py`
  - `services/method-development/app/source_documents_router.py`
  - `services/method-development/tests/test_source_document_ingestion.py`
  - `services/method-development/tests/test_source_document_api.py`
  - `services/method-development/tests/fixtures/sample_hplc_article.html`

## Planning And Decision Docs Added Or Updated

- Main chunk plan updated and current through `C6` start:
  - `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`
- External framework evaluation written:
  - `docs/agents/plans/2026-04-18-chemical-extraction-framework-evaluation.md`
- Repo/docs updated for new service boundary:
  - `AGENTS.md`
  - `README.md`
  - `docs/architecture/repo-structure.md`
  - `docs/agents/index.md`
  - `docs/agents/architecture-boundaries.md`
  - `docs/agents/quality-gates.md`
  - `docs/agents/release-and-testing.md`

## Current Behavior

- The service exposes `POST /retrieval/query`
- The service also exposes `POST /source-documents/` and `GET /source-documents/{source_document_id}`
- The service now also exposes `POST /source-documents/{source_document_id}/extract-hplc`
- The service now also exposes review-record endpoints for provenance snapshots and review-state updates
- Retrieval now uses seeded and approved review-backed records with target-only or deterministic mixture-aware ranking depending on whether impurity SMILES are supplied
- Retrieval query results now include review summaries for matched records, including approved review-backed records when they enter the retrieval corpus slice
- Retrieval query results now also include a structured `match_rationale` describing the matched entity, exact-vs-similarity match type, and a supporting provenance snippet
- Mixture-aware retrieval now uses a deterministic `0.7 * target_score + 0.3 * average_impurity_score` rule and keeps impurity-match details visible in `match_rationale`
- Review records now persist across restarts through a runtime JSON snapshot, and approved review records now persist with a frozen retrieval-record snapshot before being reloaded into the retrieval corpus on startup
- Provenance fields already exist in the schema and are returned with records
- Source document registration works for inline publisher-style HTML and base64-encoded born-digital PDFs
- C5 captures raw text, coarse sections, page text where available, and table/figure/supplement placeholders
- C6 now extracts first-pass text-native method components such as column geometry, mobile phases, flow rate, temperature, simple gradients, and retention-time observations when the document text is explicit enough
- The C6 response currently stops at retrieval-schema-aligned method components plus evidence; it does not yet emit a trustworthy final `RetrievalMethodRecord`
- C6 now also exposes `mobile_phase_candidates` so alternative solvent statements such as `instead of ACN we tested phosphate buffer` can be kept as trial/comparison notes instead of silently overwriting the final selected mobile-phase pair
- C6 now also exposes `mobile_phase_detail_candidates` so additive and pH statements can be kept as candidate details and only enrich the selected final mobile-phase system when appropriate
- C6 now also exposes `gradient_candidates` so optimization tables and trial gradients stay visible without overwriting a stronger final text-selected gradient profile
- C6 now also exposes `timing_candidates` so explicit run-time statements and gradient-derived timings can be compared without silently overwriting each other
- C6 now also exposes `chromatography_system_candidates`, candidate-aware retention-time observations, and `anchored_entity_candidates` so trial columns, optimization-only retention times, and local-identifier mentions do not automatically become the selected method output
- C6 now emits a `record_draft` object whenever enough method components exist, and that draft now carries anchored entities plus molecular-entity drafts while still declaring unresolved requirements until SMILES mapping lands in later chunks
- C8 is now started with a lightweight validation layer attached to `record_draft.validation`
- C7 is now implemented through local-identifier anchoring, alias grouping, lightweight co-reference handling, and unresolved placeholder drafts when the anchor is still generic
- C8 is now implemented through draft-level validation that flags implausible geometry/pH combinations and unresolved generic/entity linkage states before retrieval use
- C9 is now started with review-record snapshots that preserve extraction provenance, validation state, evidence snippets, and review status end to end
- Mixture-aware ranking is now implemented for target plus impurity inputs
- C11 is now started with a narrow table-extraction slice for captioned retention-time tables inside already ingested documents
- C11 now also parses multicolumn gradient tables more explicitly from header-aware rows, which makes step/time/%A/%B layouts usable without broad parser rewrites
- C12 is now started with a first deterministic orchestration route that coordinates registration, review-record creation/reuse, and optional approval/materialization
- C12 step reporting now includes explicit state, attempts-used metadata, and a hard execution-budget cutoff so the orchestrator cannot spin indefinitely
- C12 now also has a first optional Gemini-backed observer branch that summarizes deterministic orchestration outcomes without replacing the core extraction/validation path
- Molecular anchoring and full record assembly are not implemented yet

## Validation Status

- `cd services/method-development && uv run pytest -q` -> 78 passed
- `cd apps/api && uv run pytest -q` -> 20 passed
- `npm run agent:harness:check` -> passed

## C5 Notes

- `C5` is now implemented as an in-memory source document registry plus constrained PDF/HTML ingestion surface
- Reviewed representative open-access journal article formats to shape the next ingestion boundary around real HPLC-style source documents
- Sample article formats reviewed:
  - PLOS One: `https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0229990`
  - Scientific Reports: `https://www.nature.com/articles/s41598-024-78415-1`
  - MDPI / IJMS: `https://www.mdpi.com/1422-0067/17/10/1719`
- The implemented HTML ingestion path was smoke-tested against saved HTML from all 3 sample article pages
- Current smoke-test shape:
  - PLOS: coarse sections plus figure, table, and supplement placeholders are now captured from publisher-specific HTML blocks
  - Scientific Reports: coarse sections plus figure and supplement placeholders extract reasonably well from HTML and PDF
  - MDPI: sections, figures, and table placeholders are captured, but some extra non-method sections are still included and will need filtering in later chunks
- Publisher-specific HTML placeholder heuristics were then tightened for PLOS-style `div.figure` / supporting-information markup and MDPI `html-fig-wrap` / `html-table-wrap` markup
- HTML section filtering now also drops common back-matter labels and utility wrapper sections so MDPI-style pages contribute less non-method noise to extraction
- The BeautifulSoup `strip_cdata` deprecation warning was removed by switching C5 HTML parsing onto a custom `lxml` builder path
- Real PDF smoke-test status:
- PLOS PDF download succeeded, title inference is correct, and compact headings such as `Abstract`, `Materialsandmethods`, `Resultsanddiscussion`, and `Supportinginformation` now split more cleanly into coarse sections
- PDF heading parsing now also handles heading-prefix lines such as `Materialsandmethods Waters XBridge...` and `Resultsanddiscussion The PMP-glucose peak...`, which keeps extracted evidence anchored to the right section labels on compact PLOS-style layouts
  - Scientific Reports PDF download succeeded and title inference now matches the full article title
  - MDPI PDF download returned `403` in this environment, so only its HTML ingestion path was exercised directly
- Main conclusion: `C5` should support both publisher HTML and PDF from the start
- HTML is worth treating as first-class because journal HTML often exposes cleaner section structure than PDF
- PDF remains first-class for page traceability, supplements, and publisher variation
- Recommended MVP parser stack for `C5`:
  - `pdfplumber` for PDF
  - `beautifulsoup4` + `lxml` for HTML
- Immediate capture target for `C5`:
  - source metadata
  - pages when available
  - coarse sections
  - text blocks
  - table placeholders
  - future placeholders for figures/images/supplements
- Deferred for later chunks:
  - OCR for scanned PDFs
  - figure/image parsing
  - final HPLC record extraction

## C6 Notes

- `C6` is now started with a text-first extraction surface at `POST /source-documents/{source_document_id}/extract-hplc`
- The initial extractor is intentionally conservative and only turns text into retrieval-schema-aligned method components when the source states the values explicitly enough
- The current extractor supports:
  - column geometry and stationary-phase chemistry when dimensions are given in text
  - candidate selection across competing column/system mentions
  - mobile phases A/B
  - candidate solvent-system notes for final vs trial/comparison wording
  - additive/pH enrichment for the selected mobile phase via candidate detail statements
  - gradient candidates from both natural-language statements and simple table-derived text
  - timing candidates from explicit run-time statements and gradient-derived total times
  - flow rate
  - column temperature
  - run time
  - simple gradient statements such as `10 to 64% B over 30 min, hold 5 min, return to initial over 1 min`
  - simple retention-time observations
  - local-identifier anchoring from retention sentences such as `compound 4a`, `intermediate 2`, `API`, or named peaks
- The current extractor returns evidence snippets and extraction confidence for every captured field
- The extractor now prefers the highest-confidence final full-system solvent candidate and leaves replacement/comparison wording in `mobile_phase_candidates` for review
- The extractor now uses candidate detail statements to enrich additives and pH on the selected mobile phase instead of treating every acid/base note as final automatically
- The extractor now prefers the highest-confidence final gradient candidate, preferring explicit text statements over table-derived candidates when both are available
- The extractor now prefers the highest-confidence final chromatography-system candidate and marks only selected retention-time observations for the draft assembly path
- The extractor now keeps timing candidates and local-identifier anchors visible in the response while selecting only the strongest final candidates for the draft path
- PDF extraction now also builds shorter line-block text sources from PDF sections and pages so regex-based evidence capture stays more local on compact publisher layouts
- The extractor now collapses simple alias variants such as `compound 4a`, `4a`, and `target compound` into molecular-entity drafts, and it normalizes named-product variants such as `PMP glucose` / `PMP-glucose`
- The extractor now also captures lightweight co-reference aliases such as `desired isomer` and `main peak` and converts molecular-entity drafts into reusable lookup-key bundles for future SMILES linkage work
- The extractor now also keeps generic-only aliases such as `main peak` unresolved on purpose and surfaces them as placeholder drafts plus validation warnings instead of overcommitting to a wrong anchor
- The current `record_draft` is intentionally incomplete and still lists unresolved requirements such as molecule/SMILES anchoring before a real `RetrievalMethodRecord` can be emitted
- `C7` is implemented at the heuristic anchoring layer, but full molecule-to-SMILES anchoring and final record assembly remain incomplete

## C8 Notes

- `C8` is now implemented through `services/method-development/app/hplc_record_validation.py`
- Validation currently runs on `record_draft` rather than on a final `RetrievalMethodRecord`, which keeps the validation layer useful without blocking later record assembly work
- Current validation checks include:
  - narrow-bore flow-rate sanity
  - simple pressure-risk heuristic from flow, column geometry, and particle size
  - simple pH vs stationary-phase compatibility heuristic
  - duplicate/conflicting retention-time assignment detection for selected observations
  - unresolved molecular-entity linkage warnings
  - generic-anchor unresolved warnings
- Validation output is attached at `record_draft.validation`
- `retrieval_record_ready` is now derived from the validation state, so obviously bad drafts are blocked early

## C9 Notes

- `C9` is now started through an in-memory review-record layer
- New review endpoints:
  - `POST /source-documents/{source_document_id}/review-records`
  - `GET /review-records`
  - `GET /review-records/{review_record_id}`
  - `POST /review-records/{review_record_id}/status`
- Review-record snapshots preserve:
  - extraction provenance
  - evidence snippets
  - validation state
  - record drafts and molecular-entity drafts
  - lightweight review status (`draft`, `approved`, `rejected`)
- Approval is currently blocked unless a record is retrieval-ready, which keeps review states honest while later chunks finish full retrieval-record assembly
- Approved review records now materialize into the in-memory retrieval corpus slice, and retrieval query results surface `review_summary` so matched records show whether they are seeded or review-backed approved records
- Retrieval query results now also surface `match_rationale` so scientists can quickly understand why a record matched before inspecting the full provenance payload
- Review records persist by default at `tmp/method-development/review_records.json` and can be redirected with `SILICO_METHOD_DEVELOPMENT_REVIEW_RECORDS_PATH`
- Approved review records now also persist a frozen materialized retrieval-record snapshot plus review summary so later startup rehydration does not depend on recomputing from mutable review drafts
- `C9` is strong enough to stop being the default next chunk, but there is still room for later hardening:
  - add richer frozen evidence bundles on review-record detail responses
  - expose more field-level provenance summaries directly in retrieval responses
  - add optional reviewer/audit metadata if manual review becomes multi-user
  - add lightweight review-record filtering/search once record volume grows

## C10 Notes

- `C10` is now implemented in the retrieval store and API path
- Mixture-aware ranking remains intentionally deterministic and lightweight for the MVP
- The aggregate score is currently defined as `0.7 * target_score + 0.3 * average_impurity_score`
- The current implementation keeps the best target-matched entity as the primary retrieval match while surfacing impurity-match contributions inside `match_rationale`
- Focused tests now prove that a multi-analyte record can outrank a target-only record when the impurity set is relevant

## C11 Notes

- `C11` is now started through a narrow table-handling path instead of a broad parser rewrite
- The first slice extracts retention-time observations from captioned in-document tables when analyte labels and retention-time rows are explicit in the normalized article text
- The next slice now also handles multicolumn gradient tables with extra step columns and explicit `%A`/`%B` headers, which reduces false flattening of unrelated numeric columns
- Those table-derived observations already feed the existing anchoring, evidence, and draft-building pipeline, so the new coverage expands recall without changing downstream contracts
- Good next C11 follow-ups are:
  - richer gradient-table parsing beyond the current simple numeric layout assumptions
  - supplementary-material ingestion from already-detected supplement placeholders
  - a constrained scanned-PDF fallback only after deciding on runtime/dependency expectations

## C12 Prep Notes

- The current deterministic extraction surfaces are now clean enough to be wrapped by orchestration without rethinking the contracts:
  - source registration and retrieval via `source_documents_router`
  - text-first extraction via `POST /source-documents/{source_document_id}/extract-hplc`
  - draft validation via `hplc_record_validation.py`
  - review snapshot creation and approval/materialization via the review-record store and router
- A reasonable first C12 orchestration path would be a step runner over: register source -> extract -> validate -> create review record -> optionally approve when retrieval-ready
- The safest C12 scope is retry/fallback orchestration around existing deterministic modules, not new extraction heuristics

## C12 Notes

- `C12` is now started through `POST /c12/review-records/orchestrate`
- The first slice is intentionally synchronous and deterministic rather than queue-backed or LLM-driven
- Current orchestration behavior:
  - register or reuse the source document
  - create or reuse the latest review record for that source
  - optionally apply entity resolutions
  - optionally approve and materialize the record when retrieval-ready
- The route now also exposes an explicit orchestration budget (`max_step_attempts`, `max_total_steps`) and reports `cutoff` when the request reaches that boundary before a later step can run
- Current focused tests cover blocked approval, successful approval, duplicate-safe retry reuse, and duplicate-registration failure when retry is disabled
- Current focused tests also cover budget exhaustion before approval so the route stops cleanly rather than retrying indefinitely

## Where To Start Next Session

Continue with `C12` from the first orchestration slice, or return to `C11` for more extraction coverage in `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md`.

Next implementation target:

- expand extraction coverage from the new retention-table slice into richer table handling, supplementary information, or a constrained scanned-PDF fallback
- keep the current `C9` and `C10` retrieval behavior stable while improving recall
- add narrowly scoped fixtures for each new extraction mode instead of broad parser rewrites
- continue preserving provenance and validation compatibility with the existing review pipeline
- if shifting to `C12`, start by orchestrating the existing register/extract/validate/review steps rather than adding new extraction logic inside the orchestrator
- for the next `C12` slice, prefer structured retry/fallback state tracking and explicit step outcomes over hidden side effects
- keep bounded execution as a first-class rule so future agentic behavior cannot consume unbounded tokens or retries per request

Suggested resume prompt:

```text
Continue from `docs/agents/plans/2026-04-18-hplc-retrieval-mvp-breakdown.md` and continue C12 in `services/method-development`, building on `POST /c12/review-records/orchestrate` to add clearer step-state tracking, explicit retry/fallback behavior, or additional orchestration endpoints without changing the deterministic extraction and validation internals.
```

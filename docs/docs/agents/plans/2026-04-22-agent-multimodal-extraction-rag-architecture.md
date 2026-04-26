---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development multimodal extraction evidence retrieval RAG research
source_of_truth: docs/agents/execution-plans.md
---

# Agent Multimodal Extraction And RAG Architecture

## Goal and Success Criteria

Define the longer-term architecture for evolving the method-development service from a text-first extraction system with record-level retrieval into a modality-aware extraction and evidence-level retrieval system optimized for HPLC method recommendation.

Success means:

- future work has a concrete architecture to follow rather than vague “add RAG” goals
- the system remains HPLC-specific rather than drifting into generic chemistry extraction
- multimodal extraction and evidence retrieval are clearly separated from the hackathon build
- ChemEagle-inspired ideas are translated into Silico-specific design decisions

## Scope

- modality planner
- specialized extraction workers
- validator/observer roles
- cross-modal entity linking
- evidence-level retrieval/indexing
- phased scope split between build-soon and research-next

## Explicit Non-Goals

- no attempt to replicate ChemEagle’s reaction-extraction product
- no immediate replacement of the current recommendation engine
- no multimodal benchmark implementation in Wave 1

## Current State

Current backend strengths:

- strong text-first HPLC extraction
- review-record lifecycle and promotion loop
- deterministic validation
- recommendation engine with trust/evidence-rich payloads
- retrieval at the record level using seeded or review-promoted method records

Current backend limitations:

- extraction is still primarily text-centric
- tables and figures are not first-class retrieval/evidence units
- retrieval centers on records, not evidence fragments
- no explicit modality planner decides how to process a source before extraction starts

## External Inspiration And What To Borrow

ChemEagle is relevant because its public materials describe:

- a planner agent that decides workflow based on modality
- specialized extraction agents
- observer/validation agents
- strong cross-modal alignment between text, tables, and images

Sources used for this planning pass:

- [AIChE ChemEagle proceeding](https://proceedings.aiche.org/conferences/aiche-annual-meeting/2025/proceeding/paper/chemeagle-mllm-powered-multi)
- [ChemEagle official repository](https://github.com/CYF2000127/ChemEagle)

What Silico should borrow:

- modality-aware planning
- specialized workers instead of one monolithic extractor
- observer/validator passes
- cross-modal alignment as a first-class concern

What Silico should **not** borrow directly:

- reaction-extraction task framing
- generic multimodal chemistry output schema
- benchmark targets optimized for reaction graphics instead of HPLC method recommendation

## Decision-Complete Implementation Approach

### Product boundary stance

All multimodal work must stay downstream of the product goal:

- better HPLC method recommendation
- better trust/evidence traceability
- better corpus growth quality

If a multimodal feature does not improve those outcomes, it is out of scope.

### Architecture stance

Move from:

- source document -> extraction -> record -> retrieval

Toward:

- source document -> modality planning -> specialized extraction passes -> validation/observation -> evidence store -> record assembly -> recommendation retrieval

### Proposed components

#### 1. Modality Planner

Responsibility:

- inspect a registered source document
- classify modality mix:
  - text-heavy
  - table-heavy
  - figure-heavy
  - mixed
- choose extraction plan and worker ordering

Inputs:

- registered source-document metadata
- section structure
- placeholder counts for tables/figures/supplements

Outputs:

- extraction plan
- worker sequence
- expected evidence targets

#### 2. Specialized Extraction Workers

Required worker families:

- section/text extraction worker
- table extraction worker
- figure/asset interpretation worker
- entity-linking worker
- method-assembly worker

Each worker should output:

- structured candidate fields
- evidence pointers
- confidence and warning metadata

#### 3. Validators And Observers

Introduce explicit observer passes that run after or between workers.

Required observer roles:

- completeness observer
- HPLC schema consistency observer
- entity-linkage observer
- trust/readiness observer

These should not replace deterministic validators. They should feed them and explain failure modes more clearly.

#### 4. Cross-Modal Entity Linking

Add an explicit entity-linking stage that reconciles:

- names in text
- abbreviations in tables
- labels in figure captions or assets
- resolved SMILES and molecular entities

Goal:

- avoid making impurity-aware or retrieval-ready claims unless linkage quality is strong enough

#### 5. Evidence-Level Retrieval Index

Introduce an evidence store that indexes smaller units than full records.

Target indexed units:

- evidence snippets
- table rows or parsed table fragments
- entity-linkage records
- extracted method-parameter fragments
- validation and readiness annotations

Use cases:

- citation-quality evidence display
- trust-aware retrieval
- better review tooling
- future recommendation explanations grounded in exact support

### HPLC-specific schema boundaries

All new multimodal outputs must still normalize toward HPLC-specific internal objects:

- chromatography system
- method parameters
- molecular entities
- matrix/sample context
- evidence snippets and provenance
- validation/readiness state

Do not create a generic reaction schema and then try to map it later.

### Retrieval stance

Record-level retrieval remains the serving path in the near term.

Evidence-level retrieval should first be used for:

- explanation
- review tooling
- trust and validation

Only later should it influence ranking more directly.

## Phased Scope

### Hackathon-scope

Not in scope for immediate build:

- modality planner implementation
- multimodal figure recognition
- evidence-level retrieval index
- observer agent framework

### Research-next scope

Next viable research slices:

1. modality planner plus worker-plan output
2. evidence store for snippets and table fragments
3. entity-linkage pass feeding retrieval readiness
4. observer/validator instrumentation

### Later scope

- figure-heavy extraction
- more aggressive evidence-aware ranking
- broader multimodal benchmarks

## Interfaces / Contracts / Types Affected

Likely future additions in `services/method-development`:

- extraction plan metadata
- evidence-unit schemas
- observer result schemas
- explicit entity-linkage confidence fields

Wave 1 rule:

- keep current public recommendation contracts stable
- add multimodal metadata additively where needed

## Validation Matrix

For future implementation:

- `cd services/method-development && uv run pytest -q`
- extraction benchmark cases split by modality type
- evidence-linkage correctness tests
- recommendation trust-surfacing regression tests
- review-readiness tests that prove unresolved cross-modal entities are blocked

## Risks and Rollback

- Risk: multimodal work expands into generic chemistry research rather than product-relevant HPLC extraction.
- Risk: new agent/observer layers add complexity without measurable recommendation benefit.
- Risk: evidence-level retrieval becomes expensive before it becomes useful.

Rollback:

- keep record-level retrieval as the serving backbone
- gate multimodal work behind measurable trust/recommendation improvements

## Decision Notes

- 2026-04-21: ChemEagle is used as architectural inspiration, not as a direct implementation target.
- 2026-04-21: The serving product remains HPLC-method recommendation, so all multimodal work must normalize into HPLC-specific structures.

---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent product UX standalone pitch build
source_of_truth: docs/agents/execution-plans.md
---

# Agent Scientist Copilot Product Spec

## Goal and Success Criteria

Define the near-term product as an installable scientist copilot for HPLC method recommendation that feels technically serious, visually premium, and easy to pitch in a live hackathon demo.

Success means:

- the product story is simple enough to explain in under 30 seconds
- the user flow demonstrates recommendation quality, evidence traceability, and a self-improving corpus loop
- the app reads as real software for scientists, not as a generic AI demo
- downstream implementation docs can inherit a fixed product narrative and screen model

## Scope

- primary user persona and pitch narrative
- end-to-end scientist workflow
- primary screens and states
- trust/evidence story
- explicit definition of what “impressive” means for this product

## Explicit Non-Goals

- no detailed desktop packaging mechanics
- no review-store persistence design beyond the product requirements
- no full multimodal extraction architecture
- no investor deck messaging or marketing-site copy

## Current State

The current app already supports:

- staged system -> target -> source -> recommendation workflow
- recommendation ranking and comparison
- evidence panels and diagnostics
- trust posture, validation posture, and review posture
- exportable analysis handoff

The current gaps are product-shape gaps rather than total capability gaps:

- the app is still presented as a web tool, not a standalone product
- the review/corpus-growth loop is not central enough to the product story
- the experience is not yet explicitly organized around a “scientist copilot” pitch narrative

## Primary User

### Core user

- analytical chemist or method-development scientist
- has a real HPLC/LC-MS setup and real runtime constraints
- wants a strong starting method faster than manual paper search
- cares about evidence, provenance, and fit to their own system

### Secondary user

- technical evaluator, investor, or judge watching a live demo
- needs to understand product value quickly without deep chromatography context

## Product Narrative

The product pitch is:

> “Silico is a scientist copilot that recommends HPLC methods for your actual system, shows the evidence behind the recommendation, and gets smarter as reviewed extractions flow back into the corpus.”

The app should demonstrate three things in order:

1. it understands the scientist’s real system constraints
2. it produces an evidence-backed recommendation instead of a generic answer
3. it turns reviewed extraction output into a reusable asset that improves future runs

## End-To-End User Flow

### 1. Launch

The user opens the app and immediately sees:

- what the app does
- that it is built for HPLC method recommendation
- a fast path into a guided run
- a visible but secondary path into demo-safe or cached content

### 2. Define system context

The user enters:

- column manufacturer and name
- column chemistry and dimensions
- detector types
- available solvents
- runtime preference
- practical instrument constraints

The product message here is:

- “this recommendation is system-aware”

### 3. Define separation target

The user enters:

- analyte or separation request
- target SMILES
- impurity SMILES if relevant
- matrix/sample context
- optional MS requirement

The product message here is:

- “this recommendation is chemistry-aware, not just keyword-aware”

### 4. Choose evidence source

The user chooses:

- curated local corpus
- open-access discovery
- upload a paper or source document

The product message here is:

- “the app can start from both curated prior knowledge and fresh literature”

### 5. Run and inspect result

The app shows:

- live progress and runtime status
- ranked recommendations
- a top-candidate summary
- why the top candidate fits
- trust/evidence details
- how the method was adjusted or scaled

The product message here is:

- “this is an evidence-backed recommendation engine, not a chat answer”

### 6. Reuse and improve

From a recommendation or uploaded source, the user can:

- send a candidate or source into review
- approve and promote reviewed records into the corpus
- rerun and see the system benefit from prior review work

The product message here is:

- “the product builds a compounding data moat through reviewed scientific extraction”

## Primary Screens And States

### Screen 1: Launch / New Run

Required states:

- clean launch
- recent runs visible if available
- demo-safe launch path
- service health warning when hosted dependencies are unavailable

### Screen 2: Run Composer

Required sections:

- system context
- separation target
- source choice

Required states:

- empty
- partially complete
- validation errors
- restored prior session

### Screen 3: Live Run / Progress

Required states:

- queued
- running
- degraded but usable
- timed out
- failed with clear recovery path
- completed

### Screen 4: Recommendation Report

Required surfaces:

- top recommendation summary
- ranked alternatives
- trust/evidence view
- comparison view
- export action
- send-to-review action

### Screen 5: Review / Corpus Flow

Required surfaces:

- review queue
- record detail
- approval with rationale
- promotion with confirmation
- entity-resolution UI for unresolved chemistry

This remains secondary to the scientist workflow, but it must be demoable.

## Trust And Evidence Story

Trust is one of the core product pillars. The app must explain:

- where the recommendation came from
- what evidence supports it
- how validated the extraction is
- whether a human/operator has reviewed it
- whether the method is already part of the reusable local corpus

The user should not have to infer trust from dense diagnostics. The app must make it legible at a glance and inspectable in detail.

### Trust hierarchy

1. recommendation outcome
2. trust state and validation posture
3. evidence snippets and source metadata
4. review/corpus posture
5. detailed diagnostics and skipped-paper information

## What “Impressive” Means In This Product

For this product, impressive does **not** mean:

- maximal animation
- generic AI chat patterns
- speculative scientific claims
- visually noisy dashboards

It **does** mean:

- fast comprehension
- clear scientific seriousness
- visible evidence traceability
- strong recommendation hierarchy
- a memorable self-improving corpus loop
- a desktop product feel rather than a dev-tool feel

## Decision-Complete Implementation Approach

### Product stance

The app should be positioned and built as a recommendation copilot first, with review/corpus tooling as the compounding advantage behind it.

### Workflow stance

The default user flow should stay scientist-first:

- define system
- define target
- choose evidence path
- inspect ranked output

Review tooling should be reachable from this flow, but it must not dominate it.

### Source-mode stance

The app should present three conceptually clear source paths:

- local corpus
- open-access discovery
- uploaded source document

The scientist should not be exposed to backend/operator concepts such as server-local file paths.

### Pitch stance

The first live demo should be readable in this order:

1. system-aware setup
2. evidence-backed recommendation
3. trust/explanation
4. review-to-corpus compounding loop

## Interfaces / Contracts / Types Affected

The product spec assumes continued use of:

- recommendation routes in `services/method-development`
- source-document registration for uploads
- review-record and C12 orchestration flows

The product spec also assumes the frontend expands its `SystemSpecs` model to include currently unsupported but relevant backend fields such as:

- `instrument_modes`
- `max_pressure_bar`

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- backend tests covering any touched contracts in `services/method-development`
- scripted acceptance scenario for:
  - new run -> ranked result
  - upload -> extraction -> review
  - review promotion -> rerun benefit

## Risks and Rollback

- Risk: the product turns into an operator console instead of a scientist tool.
- Risk: the demo over-indexes on flashy extraction claims instead of recommendation quality.
- Risk: the corpus-growth story feels disconnected from the core recommendation flow.

Rollback:

- keep the scientist workflow as the fixed primary path
- keep review and RAG features additive, not identity-defining, for the first release

## Decision Notes

- 2026-04-21: The near-term product is explicitly defined as a scientist copilot, not a general autonomous chemistry platform.
- 2026-04-21: The strongest “wow” factor for the hackathon build is evidence-backed recommendation clarity plus the self-improving corpus loop.

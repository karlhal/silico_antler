---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent services/method-development apps/api future standalone desktop roadmap planning
source_of_truth: docs/agents/execution-plans.md
---

# Agent App Engineering Plan Set

## Goal and Success Criteria

Create a decision-ready documentation set for the agent app so implementation can begin immediately on the highest-value hackathon build while preserving a separate track for deeper multimodal extraction and RAG work.

Success means:

- the current app state is captured accurately in the updated gap report
- the hackathon/pitch track is fully spec’d as an installable scientist copilot
- the longer-term multimodal extraction and evidence-level retrieval work is documented separately and does not contaminate near-term scope
- dependency order across the plan set is explicit enough that future agents can implement top-down without re-deciding sequencing

## Scope

This plan set coordinates the following documents:

1. `docs/post-implementation-gap-report.md`
2. `2026-04-22-agent-app-plan-set.md`
3. `2026-04-22-agent-scientist-copilot-product-spec.md`
4. `2026-04-22-agent-standalone-desktop-architecture.md`
5. `2026-04-22-agent-demo-resilience-and-cache-spec.md`
6. `2026-04-22-agent-tool-contracts-and-upload-flows.md`
7. `2026-04-22-agent-review-and-corpus-growth-spec.md`
8. `2026-04-22-agent-pitch-ui-system-spec.md`
9. `2026-04-22-agent-multimodal-extraction-rag-architecture.md`
10. `2026-04-22-agent-evals-and-proof-spec.md`

## Explicit Non-Goals

- no implementation in this document
- no attempt to revive the full autonomous HPLC platform as a single near-term build
- no merging of the new agent-app desktop shell into the existing `apps/desktop` workbench
- no backend rewrites that are not justified by the hackathon product or the explicit RAG research track

## Current State

The repo already contains a strong foundation:

- `apps/agent` is a real recommendation app, not a mock
- `services/method-development` already supports recommendation, review records, source-document registration, and C12 orchestration
- evidence, diagnostics, review posture, and export are already surfaced in the app
- operator review storage and access control are still prototype-grade
- standalone delivery and demo resilience are not yet documented or implemented

The product gap is therefore not “make it real.” The product gap is:

- make it installable
- make it pitch-legible
- make it demo-safe
- make the corpus-growth loop feel like a product advantage
- keep the deeper RAG/extraction architecture on a separate track

## Track Split

### Track A: Hackathon / Pitch Build

This is the buildable near-term track.

Included docs:

- `agent-scientist-copilot-product-spec`
- `agent-standalone-desktop-architecture`
- `agent-demo-resilience-and-cache-spec`
- `agent-tool-contracts-and-upload-flows`
- `agent-review-and-corpus-growth-spec`
- `agent-pitch-ui-system-spec`
- `agent-evals-and-proof-spec`

Primary objective:

- ship an installable scientist copilot that looks credible, explains recommendations clearly, and demonstrates a self-improving review-backed corpus story

### Track B: Multimodal Extraction / RAG Research

This is the longer-horizon research and architecture track.

Included docs:

- `agent-multimodal-extraction-rag-architecture`
- RAG-related sections in `agent-evals-and-proof-spec`

Primary objective:

- define how the backend evolves from text-first extraction plus record-level retrieval toward modality-aware extraction, validator/observer passes, and evidence-level retrieval

## Dependency Order

1. `docs/post-implementation-gap-report.md`
2. `2026-04-22-agent-app-plan-set.md`
3. `2026-04-22-agent-scientist-copilot-product-spec.md`
4. `2026-04-22-agent-standalone-desktop-architecture.md`
5. `2026-04-22-agent-demo-resilience-and-cache-spec.md`
6. `2026-04-22-agent-tool-contracts-and-upload-flows.md`
7. `2026-04-22-agent-review-and-corpus-growth-spec.md`
8. `2026-04-22-agent-pitch-ui-system-spec.md`
9. `2026-04-22-agent-multimodal-extraction-rag-architecture.md`
10. `2026-04-22-agent-evals-and-proof-spec.md`

## Why This Order Is Correct

- The gap report comes first so the rest of the plan set starts from one factual baseline.
- The plan-set index comes second so every later document can reference the same dependency graph.
- The product spec comes before runtime and UI docs because it locks the user story and success criteria.
- Desktop architecture comes before cache/resilience because delivery shape determines storage and fallback behavior.
- Cache/resilience comes before contracts and review flow because standalone constraints change how uploads, reruns, and operator actions behave.
- The contract doc comes before review/corpus and RAG because those docs depend on stable route usage and payload rules.
- The pitch UI doc follows product, desktop, and resilience so it does not promise unavailable states or flows.
- The RAG architecture doc is intentionally later so long-term research does not distort the near-term build.
- The eval doc comes last so it can define proof criteria against the completed plan set rather than against guesses.

## Recommended Implementation Order

### Phase 1: Product And Delivery Lock

1. `agent-scientist-copilot-product-spec`
2. `agent-standalone-desktop-architecture`
3. `agent-demo-resilience-and-cache-spec`

Reason:

- these three docs define the actual product, delivery target, and demo-safety behavior

### Phase 2: Contract And Operator Loop Lock

4. `agent-tool-contracts-and-upload-flows`
5. `agent-review-and-corpus-growth-spec`

Reason:

- once the desktop/runtime shape is fixed, the app/backend contract and operator loop can be specified against real delivery constraints

### Phase 3: Pitch Presentation Lock

6. `agent-pitch-ui-system-spec`

Reason:

- the UI system should reflect the actual product and runtime, not invent a parallel story

### Phase 4: Research And Proof Lock

7. `agent-multimodal-extraction-rag-architecture`
8. `agent-evals-and-proof-spec`

Reason:

- the RAG architecture should stay additive and future-facing
- the eval doc should prove both the near-term build and the longer-term research direction

## Primary Risks

- Risk: the pitch build scope expands toward generic “AI chemistry platform” claims and slows down delivery.
- Risk: desktop packaging is treated as a cosmetic shell instead of a runtime boundary with explicit config and cache behavior.
- Risk: review/corpus tooling leaks into the default scientist flow in a way that makes the product feel like an operator console.
- Risk: the RAG track becomes vague or inspirational instead of concrete enough to guide future work.

## Rollback Strategy

- if hackathon time collapses, keep Track A and defer Track B without changing the product narrative
- if desktop packaging becomes riskier than expected, keep the same docs and temporarily deliver the same flow as a hosted web build without deleting the architecture work
- if review tooling slips, prioritize auth, rationale capture, and promotion safety first; defer richer queue capabilities second

## Validation Matrix

For this documentation wave:

- `npm run agent:harness:check`

When implementation begins, each focused plan doc defines its own minimum validation matrix.

## Decision Notes

- 2026-04-21: The plan set is explicitly split into a build-now hackathon track and a separate RAG research track.
- 2026-04-21: “Standalone” means an installable desktop shell for the agent app using hosted services, not a fully local scientific runtime.
- 2026-04-21: The documentation wave is intended to unblock implementation immediately, not to serve as investor-facing collateral.

# Agent App Gap Report: Hackathon Pitch And Standalone Readiness

**Date:** 2026-04-18  
**Status:** Current-state gap report  
**Applies To:** `apps/agent`, `services/method-development`, future standalone desktop packaging

## 1. Executive Summary

The agent app is no longer a thin prototype. It already provides a credible recommendation workflow with:

- a staged scientist-facing workflow
- ranked recommendation cards
- evidence and diagnostics panels
- explicit trust and review posture surfacing
- exportable handoff output

The main remaining work is not basic usability. The real gaps are:

1. making the app installable and demo-safe as a standalone desktop product
2. tightening the operator review and corpus-growth loop
3. replacing brittle runtime assumptions with explicit desktop/runtime contracts
4. defining the longer-term multimodal extraction and evidence-level retrieval architecture

This report supersedes the earlier mixed marketing-and-agent framing. The marketing slice is no longer included here.

## 2. Current Product Reality

### Implemented Today

The current repo already supports a meaningful scientist copilot workflow.

#### Scientist workflow
- `apps/agent` captures system specs, target chemistry, source choice, and recommendation runs.
- The app already renders recommendation rankings, runtime state, trust posture, validation posture, review posture, evidence snippets, and skipped-paper diagnostics.
- The app already provides export behavior through the `Export Analysis` flow rather than a dead placeholder button.

#### Backend capabilities already in place
- `services/method-development` already exposes stable recommendation endpoints, async run polling, source-document registration, review-record lifecycle routes, and C12 review-record orchestration.
- Review records already support entity resolutions in the backend contract.
- Retrieval already supports seeded and review-promoted records plus mixture-aware ranking.
- Milvus-backed retrieval already exists for scalable similarity search.

### Implemented But Still Not Pitch-Optimized

These areas exist, but they are not yet in the right form for a hackathon-grade investor demo:

- the current app is still a web app, not an installable standalone product
- runtime and proxy assumptions are still dev-oriented
- the recommendation UI is strong but not yet tuned around an investor-readable “why this wins” story
- the operator loop exists, but the main scientist flow still does not make corpus growth feel like a natural extension of the product

## 3. High-Severity Gaps

| Gap | Severity | Description |
| --- | :---: | --- |
| Standalone desktop shell | P0 | `apps/agent` is still delivered as a Vite app with dev-proxy assumptions and no installable desktop packaging. |
| Operator auth | P0 | The `/review` surface is still effectively public inside the app boundary and is not explicitly gated for operator-only use. |
| Runtime config and startup health | P0 | The app assumes `/api` and `/method-dev` relative paths rather than explicit runtime-configured hosted endpoints. |
| Demo resilience | P0 | The current flow can degrade or fail during live open-access fetch/search conditions without a deliberate cached or demo-safe mode. |
| Upload/orchestration workflow | P1 | The backend supports source-document registration and C12 orchestration, but the app does not yet provide a polished “bring a paper” flow for desktop users. |
| Promotion friction | P1 | Approval and promotion still need stronger confirmation, rationale capture, and separation of responsibilities to protect corpus quality. |
| Transactional review storage | P1 | Review records still persist through `InMemoryReviewRecordStore` backed by JSON persistence, which is not robust enough for concurrent or production-like operator flows. |
| Entity-resolution UI | P1 | The backend can accept `entity_resolutions`, but the review UI does not let operators fix unresolved chemistry before approval. |

## 4. Medium-Severity Gaps

| Gap | Severity | Description |
| --- | :---: | --- |
| Scientist-to-review handoff | P2 | The main recommendation report should let a user send a promising paper/method into review without switching mental context. |
| Desktop-local cache strategy | P2 | The intended local persistence for recent runs, uploaded sources, and fallback snapshots is not defined yet. |
| Stable app/backend contract usage | P2 | The app still carries dev-era assumptions such as proxy prefixes and incomplete request shaping for `instrument_modes` and `max_pressure_bar`. |
| Investor-readable UI hierarchy | P2 | Trust signals are present, but the top-level visual story still needs clearer prioritization for a live pitch. |
| Explicit fallback messaging | P2 | The app should make it obvious whether a result is live, cached, or demo-safe rather than leaving users to infer degraded behavior. |

## 5. Lower-Severity But Strategic Gaps

| Gap | Severity | Description |
| --- | :---: | --- |
| Evidence-level retrieval | P3 | Retrieval is still primarily record-level; future trust and recall improvements should move toward snippet/table/evidence-level indexing. |
| Multimodal extraction planning | P3 | The extraction stack is still predominantly text-first and does not yet use a modality planner for text vs tables vs figures. |
| Validator/observer architecture | P3 | The system has deterministic validation, but not yet a richer observer model for cross-modal extraction quality. |
| Proof framework for the pitch build | P3 | Evaluation assets exist, but the acceptance-proof story for the full desktop copilot and review loop needs a consolidated spec. |

## 6. Technical Debt And Architectural Constraints

### Current runtime constraints
- `apps/agent` still depends on Vite dev proxy behavior for `/api` and `/method-dev`.
- `local_files` is implemented in the backend as server-local path ingestion and is therefore not a valid direct desktop UX for hosted deployment.
- Standalone delivery will need explicit upload-first behavior through `/source-documents`, not path-based file references.

### Current storage constraints
- Review records default to `tmp/method-development/review_records.json`.
- This is acceptable for current prototyping, but not for a serious operator workflow with promotion semantics.

### Current UX constraints
- Trust, evidence, and diagnostics are already present, so the next UI work should improve hierarchy and pitch clarity rather than reintroduce backend-only capabilities that are already surfaced.
- The operator workflow should remain visibly separate from the default scientist workflow even when the two connect more directly.

## 7. Recommended Next Documentation/Implementation Order

1. Lock the agent-only roadmap/spec set.
2. Lock the scientist-copilot product spec.
3. Lock the standalone desktop architecture and runtime resilience behavior.
4. Lock the app/backend upload and contract rules.
5. Lock the operator review and corpus-growth model.
6. Lock the pitch UI system.
7. Lock the multimodal extraction and RAG architecture.
8. Lock the eval and proof framework.

## 8. Gap-To-Plan Mapping

| Gap | Primary plan doc |
| --- | --- |
| Standalone desktop shell | `docs/agents/plans/2026-04-18-agent-standalone-desktop-architecture.md` |
| Operator auth | `docs/agents/plans/2026-04-18-agent-review-and-corpus-growth-spec.md` |
| Runtime config and startup health | `docs/agents/plans/2026-04-18-agent-standalone-desktop-architecture.md` |
| Demo resilience | `docs/agents/plans/2026-04-18-agent-demo-resilience-and-cache-spec.md` |
| Upload/orchestration workflow | `docs/agents/plans/2026-04-18-agent-tool-contracts-and-upload-flows.md` |
| Promotion friction | `docs/agents/plans/2026-04-18-agent-review-and-corpus-growth-spec.md` |
| Transactional review storage | `docs/agents/plans/2026-04-18-agent-review-and-corpus-growth-spec.md` |
| Entity-resolution UI | `docs/agents/plans/2026-04-18-agent-review-and-corpus-growth-spec.md` |
| Scientist-to-review handoff | `docs/agents/plans/2026-04-18-agent-review-and-corpus-growth-spec.md` |
| Desktop-local cache strategy | `docs/agents/plans/2026-04-18-agent-demo-resilience-and-cache-spec.md` |
| Stable app/backend contract usage | `docs/agents/plans/2026-04-18-agent-tool-contracts-and-upload-flows.md` |
| Investor-readable UI hierarchy | `docs/agents/plans/2026-04-18-agent-pitch-ui-system-spec.md` |
| Evidence-level retrieval | `docs/agents/plans/2026-04-18-agent-multimodal-extraction-rag-architecture.md` |
| Multimodal extraction planning | `docs/agents/plans/2026-04-18-agent-multimodal-extraction-rag-architecture.md` |
| Validator/observer architecture | `docs/agents/plans/2026-04-18-agent-multimodal-extraction-rag-architecture.md` |
| Proof framework for the pitch build | `docs/agents/plans/2026-04-18-agent-evals-and-proof-spec.md` |

## 9. Definition Of Done For This Documentation Wave

This gap report is considered closed for Wave 1 when:

- every high-severity gap has a decision-complete plan doc
- the plan-set index defines dependency order across the full set
- the hackathon/pitch track is clearly separated from the longer-term RAG research track
- future implementation can start from the docs without relying on chat history

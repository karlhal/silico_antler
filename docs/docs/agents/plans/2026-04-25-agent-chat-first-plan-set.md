---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent docs product UX planning
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-conversational-run-loop-spec.md
  - ./2026-04-25-agent-recognition-and-confirmation-spec.md
  - ./2026-04-25-agent-presentation-motion-and-component-system-spec.md
  - ./2026-04-25-agent-hardware-and-legacy-access-spec.md
  - ./2026-04-25-agent-result-detail-and-dummy-surrogate-spec.md
  - ./2026-04-23-agent-lovable-ui-integration-plan.md
  - ./2026-04-23-agent-ui-refinement-slices.md
---

# Agent Chat-First Transformation Plan Set

## Goal and Success Criteria

Create a decision-complete plan set for transforming `apps/agent` from a mixed workflow/report interface into a premium chat-first scientist copilot that can sell to both lab buyers and VC audiences.

Success means:

- the first user action is a natural-language prompt, not staged form completion
- analyte recognition becomes visible during the input flow, with chemistry-aware feedback
- the agent produces a clear in-chat implementation plan before any run starts
- execution requires explicit user confirmation
- completed runs remain conversation-first, with inline result cards and popup detail views
- the shipped app no longer exposes `/studio` or `/studio/classic` to normal users
- the UI uses existing shadcn/Radix primitives plus intentional motion rather than custom one-off component stacks
- the most cinematic motion is concentrated in high-value moments while evidence and trust surfaces remain sober and credible

## Scope

This plan set coordinates six implementation specs:

1. `2026-04-25-agent-chat-first-plan-set.md`
2. `2026-04-25-agent-conversational-run-loop-spec.md`
3. `2026-04-25-agent-recognition-and-confirmation-spec.md`
4. `2026-04-25-agent-presentation-motion-and-component-system-spec.md`
5. `2026-04-25-agent-hardware-and-legacy-access-spec.md`
6. `2026-04-25-agent-result-detail-and-dummy-surrogate-spec.md`

The implementation boundary is primarily `apps/agent`, with design inspiration from `apps/desktop` and no direct business-logic imports across app boundaries.

## Explicit Non-Goals

- no real surrogate model integration in this wave
- no direct imports of desktop run logic, predictors, or optimizer orchestration into `apps/agent`
- no public `Studio preview` or `Classic shell` affordances in the shipped product
- no rewrite of recommendation scoring or trust payload semantics unless a focused later task explicitly requires it
- no custom rebuild of primitives that already exist in the shadcn/Radix stack or can be added through CLI

## Current State

The current app already provides real scientific value:

- `apps/agent/src/components/dashboard/DashboardView.tsx` has an anchored composer, inline clarification workspace, live run surface, and a report workspace
- `apps/agent/src/hooks/useAgentWorkflow.ts` already owns clarification, runtime health, cached recovery, reruns, and recommendation orchestration
- `apps/agent/src/lib/api.ts` already exposes SMILES/name resolution and recommendation clarification/run endpoints
- `apps/agent/src/App.tsx` still exposes `/studio` and `/studio/classic`
- `apps/desktop` already has prediction and operating-window concepts that can inform a later surrogate-testing UX

The gap is not missing scientific capability. The gap is product framing, interaction quality, and pitch clarity.

## Decision-Complete Implementation Approach

### Product Thesis

The default agent experience should optimize for:

- VC-first wow in first impression, recognition, confirmation, and result reveal moments
- lab credibility in evidence, trust, provenance, and operational editing surfaces

The correct product shape is a conversation-led workspace with strong structured reveals, not a generic chat app and not a classic dashboard.

### Dependency Order

1. `agent-chat-first-plan-set`
2. `agent-conversational-run-loop-spec`
3. `agent-recognition-and-confirmation-spec`
4. `agent-presentation-motion-and-component-system-spec`
5. `agent-hardware-and-legacy-access-spec`
6. `agent-result-detail-and-dummy-surrogate-spec`

Why this order:

- the run-loop spec locks the product state model before visual refinement
- recognition and confirmation rules define the highest-leverage pre-run behavior
- motion and component rules must be fixed before UI work starts so engineers do not hand-roll primitives or overbuild animation
- hardware and legacy access must be specified after the transcript and confirmation model is settled
- result detail and dummy surrogate should be specified after the conversation and popup patterns are fixed

### Implementation Order

Phase 1: conversational shell and transcript model

- reframe the dashboard into a chat-first workspace
- add transcript-native run states

Phase 2: inline analyte recognition and chemistry preview

- surface recognized analytes during input
- bind structure previews to the existing SMILES-resolution path

Phase 3: in-chat implementation-plan and explicit confirmation

- show recognized fields, provenance state, unresolved items, and explicit run confirmation

Phase 4: motion and component-system upgrade

- add missing shadcn primitives intentionally
- add `framer-motion`
- implement app-local typewriter behavior

Phase 5: hardware modal and structured escape hatches

- keep hardware editing secondary and tied to the confirmation summary
- remove public legacy shell entry points

Phase 6: inline result cards, popup deep views, and dummy surrogate

- keep finished runs in the transcript
- add method-detail popup flow
- add simulated desktop-inspired surrogate next step

Phase 7: separate developer build for legacy shells

- normal users cannot discover legacy routes
- developers retain an intentional build/runtime path

## Initial Audit Snapshot (2026-04-23)

- `apps/agent/src/App.tsx` directly exposes `/studio` and `/studio/classic`, which conflicts with the shipped-product success criteria and the later legacy-access phases.
- `apps/agent/src/pages/Dashboard.tsx` passes public `onOpenStudio` and `onOpenClassicStudio` actions into the main UI, and `apps/agent/src/components/dashboard/DashboardView.tsx` renders both affordances in the primary header.
- `apps/agent/src/components/dashboard/DashboardView.tsx` is the current monolith for composer, clarification, live run, report, recent runs, and settings-sheet UI; phases 2-6 should decompose it instead of growing the file further.
- `apps/agent/src/hooks/useAgentWorkflow.ts` already owns validation, clarification, runtime health, caching, reruns, and restore. This matches the plan-set requirement that transcript state be derived from existing workflow logic rather than replacing it.
- `apps/agent/src/lib/api.ts` already provides the clarify and SMILES-resolution calls needed for recognition and implementation-plan work, so no new backend contract is required to start phases 2-3.
- `apps/agent/components.json` already points shared primitives at `@/studio/components/ui`; this supports phase 4 reuse, but it also means phase 4 must avoid creating a third primitive tree under `src/components/ui`.

## Short Execution Checklist

- `2026-04-25-agent-chat-first-plan-set.md`: keep the implementation boundary in `apps/agent`, convert the default product shape to transcript-first, and treat public legacy exposure removal as a required shipped-product gate rather than optional cleanup.
- `2026-04-25-agent-conversational-run-loop-spec.md`: introduce a transcript view-model layer above `useAgentWorkflow`, keep it reconstructible from cached and restored state, and pull new chat surfaces out of `apps/agent/src/components/dashboard/DashboardView.tsx`.
- `2026-04-25-agent-recognition-and-confirmation-spec.md`: add recognized-field and provenance types, wire analyte recognition to the existing SMILES-resolution path, and show an implementation-plan turn before any run starts.
- `2026-04-25-agent-presentation-motion-and-component-system-spec.md`: reuse `@/studio/components/ui`, add only missing shadcn primitives, install `framer-motion`, and keep any typewriter logic app-local and deterministic.
- `2026-04-25-agent-hardware-and-legacy-access-spec.md`: replace the dashboard-style settings surface with transcript-linked secondary edits, add a dev-only legacy exposure flag, and gate both routing and navigation for `/studio` and `/studio/classic`.
- `2026-04-25-agent-result-detail-and-dummy-surrogate-spec.md`: keep results inline in the thread, move deep inspection into popup detail views, and model surrogate follow-up with clearly labeled app-local dummy types only.

## Expected Phase 2-6 Touch Files

- Phase 2 likely touches `apps/agent/src/types/index.ts`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/components/dashboard/DashboardView.tsx`, and new transcript or recognition components under `apps/agent/src/components/`.
- Phase 3 likely touches `apps/agent/src/types/index.ts`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/components/dashboard/DashboardView.tsx`, and new implementation-plan or transcript view-model helpers under `apps/agent/src/lib/` or `apps/agent/src/components/`.
- Phase 4 likely touches `apps/agent/package.json`, `apps/agent/components.json`, `apps/agent/src/index.css`, `apps/agent/src/studio/components/ui/*` via reuse, and new motion or typewriter helpers under `apps/agent/src/lib/` or `apps/agent/src/components/ui/`.
- Phase 5 likely touches `apps/agent/src/App.tsx`, `apps/agent/src/lib/agentRuntime.ts`, `apps/agent/src/lib/appNavigation.ts`, `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/components/dashboard/DashboardView.tsx`, and any legacy-enabled dev script or env docs needed inside `apps/agent`.
- Phase 6 likely touches `apps/agent/src/types/index.ts`, `apps/agent/src/hooks/useAgentWorkflow.ts`, `apps/agent/src/pages/Dashboard.tsx`, `apps/agent/src/components/dashboard/DashboardView.tsx`, and new result-detail or dummy-surrogate components under `apps/agent/src/components/` plus app-local helpers under `apps/agent/src/lib/`.

## Conflict Notes: `/studio` and `/studio/classic`

- Current conflict: `apps/agent/src/App.tsx` routes both legacy paths unconditionally for any signed-in user.
- Current conflict: `apps/agent/src/pages/Dashboard.tsx` and `apps/agent/src/components/dashboard/DashboardView.tsx` surface both legacy paths as first-class header actions.
- Current conflict: legacy studio surfaces cross-link back to each other internally, so hiding only the new-shell header buttons would not satisfy the plan set.
- Constraint for later phases: gating must happen at route resolution and navigation entry points, with a dedicated `VITE_AGENT_ENABLE_LEGACY_STUDIO`-style flag defaulting off for shipped builds.

### Supersession Rule

This plan set supersedes older overlapping docs for this transformation. Older docs may still be referenced for historical rationale, but this set becomes the source of truth for the 2026-04-23 chat-first product direction.

## Validation Matrix

Documentation phase:

- `npm run agent:harness:check`

Implementation minimum once work begins:

- `cd apps/agent && npm run build`

Cross-spec QA requirements:

- analyte recognition appears during prompt entry or immediately on submit
- structure previews appear when SMILES resolution succeeds
- implementation-plan summary is visible before execution
- no run starts without explicit confirmation
- results remain in the conversation thread
- popup detail view and dummy surrogate flow are clearly labeled and reachable
- legacy routes are absent from the normal build and available only in the dedicated dev build

## Risks and Rollback Strategy

- Risk: cinematic motion pushes the app into “fake AI demo” territory.
- Risk: chat-first framing hides scientific precision or editable state.
- Risk: legacy studio access is hidden in UI but not truly isolated at build/runtime level.
- Risk: engineers bypass existing primitives and create a third UI system inside `apps/agent`.

Rollback and mitigation:

- concentrate motion in a few moments and keep trust/evidence surfaces visually calm
- require a structured implementation-plan turn before run start so recognized state stays inspectable
- enforce dev-only legacy exposure through explicit build/runtime flags, not convention
- require shadcn/Radix reuse and CLI-first component additions in the component-system spec

## Decision Notes

- 2026-04-23: default product mode is chat-first with structured escape hatches, not pure chat
- 2026-04-23: completed runs remain transcript-first rather than switching to a report-first workspace
- 2026-04-23: dummy surrogate testing is included as a next-step UX only and must remain simulated in v1
- 2026-04-23: legacy `/studio` and `/studio/classic` belong in a separate developer build, not in the shipped product surface

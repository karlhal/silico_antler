---
status: draft
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent chat UX workflow state
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-chat-first-plan-set.md
  - ./2026-04-25-agent-recognition-and-confirmation-spec.md
---

# Agent Conversational Run Loop Spec

## Goal and Success Criteria

Define the primary chat-first workflow for `apps/agent` so the recommendation experience feels like a premium scientist copilot instead of a staged dashboard.

Success means:

- the first interaction is a natural-language prompt
- the agent can respond with recognition feedback, clarification questions, and a structured implementation plan inside one transcript
- the run starts only after explicit user confirmation
- run progress and results remain in the same thread
- structured editing remains available, but only as a secondary escape hatch

## Scope

- `apps/agent/src/App.tsx`
- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- new chat/transcript view-model helpers and presentational components in `apps/agent/src/components`

## Explicit Non-Goals

- no general-purpose agent memory or multi-threaded project system
- no replacement of backend recommendation semantics
- no replacement of the current scientific workflow hook with a totally new orchestration backend
- no report-first navigation mode for the completed run surface

## Current State

Today the app is already partially chat-adjacent:

- the anchored composer is the primary input surface
- clarification prompts already render inline above the main report
- live runs and completed reports are still treated as separate workspaces
- the current layout still reads as a dashboard with a composer attached, not as a conversation-led product

## Decision-Complete Implementation Approach

### Core Conversation Lifecycle

The primary run lifecycle is:

1. user types a natural-language request
2. composer parsing and recognition surface early chemistry/context understanding
3. agent emits recognition feedback in-thread
4. agent asks clarifying questions if needed
5. agent builds an implementation-plan turn
6. user confirms explicitly
7. run progress is shown as transcript-native turns
8. result cards are appended into the same thread
9. user may open a result popup or revise and rerun from the same thread

### Transcript Item Types

The app should introduce a transcript model with these item types:

- `user_turn`
- `agent_typing_turn`
- `recognition_turn`
- `clarification_turn`
- `implementation_plan_turn`
- `run_confirmation_turn`
- `run_progress_turn`
- `result_card_cluster`
- `post_run_cta_turn`

The transcript must be deterministic enough that the same workflow state can be reconstructed after refresh or cached-run restoration without inventing hidden agent state.

### Structured Run-Draft Summary

The implementation-plan turn is mandatory before execution. It must show exactly what the system believes it understands.

Required fields in the implementation-plan summary:

- analyte or analytes
- matrix
- impurities, if present
- detector or MS requirement
- runtime limit
- source mode
- hardware summary
- unresolved items
- inferred defaults

Each field must carry provenance/status:

- `provided`
- `recognized`
- `inferred`
- `missing`

This is the core anti-magic safeguard. The app must never jump from “agent understood something” straight to “run started” without showing the recognized plan.

### Confirmation Semantics

The run-confirmation turn must be explicit and user-triggered.

Rules:

- no implicit run on recognition success
- no implicit run after clarification answer unless the user confirms
- reruns also use explicit user confirmation when the recognized plan changed materially
- a confirm action may be labeled as `Confirm and run`, but the UI copy can still present the moment as an implementation-plan approval

### Clarification Rules

Clarification turns are part of the conversation, not detached forms.

Rules:

- backend clarifications and local missing-constraint prompts use one common transcript pattern
- the agent must show what it is waiting on and how that answer affects readiness
- skipping a clarification is allowed only when the workflow already supports proceeding
- any skipped field remains visible as `missing` or `inferred` in the implementation-plan turn

### Integration With Existing Workflow Logic

`useAgentWorkflow` remains the scientific orchestration layer in v1.

The UI layer should:

- keep using the existing recommendation, clarification, runtime, caching, and rerun behavior
- translate workflow state into transcript items instead of separate dashboard sections
- avoid inventing frontend-only scientific logic

Recommended split:

- `useAgentWorkflow` stays responsible for recommendation orchestration
- a new transcript/view-model layer derives the chat presentation
- recognized field summaries and transcript items are computed from workflow state plus prompt-recognition state

### Post-Run Behavior

Completed runs remain conversation-first.

Rules:

- do not switch the app to a report-first full-page mode after completion
- append result cards into the thread
- allow revising, rerunning, and opening detail popups without abandoning the conversation context

## Validation Matrix

- `cd apps/agent && npm run build`

Required QA scenarios:

- empty-state prompt to implementation-plan flow
- clarification loop with one or more missing fields
- explicit confirmation before run start
- rerun with revised recognized fields
- cached or restored run still reconstructs a coherent transcript
- degraded, timeout, or empty-result outcomes remain inspectable in the thread

## Risks and Rollback Strategy

- Risk: transcript state becomes fragile or duplicated alongside existing workflow state.
- Risk: chat-first framing makes advanced users feel they lost control.
- Risk: confirmation becomes redundant or annoying if not tuned carefully.

Mitigations:

- keep workflow orchestration in `useAgentWorkflow` and derive transcript state from it
- keep secondary edit affordances visible from the implementation-plan turn
- only require fresh confirmation when the plan is new or materially revised

Rollback path:

- if the full transcript model destabilizes the app, keep the same recognized-plan and result-card concepts but temporarily render them inside the existing dashboard shell before reattempting the full chat-first shell

## Decision Notes

- 2026-04-23: the transcript is the primary product surface before, during, and after a run
- 2026-04-23: the implementation-plan turn is the mandatory execution gate
- 2026-04-23: structured editing remains available, but the default product story is conversational

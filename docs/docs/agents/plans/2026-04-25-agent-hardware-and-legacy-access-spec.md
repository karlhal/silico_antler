---
status: completed
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent hardware editing legacy studio routing
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-chat-first-plan-set.md
  - ./2026-04-25-agent-conversational-run-loop-spec.md
---

# Agent Hardware and Legacy Access Spec

## Goal and Success Criteria

Define how secondary editing works in the chat-first agent and how legacy studio/classic routes are kept out of the shipped product.

Success means:

- hardware remains easy to reach from the composer without taking over the product
- recognized details can be revised from the implementation-plan moment
- edits update the current transcript state rather than launching a separate wizard
- normal users cannot discover `/studio` or `/studio/classic`
- developers still have a deliberate build/runtime path to those legacy surfaces

## Scope

- hardware entry points and modal behavior in `apps/agent`
- transcript-linked secondary edits
- dev-only legacy route exposure
- build/runtime flag strategy

## Explicit Non-Goals

- no OS-native secondary window for hardware in this wave
- no public secret-URL convention for legacy access
- no requirement to merge legacy studio shells into the new default product

## Current State

Today:

- the dashboard exposes public buttons for `Studio preview` and `Classic shell`
- `apps/agent/src/App.tsx` routes directly to `/studio` and `/studio/classic`
- `operatorModeEnabled` exists in runtime config, but it is not yet the product-level rule that hides legacy routes from normal users
- hardware and structured inputs are still embedded in dashboard-oriented settings surfaces rather than a deliberately secondary editing model

## Decision-Complete Implementation Approach

### Hardware Editing Model

Hardware stays secondary and composer-adjacent.

Rules:

- keep a persistent hardware hint near the composer
- clicking it opens an in-app modal, not a separate OS window
- the modal contains the system, instrument, solvent, and related run-context editing needed for the draft
- the modal closes back into the transcript and updates the current implementation-plan summary

The hardware surface should feel like a precise utility edit, not like the app switching modes.

### Secondary Edit Behavior

If the agent recognized something incorrectly:

- the user may revise hardware from the hardware modal
- the user may revise analyte, matrix, or other recognized details from an implementation-plan action
- these edits mutate the current draft and update the current or latest implementation-plan turn
- the transcript should not branch into multiple competing draft flows

### Legacy Access Rule

The shipped build must not expose:

- `Studio preview`
- `Classic shell`
- any discoverable route or menu item leading to `/studio` or `/studio/classic`

Legacy access must exist only in a separate developer build/runtime mode.

### Build and Runtime Shape

Use an explicit dev-only exposure flag:

- `VITE_AGENT_ENABLE_LEGACY_STUDIO=false` by default
- dedicated developer build or dev script sets it to `true`

Required behavior:

- when the flag is `false`, normal routing ignores or redirects legacy routes away from the shipped product surface
- when the flag is `true`, developers may access legacy routes intentionally
- runtime/operator concepts may be reused if helpful, but the source of truth is the dedicated dev-only exposure flag, not undocumented convention

Recommended implementation follow-up:

- add dedicated dev entry points or scripts for the legacy-enabled build so developers do not toggle the product manually

### UI Summary Update Rules

When the hardware modal closes:

- the composer-adjacent summary updates immediately
- the implementation-plan turn updates immediately
- field provenance remains visible if hardware edits changed inferred or missing state

## Validation Matrix

- `cd apps/agent && npm run build`

Required QA scenarios:

- hardware hint is always reachable near the composer
- hardware modal opens and closes without losing transcript context
- hardware edits update the implementation-plan summary
- revising a recognized field updates the current plan rather than launching a separate workflow
- normal build has no legacy studio/classic navigation or discoverable access
- dev build exposes legacy routes intentionally and only there

## Risks and Rollback Strategy

- Risk: the modal becomes a hidden full settings app and undermines the chat-first story.
- Risk: legacy routes remain technically reachable in normal builds despite hidden buttons.
- Risk: draft mutation after modal edits becomes confusing in the transcript.

Mitigations:

- keep the hardware surface scoped to run-relevant edits only
- gate route exposure at build/runtime level, not only at navigation level
- update a single current implementation-plan summary rather than appending duplicate drafts

Rollback path:

- if full route gating slips, temporarily remove all public legacy affordances first and defer direct-route exposure until the dev-only build flag is in place

## Decision Notes

- 2026-04-23: hardware opens as a modal everywhere in v1
- 2026-04-23: legacy studio/classic access belongs in a separate developer build
- 2026-04-23: secondary edits update the current recognized plan instead of creating parallel wizard flows

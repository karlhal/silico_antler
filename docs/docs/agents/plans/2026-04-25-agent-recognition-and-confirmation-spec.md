---
status: draft
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent prompt recognition chemistry preview pre-run confirmation
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-chat-first-plan-set.md
  - ./2026-04-25-agent-conversational-run-loop-spec.md
---

# Agent Recognition and Confirmation Spec

## Goal and Success Criteria

Define the chemistry-aware pre-run UX so the agent visibly recognizes analytes and presents a trustworthy implementation-plan turn before execution.

Success means:

- recognizable analytes trigger visible inline feedback during prompt entry or immediately on submit
- successful recognition surfaces a structure preview from the existing SMILES-resolution path
- unresolved or ambiguous recognition is explicit
- the implementation-plan turn shows exactly what the agent recognized, inferred, or still needs
- secondary edits update the same plan rather than creating a parallel workflow

## Scope

- prompt parsing and recognition view models in `apps/agent`
- analyte recognition UI near the composer and in the transcript
- pre-run implementation-plan turn
- field provenance display rules

## Explicit Non-Goals

- no new backend recognition service in this wave
- no direct molecular drawing engine imported from another app boundary
- no hidden autofill that skips visibility of recognized values

## Current State

The current app already has pieces to build from:

- `apps/agent/src/lib/api.ts` already supports SMILES name resolution
- the dashboard already has clarification and runtime prompts
- the app does not yet expose a rich recognized-entity layer or a visible “agent understood this” summary before runs start

## Decision-Complete Implementation Approach

### Recognition Surface Behavior

When the prompt contains a recognizable analyte, the app should render a recognition surface close to the composer and reflect it in the transcript context.

The recognition surface must show:

- analyte display name
- recognition state
- resolved SMILES or unresolved status
- structure preview when resolution succeeds

Recognition states:

- `recognizing`
- `recognized`
- `ambiguous`
- `unresolved`
- `error`

The UI must never flatten ambiguous or unresolved states into silent failure.

### Recognition Data Model

Each recognized field should carry:

- `field`
- `value`
- `status`
- `provenance`
- `confidence_label`
- `source_text_span` when available

For analytes specifically, add:

- `resolved_smiles`
- `resolved_name`
- `structure_preview_state`
- `lookup_source`
- `lookup_error`

### Structure Preview Rules

The first implementation route is the existing SMILES-resolution path.

Rules:

- if resolution succeeds, show a compact structure preview inline
- if resolution is still pending, reserve the visual slot and show a meaningful loading state
- if resolution fails, keep the analyte visible but mark it unresolved
- if the prompt contains multiple analytes, each analyte gets its own recognition state and preview treatment

### Implementation-Plan Turn

The agent must present a premium structured turn before the run starts.

Required content:

- title framing the step as an implementation plan or run draft
- structured field rows/cards for recognized context
- explicit unresolved or inferred items
- action buttons:
  - `Confirm and run`
  - `Revise hardware`
  - `Revise recognized details`
  - `Answer unresolved question`

The plan turn should feel like an approval checkpoint, not like a hidden machine-state dump.

### Field Provenance Rules

Every displayed field in the plan summary must use one of:

- `provided`
- `recognized`
- `inferred`
- `missing`

Display rules:

- `provided` reads as user-controlled truth
- `recognized` reads as agent-detected from the prompt
- `inferred` reads as a default or assumption and should be visually softer
- `missing` reads as blocking or unresolved and should be visually strongest among non-success states

### Recognition Micro-Interactions

Required motion moments:

- analyte text or token morphs into a recognized chemistry card
- structure preview fades/scales in after resolution
- recognized fields reveal in a short stagger inside the implementation-plan turn

Reduced-motion rules:

- no morphing transforms
- use simple opacity and state transitions only
- typewriter and recognition motion must resolve instantly when reduced motion is enabled

### Edit and Update Behavior

When the user revises hardware or recognized details:

- the same implementation-plan turn updates in place or is superseded by a clearly newer version
- the transcript should not fork into parallel conflicting drafts
- any revised field must retain updated provenance status

## Validation Matrix

- `cd apps/agent && npm run build`

Required QA scenarios:

- recognized analyte with successful structure preview
- recognized analyte with pending resolution state
- ambiguous analyte state
- failed recognition state
- mixed provided, recognized, inferred, and missing fields in one implementation-plan turn
- plan-turn update after editing a recognized field

## Risks and Rollback Strategy

- Risk: over-aggressive recognition misleads users by appearing too confident.
- Risk: inline chemistry cards overwhelm the composer visually.
- Risk: field provenance becomes too subtle and users cannot tell what was inferred.

Mitigations:

- keep unresolved and ambiguous states explicit
- constrain recognition UI to a compact but premium surface
- require provenance badges or labels on every plan-summary field

Rollback path:

- if continuous recognition during typing is unstable, fall back to immediate post-submit recognition while keeping the same visible recognition and plan-summary contract

## Decision Notes

- 2026-04-23: recognition visibility is a product requirement, not an optional enhancement
- 2026-04-23: structure preview must use the existing SMILES-resolution path first
- 2026-04-23: implementation-plan approval is the primary anti-magic control surface

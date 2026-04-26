---
status: draft
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent post-run result UX popup details dummy surrogate
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-chat-first-plan-set.md
  - ./2026-04-25-agent-conversational-run-loop-spec.md
---

# Agent Result Detail and Dummy Surrogate Spec

## Goal and Success Criteria

Define the post-run UX for the chat-first agent so completed recommendations stay inside the conversation, offer deeper popup inspection, and lead into a believable but simulated surrogate-testing next step.

Success means:

- recommendation results appear as inline cards in the transcript
- users can inspect a method deeply without switching the whole app into report mode
- the popup detail view is rich enough to replace today’s page-level detail emphasis
- the surrogate next step feels plausible and valuable while remaining explicitly simulated in v1

## Scope

- result-card cluster UI in `apps/agent`
- popup method-detail view
- dummy surrogate flow modeled after desktop prediction and operating-window concepts

## Explicit Non-Goals

- no real sidecar calls
- no real model bundle loading
- no cross-app import of desktop run orchestration
- no full page-level report-first route as the primary completed state

## Current State

The current app already exposes rich recommendation data:

- recommendation titles, ranking, and score summaries
- trust, evidence, provenance, and warnings
- runner-up comparison context

What is missing is a conversation-first post-run packaging of that information and a next-step UX that bridges toward the desktop surrogate story.

## Decision-Complete Implementation Approach

### Result Cards in the Transcript

Completed runs should append a result-card cluster into the conversation thread.

Each result card must show:

- title
- rank or fit
- short why-it-fits summary
- trust or evidence summary

The first card should feel like the primary recommendation. Runner-up cards remain visible but secondary.

### Popup Deep View

Clicking a result card opens a modal or popup detail view.

The popup must include:

- method summary
- evidence preview
- provenance
- trust and validation posture
- warnings and scaling notes
- comparison context

This popup becomes the detailed inspection surface instead of requiring the whole app to flip into a report-first mode.

### Surrogate Branch

Inside the popup, the user is asked whether they want to test the method in the AI surrogate.

Rules:

- this is never automatic
- the CTA is a deliberate next step after reading the method detail
- the resulting surrogate flow is simulated/demo-only in v1

### Dummy Surrogate Scope

The v1 surrogate flow should borrow concepts from `apps/desktop`:

- predicted output
- operating-window style framing
- scan or evaluation next-step concept

But the implementation must not:

- call the real sidecar
- import desktop business logic directly
- imply scientific validity beyond a demo preview

Every surrogate output state must be labeled clearly as simulated or demo-only.

### Suggested Dummy Surrogate State Model

Introduce agent-local dummy types shaped after desktop concepts:

- `DummySurrogateSession`
- `DummySurrogatePrediction`
- `DummySurrogateWindowScan`
- `DummySurrogateState = idle | launching | ready | failed`

These types should support believable UI composition without creating a hidden dependency on the desktop runtime.

### Motion and Presentation Rules

Result reveal is a high-motion moment.

Allowed emphasis:

- result-card entrance choreography
- popup opening transition
- CTA reveal for surrogate testing

Calm detail areas:

- evidence reading
- trust fields
- warnings
- provenance metadata

## Validation Matrix

- `cd apps/agent && npm run build`

Required QA scenarios:

- completed run appends result cards into the conversation thread
- primary recommendation is visually clear
- popup deep view opens and closes cleanly
- popup shows trust, evidence, provenance, warnings, and comparison context
- surrogate CTA is explicit and never automatic
- dummy surrogate flow remains clearly labeled simulated/demo-only

## Risks and Rollback Strategy

- Risk: result cards oversimplify the scientific richness of the recommendation payload.
- Risk: popup detail views become so dense they recreate the same page-level report problem inside a modal.
- Risk: dummy surrogate language overpromises real scientific capability.

Mitigations:

- keep trust and evidence summaries on the cards, not just marketing copy
- use the popup to structure detail into clear sections instead of one dense dump
- label every surrogate surface as simulated or demo-only

Rollback path:

- if the popup proves too dense initially, ship inline result cards first and keep a simplified detail popup until the full detail composition stabilizes

## Decision Notes

- 2026-04-23: completed runs remain chat-first
- 2026-04-23: popup detail view is the deep-inspection mechanism for v1
- 2026-04-23: surrogate testing is a desktop-inspired simulated next step, not a real runtime integration

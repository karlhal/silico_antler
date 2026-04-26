---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent workflow ux presentation hardening
source_of_truth: docs/agents/execution-plans.md
---

# Agent Workflow And Presentation Hardening

## Goal and Success Criteria

Harden the agent app's core workflow so it feels more usable as a repeated scientific tool rather than a one-shot demo flow.

Success means:

- users can recover, revise, and compare without restarting the whole flow
- validation, failure, and fallback states are more specific and less brittle
- the report view becomes easier to scan and more useful for actual decision-making
- session state can survive refresh or accidental navigation in at least a minimal form

## Scope

- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`
- related typed models and small helper modules under `apps/agent`

## Explicit Non-Goals

- no backend ranking rewrite
- no auth or multi-user persistence requirement in the first slice
- no full notebook/workspace product in this round
- no operator review workflow in this document

## Current State

The current app already has a credible shell, but several behaviors still feel prototype-grade:

- the workflow is strictly linear
- retries jump back to source selection rather than preserving enough state to recover intelligently
- discovery status uses simulated timing delays in addition to the real API call
- the report view is compact and visually strong, but still thin for repeated analysis work
- there is no save, restore, or compare affordance

## Why This Should Happen

The app is already valuable enough that UX friction matters now. The next gains are not only algorithmic. They are operational:

- fewer forced restarts
- better edit loops
- clearer failure recovery
- more legible comparison of candidates

## Decision-Complete Implementation Approach

### Workflow stance

Move from a one-direction staged deck toward a revisable workflow:

- preserve completed inputs while editing downstream choices
- allow users to jump back to specific stages without losing the whole run
- support explicit rerun from current state

### State persistence stance

Add lightweight local session persistence for:

- system specs
- target fields
- source mode
- latest recommendation report metadata

The first slice can use local storage with a clear reset boundary. The goal is resilience, not multi-device sync.

### Validation stance

Upgrade validation from blocking strings to structured field-level guidance:

- show what is missing
- keep the user near the field that needs correction
- distinguish between required, optional, and confidence-improving inputs

### Failure and fallback stance

When runs fail:

- preserve the current inputs
- preserve partial backend diagnostics when safe to show
- distinguish validation failure, empty results, timed-out request, and demo fallback more clearly

### Report stance

Improve the report view for real comparison:

- clearer primary recommendation summary
- side-by-side or step-through comparison between candidates
- explicit "what changed vs alternatives" summaries
- stronger organization of scaled method, score, warnings, and rationale

### Presentation stance

Keep the calm editorial tone, but reduce unnecessary theatricality in workflow transitions. The app should feel fast and reliable first.

## Primary Files And Boundaries

Likely implementation homes:

- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`
- new local persistence and view-model helpers under `apps/agent/src/`

Boundary rule:

- this slice stays frontend-only unless a contract gap is found

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- browser QA for fresh run, rerun, refresh, and failure recovery states
- contract tests only if request/response behavior changes

## Risks and Rollback Strategy

- Risk: persistence introduces stale-state confusion.
- Risk: a more flexible workflow becomes less legible than the current staged deck.
- Risk: comparison UI adds too much density to a previously calm interface.

Rollback:

- keep persistence optional and versioned
- add flexibility in layers so jump-back, restore, and compare can be reverted independently

## Decision Notes

- 2026-04-20: The right direction is "more useful for repeat work," not "more impressive as a demo."
- 2026-04-20: Current artificial step timing is acceptable for demos but should not dominate the long-term product feel.

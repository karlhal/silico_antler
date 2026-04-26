---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development trust evidence
source_of_truth: docs/agents/execution-plans.md
---

# Agent Trust And Evidence Surfacing

## Goal and Success Criteria

Make the agent app's recommendation trust legible by surfacing the evidence, review posture, and ranking rationale already present in backend payloads.

Success means:

- each recommendation clearly communicates why it ranked where it did
- users can inspect evidence snippets, warning posture, and review state without leaving the report view
- local-corpus and open-access recommendations use the same trust vocabulary
- the app stays a rendering client and does not re-implement backend scoring logic

## Scope

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/types/index.ts` only if payload typing needs extension
- `services/method-development` only if recommendation payload shape needs small additions or normalization

## Explicit Non-Goals

- no scoring-algorithm rewrite
- no new retrieval engine
- no broad operator review workflow in this slice
- no attempt to show every raw backend field by default

## Current State

The implementation report is explicit about the current mismatch:

- backend recommendation contracts already include `evidence_snippets`, `match_rationale`, and `review_summary`
- the app currently surfaces only citation, overall score, rationale, and selected scaled method details
- the biggest remaining gap is trust surfacing, not recommendation generation

This means the next useful improvement is presentation and workflow design, not backend invention.

## Why This Should Happen

Silico's product value depends on decision quality and trust. A recommendation that feels opaque will be discounted even if the ranking is good. The current UI already has the right product backbone, but it still hides too much of the "why."

## Decision-Complete Implementation Approach

### Product stance

Trust information should become a first-class report layer, not an afterthought under the winning candidate.

Every candidate should show a compact trust summary at scan level, then allow expansion into deeper explanation.

### Report structure

Add three trust layers:

1. scan layer
2. explanation layer
3. evidence layer

#### Scan layer

Visible without expanding:

- trust state
- validation status
- source mode
- ranking mode
- warning count

#### Explanation layer

Visible on candidate expansion:

- score dimension summary
- `match_rationale` summary
- impurity handling summary
- scaling notes and warnings

#### Evidence layer

Visible in a dedicated expandable region:

- evidence snippets
- source document metadata
- review summary when present
- open-access skip diagnostics when relevant

### Vocabulary stance

Use the backend's own trust concepts and keep them consistent:

- `review_backed`
- `seeded_corpus`
- `open_access_extracted`
- validation status
- manual verification required

Do not invent a second frontend-only trust taxonomy.

### Interaction stance

The default view should remain calm and scannable. Trust depth should be progressively disclosed rather than dumped into one dense panel.

### Contract stance

Prefer small backend normalization over frontend inference. If fields are missing or uneven across modes, fix that in `services/method-development` rather than teaching the app to guess.

## Primary Files And Boundaries

Likely implementation homes:

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/types/index.ts`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/recommendation_engine.py`

Boundary rule:

- method-development owns trust semantics and report fields
- agent owns presentation, progressive disclosure, and copy

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- focused recommendation API tests in `services/method-development`
- `cd services/method-development && uv run pytest -q`

## Risks and Rollback Strategy

- Risk: too much evidence in the default view creates cognitive overload.
- Risk: exposing warnings without context lowers confidence unnecessarily.
- Risk: frontend copy accidentally overstates certainty.

Rollback:

- keep trust UI behind additive panels and collapsible sections
- preserve the existing summary card layout so deeper trust layers can be reduced without removing the report entirely

## Decision Notes

- 2026-04-20: This plan treats trust as the next major product differentiator for the current MVP.
- 2026-04-20: The app should explain backend reasoning, not compete with it.

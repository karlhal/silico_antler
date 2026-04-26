---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development export handoff
source_of_truth: docs/agents/execution-plans.md
---

# Agent Export And Handoff Package

## Goal and Success Criteria

Replace the current dead `Export Analysis` button with a deterministic export package that scientists can hand off, review, and archive outside the app.

Success means:

- the report view exports a real artifact
- exported content includes both recommendation and trust context
- the first slice is deterministic and does not require a new heavyweight backend service
- exported artifacts are explicit about draft versus review-backed status

## Scope

- `apps/agent/src/pages/Dashboard.tsx`
- export assembly utilities in `apps/agent`
- optional backend contract extension only if export payload normalization is needed

## Explicit Non-Goals

- no direct instrument-method file generation
- no email sending workflow in the first slice
- no PDF-perfect publishing pipeline requirement on day one
- no approval or signature workflow

## Current State

The app already presents an `Export Analysis` button in the final report view, but it has no click handler and no artifact model behind it. This is a visible gap in a product that otherwise positions itself as a decision-support tool.

## Why This Should Happen

Scientists rarely finish with a recommendation by just looking at it on screen. They need to:

- share the result
- compare it with current practice
- attach it to notes or project history
- preserve the exact context that produced it

Without export, the product's recommendation loop stops inside the browser.

## Decision-Complete Implementation Approach

### Product stance

The first export should optimize for traceable handoff, not visual perfection.

That means the package should be rich in context and low in ambiguity before it aims for polished PDF output.

### Artifact stance

Phase the export format:

#### Phase 1

- machine-readable JSON
- human-readable Markdown or HTML summary

#### Phase 2

- printable PDF or branded report once the content model is stable

### Content model

The export package should include:

- request summary
- system constraints
- selected source mode
- chosen recommendation
- ranked alternatives summary
- scaled method details
- scaling notes and warnings
- trust state and validation posture
- evidence snippets
- source metadata and citation fields
- timestamp and export version

### Assembly stance

Default to client-side assembly from the existing recommendation payload. This keeps the first slice fast to ship and avoids inventing a dedicated export backend before the content model settles.

If the payload is missing required trust fields, add them to the recommendation contract rather than inventing a second export-only response shape.

### UX stance

The export action should let the user choose the active recommendation explicitly. If multiple candidates exist, the exported package should name both the selected recommendation and the alternative set.

### Trust stance

Every export must state whether the recommendation is:

- review-backed
- seeded corpus
- open-access extracted
- manually verification-required

Exports should never imply laboratory approval.

## Primary Files And Boundaries

Likely implementation homes:

- `apps/agent/src/pages/Dashboard.tsx`
- new export helper modules under `apps/agent/src/`
- `services/method-development/app/recommendation_schemas.py` only if payload normalization is needed

Boundary rule:

- agent owns artifact assembly and download UX in the first slice
- method-development owns source payload completeness, not file generation

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- targeted frontend tests or manual export smoke checks
- `cd services/method-development && uv run pytest -q` only if contract fields change

## Risks and Rollback Strategy

- Risk: exports become too polished before the trust model is stable.
- Risk: exported content overstates scientific certainty.
- Risk: a client-only export drifts from the report view over time.

Rollback:

- keep export assembly driven by the active typed recommendation payload
- phase output formats so Markdown/JSON can ship before any harder PDF path

## Decision Notes

- 2026-04-20: The first win is a trustworthy handoff package, not a beautiful PDF.
- 2026-04-20: Export content should reuse the same trust vocabulary planned for in-app surfacing.

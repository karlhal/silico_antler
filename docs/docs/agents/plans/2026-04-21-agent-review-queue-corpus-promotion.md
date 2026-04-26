---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development review queue corpus promotion
source_of_truth: docs/agents/execution-plans.md
---

# Agent Review Queue And Corpus Promotion

## Goal and Success Criteria

Surface the existing review-record and corpus-promotion backend capabilities through a dedicated operator workflow so strong extracted methods can be reviewed and promoted into the future local corpus.

Success means:

- reviewed extraction work no longer remains backend-only
- an operator can inspect reviewable records, update status, and promote or unpromote corpus entries from a UI surface
- the default scientist workflow stays separate from the operator review workflow
- promotion state becomes visible and auditable

## Scope

- new operator-facing surface inside `apps/agent` or an adjacent route within the same app boundary
- existing review endpoints in `services/method-development`
- recommendation-to-review handoff only where needed to seed the queue

## Explicit Non-Goals

- no public self-serve moderation system
- no role-based auth requirement in the first slice if the surface remains internal/operator-only
- no rewrite of the review-record storage model
- no attempt to expose every backend orchestration control in the first UI pass

## Current State

The backend already supports the lifecycle:

- create review record
- list review records
- fetch a review record
- update review status
- update corpus promotion
- orchestration entrypoint for review-record preparation

Relevant routes already exist under `services/method-development/app/review_records_router.py` and `services/method-development/app/c12_orchestration_router.py`.

The agent app does not surface any of this today.

## Why This Should Happen

This is the compounding loop in the product:

- open-access discovery finds candidate methods
- humans review stronger extractions
- approved records become reusable local-corpus inputs
- future recommendations improve

If this remains backend-only, the product keeps paying the cost of one-off extraction work without getting the full corpus-growth benefit.

## Decision-Complete Implementation Approach

### Product stance

Do not mix review operations directly into the default user discovery flow. Create a distinct operator surface with a different mental model:

- discovery for scientists
- review and promotion for operators

### Workflow stance

The first UI slice should support this sequence:

1. open review queue
2. inspect record metadata, extraction summary, warnings, and provenance
3. update status to draft, approved, or rejected
4. promote approved records into corpus when appropriate
5. see current promotion state and retrieval readiness

### Recommendation handoff

From the recommendation view, support a minimal "send to review" or "open in review queue" action only if it can be done without cluttering the default report.

This should remain secondary to the scientist-facing report.

### Surface stance

Likely shapes:

- a dedicated `/review` route in `apps/agent`
- an operator-only panel behind an environment flag

The route approach is cleaner because it avoids contaminating the main report surface with moderation controls.

### Backend stance

Reuse current endpoints first:

- `POST /source-documents/{source_document_id}/review-records`
- `GET /review-records`
- `GET /review-records/{review_record_id}`
- `POST /review-records/{review_record_id}/status`
- `POST /review-records/{review_record_id}/promotion`
- `POST /c12/review-records/orchestrate`

Only add new endpoints if the current contract proves insufficient for an efficient queue UI.

## Primary Files And Boundaries

Likely implementation homes:

- `apps/agent/src/pages/`
- `apps/agent/src/lib/api.ts`
- `apps/agent/src/types/index.ts`
- `services/method-development/app/review_records_router.py`
- `services/method-development/app/c12_orchestration_router.py`
- related method-development tests

Boundary rule:

- method-development owns review-record state and corpus-promotion semantics
- agent owns queue UX, operator affordances, and progressive disclosure

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- `cd services/method-development && uv run pytest -q`
- manual queue flow QA for create, status change, promote, and unpromote paths

## Risks and Rollback Strategy

- Risk: operator controls leak into the main scientist workflow and create confusion.
- Risk: promotion becomes too easy and pollutes the local corpus.
- Risk: the UI exposes backend complexity faster than users can reason about it.
- **Security Risk (Identified 2026-04-20):** The `/review` route is currently accessible without explicit operator-role authentication. This must be addressed with auth guards (e.g., JWT role check or environment-based gating) before production deployment.
- **Operational Risk (Identified 2026-04-20):** The one-click "Approve & Promote" action reduces friction but increases the risk of accidental corpus pollution. Future iterations should consider adding a confirmation step or mandatory audit notes.

Rollback:

- keep the review surface route-scoped or environment-gated
- preserve backend promotion constraints and avoid frontend-only shortcuts

## Decision Notes

- 2026-04-20: This plan is intentionally operator-facing, not part of the default recommendation MVP.
- 2026-04-20: The value of this slice is product compounding, not public demo polish.

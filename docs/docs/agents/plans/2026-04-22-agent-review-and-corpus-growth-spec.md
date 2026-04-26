---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent services/method-development operator review corpus growth
source_of_truth: docs/agents/execution-plans.md
---

# Agent Review And Corpus Growth Spec

## Goal and Success Criteria

Make the review and corpus-growth loop a first-class product capability without letting it overtake the default scientist workflow.

Success means:

- promising results can be sent into review directly from the main recommendation flow
- operator actions are gated and auditable
- approval and promotion are intentionally separate decisions
- entity-resolution is available before approval
- review persistence is transactional rather than JSON-file based

## Scope

- [ ] send-to-review flow from the recommendation report
- [ ] review queue and record-detail UX
- [ ] auth gating for operator controls
- [ ] approval/promotion behavior
- [ ] entity-resolution workflow
- [x] auditability requirements (Backend SQLite events implemented)
- [x] persistence migration from JSON to SQLite-backed review storage

## Explicit Non-Goals

- no attempt to make the review queue the primary scientist workflow
- no broad RBAC platform implementation beyond what is needed for operator gating
- no speculative multi-user workflow beyond transactional correctness and audit events

## Current State

Already available in backend:

- review-record creation, listing, fetch, approve, reject, promote, and demote routes
- `entity_resolutions` in the approval request contract
- review-to-corpus materialization and retrieval reuse
- C12 orchestration that can prepare or reuse review records

Current gaps:

- `/review` access is not sufficiently gated
- review notes are still too blunt in the UI flow
- promotion is too easy and not deliberately separated enough
- entity-resolution is backend-capable but not app-capable
- persistence still uses JSON-backed `InMemoryReviewRecordStore`

## Decision-Complete Implementation Approach

### Product stance

Review exists to make the recommendation engine better over time.

It should therefore feel like:

- a deliberate quality loop
- a controlled operator action
- a product advantage

It should not feel like:

- an admin afterthought
- a public moderation screen
- a hidden backend-only capability

### Access-control stance

Operator actions must be gated.

Wave 1 requirement:

- gate operator surfaces behind explicit operator mode plus authenticated access

Minimum acceptable implementation:

- runtime-configured operator-mode enablement
- authenticated user check before showing operator controls
- deny-by-default on direct `/review` entry when operator conditions are not satisfied

The app should not rely solely on “security through hidden links.”

### Scientist-to-review handoff

From the recommendation report, the user must be able to trigger:

- `Send to review`

This action should:

- create or prepare a review record from the selected source document or orchestration path
- confirm success to the user
- expose the record in the operator queue

The default scientist user does not need to enter the review queue itself.

### Review queue UX

The operator queue should support:

- sortable list of review records
- filters by status and promotion posture
- clear display of validation state and retrieval readiness
- record-detail screen with evidence, extracted method, unresolved entities, review history, and operator actions

### Approval vs promotion stance

Approval and promotion must be separate decisions.

Required behavior:

- `Approve` means the extraction is acceptable and frozen as reviewed
- `Promote` means the approved record should actively influence future corpus-backed recommendations

Required UX rules:

- approving requires rationale text
- promoting requires rationale text plus confirmation
- “approve and promote” can exist as an explicit accelerated path, but it must still show both intents and require confirmation

### Entity-resolution workflow

Before approving a record with unresolved molecular entities, the operator must be able to:

- inspect unresolved or weakly linked entities
- provide corrected SMILES and optional display names
- re-run validation against the updated record draft

Required UX behavior:

- unresolved entities are visible above approval controls
- approval is blocked while required entity linkages remain unresolved
- the operator sees whether the record becomes retrieval-ready after resolution

### Auditability requirements

Every operator mutation should create an audit event.

Minimum event types:

- review created
- review approved
- review rejected
- promotion enabled
- promotion removed
- entity resolutions applied

Each event should capture:

- event type
- timestamp
- actor identifier if available
- free-text rationale when provided
- changed payload summary

### Persistence migration stance

Replace JSON-backed review persistence with SQLite-backed transactional storage.

Required architectural rule:

- keep the current store interface shape stable enough that router behavior does not need a product-level rewrite

Recommended implementation:

- introduce a SQLite-backed review store implementation
- keep one row for current record state
- keep append-only event rows for audit history

Recommended table set:

- `review_records`
- `review_record_events`

This is enough for Wave 1. Additional normalization can wait.

### Concurrency stance

Mutations must happen in transactions so that:

- approval and promotion state stay consistent
- event logs and current-state rows cannot diverge
- concurrent edits do not silently overwrite each other

If optimistic concurrency is needed, use `updated_at` or version checks on mutation.

## Interfaces / Contracts / Types Affected

### Existing routes to keep

- `/review-records`
- `/review-records/{id}`
- `/review-records/{id}/approve`
- `/review-records/{id}/reject`
- `/review-records/{id}/promote`
- `/review-records/{id}/demote`

### Frontend UX additions

- send-to-review action from recommendation report
- rationale inputs for approval and promotion
- entity-resolution editor using existing `ReviewRecordApproveRequest.entity_resolutions`

### Backend storage

- new SQLite-backed review store preserving current HTTP contract semantics

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- `cd services/method-development && uv run pytest -q`
- tests for:
  - approval requiring rationale
  - promotion requiring confirmation path
  - entity-resolution leading to retrieval-ready state
  - promotion changing local-corpus retrieval outcome
  - concurrent mutation safety

## Risks and Rollback

- Risk: review tooling overwhelms the scientist UX.
- Risk: auth gating is too weak and leaves operator paths exposed.
- Risk: SQLite migration changes route behavior or breaks review-materialization semantics.

Rollback:

- keep UI and storage changes separated
- preserve HTTP contract behavior while swapping store implementation underneath
- if richer queue UX slips, prioritize auth, rationale capture, promotion split, and storage migration first

## Decision Notes

- 2026-04-21: Review and promotion are distinct product actions.
- 2026-04-21: Entity-resolution is required before approval for unresolved retrieval-critical chemistry.
- 2026-04-21: Review persistence moves from JSON-backed in-memory state to SQLite-backed transactional state.

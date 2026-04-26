---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent services/method-development apps/api contracts uploads
source_of_truth: docs/agents/execution-plans.md
---

# Agent Tool Contracts And Upload Flows

## Goal and Success Criteria

Define the canonical app/backend contract usage for the standalone agent app so implementation uses stable routes, consistent payloads, and upload-first flows that work in a hosted-service architecture.

Success means:

- the app uses canonical non-deprecated routes
- route usage is aligned with standalone desktop constraints
- source-document upload behavior is explicit
- request and response detail modes are used intentionally
- frontend types and payload shaping include missing high-value fields already supported by the backend

## Scope

- recommendation route usage
- source-document registration/upload contracts
- review-record and C12 orchestration usage
- response-detail behavior
- frontend request-shape additions

## Explicit Non-Goals

- no deep backend refactor
- no invention of new routes unless the current route set cannot support the required flow
- no operator-console product design in this document

## Current State

Current backend capabilities already include:

- `POST /recommendation/run`
- `POST /recommendation/runs`
- `GET /recommendation/runs/{job_id}`
- `POST /source-documents/`
- `GET /source-documents/{source_document_id}`
- `POST /review-records/from-source-documents/{source_document_id}`
- `POST /review-records/{review_record_id}/approve`
- `POST /review-records/{review_record_id}/reject`
- `POST /review-records/{review_record_id}/promote`
- `POST /review-records/{review_record_id}/demote`
- `POST /c12/review-records/prepare`

The app currently still assumes:

- relative `/api` and `/method-dev` proxy prefixes
- partial frontend `SystemSpecs` coverage
- no desktop upload-first story

## Decision-Complete Implementation Approach

### Route-family stance

The standalone app should treat the following routes as canonical:

#### Recommendation

- `POST /recommendation/run`
- `POST /recommendation/runs`
- `GET /recommendation/runs/{job_id}`

The app should avoid deprecated `/recommendation/recommend` and `/recommendation/jobs` routes in new implementation work.

#### Source documents

- `POST /source-documents/`
- `GET /source-documents/{source_document_id}`

#### Review records

- `GET /review-records`
- `GET /review-records/{review_record_id}`
- `POST /review-records/from-source-documents/{source_document_id}`
- `POST /review-records/{review_record_id}/approve`
- `POST /review-records/{review_record_id}/reject`
- `POST /review-records/{review_record_id}/promote`
- `POST /review-records/{review_record_id}/demote`

#### Orchestration

- `POST /c12/review-records/prepare`

The app should avoid deprecated legacy orchestration/status routes in new client work unless a legacy path is temporarily required for compatibility.

### Base-URL stance

In desktop mode, the app must treat `api` and `method-dev` as fully qualified runtime-configured base URLs. It must not assume Vite proxy behavior in production.

### Recommendation detail-mode stance

Use `response_detail=agent` by default for the scientist-facing recommendation flow.

Use `response_detail=operator` only when:

- a richer operator/debug surface explicitly requires full discovered/skipped lists
- the user is in review/operator tooling

Reason:

- the scientist flow should stay lean and readable
- operator/debug flows can pay the extra context cost

### Upload flow stance

The standalone app must support upload-first ingestion through `/source-documents/`.

#### Supported source types

- `pdf`
- `html`

#### Client-side responsibilities

- choose file locally
- detect whether it is HTML or PDF
- generate source-document metadata
- base64-encode PDF payloads for `pdf_base64`
- send raw HTML text for `html_content`

#### Contract rule

The client must never send desktop-local file paths to the hosted backend as `local_paths`.

### Review-record creation stance

For a simple upload -> review flow, the preferred path is:

1. `POST /source-documents/`
2. `POST /review-records/from-source-documents/{source_document_id}`

For a richer upload -> extract -> optional-approve orchestration flow, the preferred path is:

1. `POST /c12/review-records/prepare`

Use orchestration when:

- the user wants one guided “prepare this paper” action
- the UI wants bounded execution-step feedback

### Frontend type expansion stance

The frontend request model should expand to include backend-supported fields that materially improve recommendation fit:

- `instrument_modes`
- `max_pressure_bar`

Frontend `SystemSpecs` should therefore grow accordingly, and payload shaping should pass them through when present.

### Local corpus and upload mode stance

The app should expose three user-facing source paths:

- `local_corpus`
- `open_access`
- `uploaded_source`

Implementation note:

- `uploaded_source` is a frontend workflow concept built on `/source-documents` and review/orchestration routes
- it is not the same as backend `local_files`

## Interfaces / Contracts / Types Affected

### Frontend `SystemSpecs`

Add:

- `instrumentModes: string[]`
- `maxPressureBar: number | null`

### Frontend route abstraction

Refactor API client construction so each service route is based on:

- `apiBaseUrl`
- `methodDevBaseUrl`

### Upload payload contract

Use existing backend schema:

- `source_document`
- `html_content` or `pdf_base64`

No new upload route is required for Wave 1.

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- `cd services/method-development && uv run pytest -q`
- upload-flow integration test against source-document registration and review/orchestration path
- contract tests for `response_detail=agent` vs `response_detail=operator`

## Risks and Rollback

- Risk: client code continues to mix canonical and deprecated routes.
- Risk: upload UX accidentally exposes backend-local path concepts.
- Risk: the app sends richer request fields but backend/client types drift.

Rollback:

- keep canonical route usage additive first
- retain legacy route compatibility temporarily if needed
- do not expose user-facing upload features until the explicit upload-first contract is wired end to end

## Decision Notes

- 2026-04-21: Canonical non-deprecated routes are the required target for new client work.
- 2026-04-21: Upload-first behavior must be built on `/source-documents`, not `local_files`.
- 2026-04-21: `response_detail=agent` is the default for scientist-facing flows.

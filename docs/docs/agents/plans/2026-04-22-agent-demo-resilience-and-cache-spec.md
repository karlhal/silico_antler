---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent standalone desktop runtime cache resilience demo behavior
source_of_truth: docs/agents/execution-plans.md
---

# Agent Demo Resilience And Cache Spec

## Goal and Success Criteria

Define deterministic runtime behavior for live, cached, and demo-safe operation so the app remains credible during a hackathon or investor demo even under flaky network conditions.

Success means:

- the app can clearly operate in `Live`, `Cached`, or `Demo-safe` mode
- fallback behavior is predictable and visible, not accidental
- recently successful runs and upload artifacts are reusable locally
- degraded external conditions do not make the product feel broken

## Scope

- operating modes
- local cache contents and boundaries
- fallback triggers
- UI communication rules for degraded behavior
- acceptance criteria for unreliable live conditions

## Explicit Non-Goals

- no fully offline scientific backend
- no replacement of hosted services with local inference
- no hidden “fake success” states that pretend live work happened when it did not

## Current State

The current app already handles runtime outcomes such as:

- backend error
- timeout
- interrupted run
- demo fallback

What is missing is a deliberate desktop-level resilience model that:

- preserves successful results locally
- distinguishes live from cached or demo-safe output
- makes fallback and recovery understandable to the user

## Decision-Complete Implementation Approach

## Operating Modes

### 1. `Live`

Use when:

- hosted `api` and `method-dev` health checks are good
- the user has not explicitly chosen demo-safe mode

Behavior:

- all runs call hosted services directly
- successful responses are cached locally
- uploads attempt live registration and orchestration

### 2. `Cached`

Use when:

- the user reopens a recent run
- the user explicitly requests a prior successful result
- health checks are degraded or unavailable, but a valid local snapshot exists

Behavior:

- show the cached result immediately
- clearly label that the content is cached
- offer explicit `Retry live` action when services recover

### 3. `Demo-safe`

Use when:

- the user toggles demo-safe mode
- startup health checks fail and no valid live path is available
- the operator wants maximum demo reliability

Behavior:

- use deterministic bundled snapshots and/or previously cached successful outputs
- never silently claim that fresh discovery or upload extraction was performed
- keep the UI polished and intentional rather than “error-first”

## What Gets Cached Locally

### Required cache objects

- recommendation run request payload
- recommendation result payload
- runtime summary and request ID
- top-level recommendation metadata for recent-run lists
- uploaded source-document metadata
- uploaded file fingerprint
- extracted/review-ready response snapshots
- startup health result and timestamp
- deterministic demo-safe fixtures bundled with the app

### Recommended cache key dimensions

- request hash derived from system specs, target inputs, source mode, and selected runtime config
- uploaded file fingerprint derived from file name, size, modified timestamp, and content hash
- schema version

### Cache boundaries

Allowed:

- successful live outputs
- deterministic demo-safe fixtures
- local UI state helpful for recovery

Not allowed:

- authoritative review-store truth
- hidden mutation queues against hosted services
- stale cached content presented as live output

## Fallback Rules

### Recommendation flow

- If `method-dev` is healthy: default to live.
- If `method-dev` is unavailable and a matching cached result exists: show cached result first.
- If `method-dev` is unavailable and no cache exists: offer demo-safe run with explicit label.

### Upload flow

- If source-document registration or orchestration is unavailable:
  - preserve local file metadata
  - explain that live extraction is unavailable
  - offer retry when services recover
  - if a prior extraction snapshot exists for the same file fingerprint, allow cached inspection

### Open-access discovery degradation

- If open-access search/fetch degrades but hosted service still returns a valid degraded report:
  - show it as live degraded output
  - preserve runtime summary and degraded label
- If the service cannot return a result:
  - fall back to cached or demo-safe mode according to availability

## UI Communication Rules

The app must clearly label result origin with one of:

- `Live result`
- `Cached result`
- `Demo-safe result`
- `Live degraded result`

Required communication principles:

- no silent fallback
- no punitive error walls as the primary experience
- give the user one clear next action:
  - retry live
  - inspect cached result
  - continue with demo-safe run

## Recovery Rules

- when services recover, the user can explicitly rerun live from any cached or demo-safe view
- cached results remain viewable even after live recovery
- demo-safe mode should be sticky only when explicitly enabled by the user or operator

## Interfaces / Contracts / Types Affected

Introduce a frontend runtime-mode model:

```ts
type AgentRuntimeMode = 'live' | 'cached' | 'demo_safe'
type AgentResultOrigin = 'live' | 'cached' | 'demo_safe' | 'live_degraded'
```

Recommended persisted snapshot shape:

```ts
interface CachedAgentRunSnapshot {
  schemaVersion: 1
  requestHash: string
  createdAt: string
  origin: AgentResultOrigin
  request: unknown
  report: unknown
  runtimeSummary: unknown
}
```

## Validation Matrix

When implemented:

- desktop smoke test for startup in all three modes
- simulated service-unavailable case with cached recommendation recovery
- simulated service-unavailable case with demo-safe fallback
- upload flow test for interrupted registration/orchestration
- `cd apps/agent && npm run build`

## Risks and Rollback

- Risk: cache behavior becomes too implicit and confuses trust.
- Risk: demo-safe mode feels fake or toy-like.
- Risk: stale cached results are mistaken for fresh outputs.

Rollback:

- keep all fallback labeling explicit
- keep demo-safe fixtures deterministic and intentionally framed
- prefer showing fewer capabilities clearly over pretending live capability exists

## Decision Notes

- 2026-04-21: The first resilient build will support `Live`, `Cached`, and `Demo-safe` modes.
- 2026-04-21: Demo-safe mode is a productized resilience path, not a hidden developer fallback.

---
status: active
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent standalone desktop architecture tauri runtime packaging
source_of_truth: docs/agents/execution-plans.md
---

# Agent Standalone Desktop Architecture

## Goal and Success Criteria

Define the architecture for turning `apps/agent` into an installable standalone desktop app without collapsing it into the existing `apps/desktop` workbench.

Success means:

- the agent app has a dedicated desktop shell and runtime boundary
- hosted API endpoints are injected through runtime config instead of dev proxy assumptions
- uploaded PDFs/HTML flow through hosted `/source-documents` routes rather than server-local file paths
- local persistence and cache boundaries are explicit enough to implement without ad hoc decisions

## Scope

- Tauri shell placement and repo boundaries
- frontend/runtime boundary for `apps/agent`
- runtime config injection for hosted dependencies
- desktop-local persistence and cache boundaries
- startup health checks
- file upload flow for source documents

## Explicit Non-Goals

- no reuse of the existing `apps/desktop` UI surface
- no bundling of the method-development service or scientific runtime locally
- no fully offline product mode
- no detailed review-store schema design beyond desktop integration requirements

## Current State

Today:

- `apps/agent` is a standalone React + Vite app
- its runtime assumes relative `/api` and `/method-dev` URLs under Vite or reverse-proxy hosting
- `apps/desktop` is a separate Tauri shell for the sidecar/local inference workbench
- the backend’s `local_files` mode is server-path based and is therefore not a valid direct UX for a desktop app that talks to hosted services

The new desktop build should preserve the existing app boundary instead of folding agent work into the existing desktop workbench.

## Decision-Complete Implementation Approach

### Architecture stance

Create a dedicated Tauri shell inside `apps/agent`, not in `apps/desktop`.

Target structure:

- `apps/agent/src/` remains the React scientist-copilot frontend
- `apps/agent/src-tauri/` becomes the dedicated shell for agent desktop packaging

Reason:

- the product boundary stays aligned with the repo’s app boundaries
- the existing `apps/desktop` workbench has a different product purpose, runtime stack, and release model
- co-locating the shell with `apps/agent` keeps build, docs, and ownership coherent

### Why this must not reuse `apps/desktop`

`apps/desktop` is a local sidecar/inference workbench. The agent app is a hosted-service copilot with different:

- target workflow
- network assumptions
- state model
- release story
- demo narrative

Reusing `apps/desktop` would create:

- mixed mental models
- mixed release/testing boundaries
- avoidable complexity in runtime orchestration

### Frontend/runtime boundary

The React app stays responsible for:

- scientist workflow and report UI
- local session state
- cache-awareness and fallback presentation
- upload initiation

The Tauri shell is responsible for:

- installable packaging
- desktop-local config storage
- file-picker and local file reading
- desktop-local cache persistence
- startup health checks and status handoff
- safe opening of exported reports or source links

The Tauri shell is **not** responsible for:

- method recommendation logic
- extraction logic
- review-record business rules
- retrieval/scoring decisions

### Runtime config injection

Replace all production reliance on relative proxy paths with explicit runtime-configured base URLs.

Define one desktop runtime config object:

```ts
interface AgentDesktopRuntimeConfig {
  apiBaseUrl: string
  methodDevBaseUrl: string
  operatorModeEnabled: boolean
  cachePolicy: 'live_preferred' | 'cached_preferred' | 'demo_safe'
  demoSnapshotVersion: string
  startupHealthTtlSec: number
}
```

Runtime config source of truth:

- persisted desktop config file managed by Tauri
- seeded from sensible defaults in development
- environment-overridable during packaging or CI

Frontend access pattern:

- on desktop: fetch config through a Tauri command at startup
- on web: continue to support environment/config fallback

### Required startup health checks

At launch, the desktop shell must perform lightweight health checks against:

- `apiBaseUrl`
- `methodDevBaseUrl`

Health result should be cached with timestamp and surfaced to the frontend as:

- healthy
- degraded
- unavailable

The frontend should use this to determine whether live, cached, or demo-safe mode is the default at launch.

### Desktop-local persistence boundaries

Desktop-local persistence should store only:

- runtime config
- cached recommendation results
- cached upload/extraction artifacts
- recent run metadata
- deterministic demo-safe snapshots

Desktop-local persistence should **not** store:

- authoritative review-record truth
- scientific business logic state that belongs to hosted services
- server-side promotion state

### File upload flow

The desktop app must support upload-first behavior for source documents.

Required flow:

1. user chooses PDF or HTML file through native file picker
2. Tauri shell reads the file locally
3. frontend constructs `SourceDocumentRegisterRequest`
4. frontend uploads to hosted `/source-documents/`
5. frontend either:
   - creates a review record from the registered source, or
   - calls C12 orchestration for preparation/review-ready flow

Important rule:

- do not expose `local_files` server-path semantics in the desktop UX

### Export and external-open behavior

The desktop shell should provide safe helpers for:

- saving exported HTML handoffs locally
- opening exported files in the default browser
- opening external source URLs explicitly

This prevents the React app from trying to improvise desktop-specific file behavior.

## Interfaces / Contracts / Types Affected

### Frontend types

Add desktop runtime config typing to `apps/agent`.

### API client

Refactor `apps/agent/src/lib/api.ts` so route construction is based on injected base URLs rather than implicit relative prefixes.

### Tauri commands

Implement commands equivalent to:

- `get_agent_runtime_config`
- `set_agent_runtime_config`
- `pick_source_document`
- `read_source_document_for_upload`
- `read_cached_agent_snapshot`
- `write_cached_agent_snapshot`
- `get_agent_startup_health`
- `save_exported_analysis`

Exact command naming can change, but responsibilities must remain fixed.

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- desktop shell smoke test for:
  - launch
  - config load
  - health check
  - upload initiation
  - cached snapshot recovery
- relevant `services/method-development` tests if upload/orchestration contracts change

## Risks and Rollback

- Risk: runtime config remains half-proxy, half-explicit and causes inconsistent behavior.
- Risk: desktop shell starts owning business logic that belongs to hosted services.
- Risk: upload flow accidentally depends on server-local path behavior.

Rollback:

- keep the React app web-capable
- keep desktop additions additive at the runtime boundary
- if packaging slips, retain the same explicit config model in the web build

## Implementation Status

### Implemented on 2026-04-21

First thin vertical slice completed:

- dedicated Tauri shell scaffold created under `apps/agent/src-tauri`
- desktop runtime config added and persisted locally by the Tauri shell
- startup health checks added for `apiBaseUrl` and `methodDevBaseUrl`
- startup health status handed off to the React app and surfaced in the dashboard
- frontend API client refactored to build canonical service URLs from injected base URLs instead of implicit `/api` and `/method-dev` assumptions
- web fallback path preserved through Vite/env config so the same app still runs outside Tauri

Files added or introduced for this slice:

- `apps/agent/src-tauri/Cargo.toml`
- `apps/agent/src-tauri/build.rs`
- `apps/agent/src-tauri/tauri.conf.json`
- `apps/agent/src-tauri/capabilities/default.json`
- `apps/agent/src-tauri/src/main.rs`
- `apps/agent/src/lib/agentRuntime.ts`
- `apps/agent/src/vite-env.d.ts`

Files updated for this slice:

- `apps/agent/src/lib/api.ts`
- `apps/agent/src/App.tsx`
- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/types/index.ts`
- `apps/agent/package.json`
- `apps/agent/vite.config.ts`
- `apps/agent/README.md`

Validation completed for this slice:

- `cd apps/agent && npm run build`
- `cd apps/agent/src-tauri && cargo check`

### Not yet implemented

Still pending from this architecture plan:

- native file picker and local file read commands for upload-first source-document flow
- hosted `/source-documents/` desktop upload path
- cached snapshot read/write commands and desktop cache recovery behavior
- export/save/open desktop helpers
- runtime-config editing UI inside the app
- launch-mode selection logic that automatically chooses between live, cached, and demo-safe operation
- packaging/release hardening beyond the current development shell scaffold

### Follow-up note from 2026-04-21

During demo-path verification, `services/method-development/app/recommendations_router.py` had a broken top-level import line that prevented live recommendation service startup. That backend issue was corrected and validated separately so live service-backed demo behavior can run again when Gemini/runtime env is configured.

## Decision Notes

- 2026-04-21: The agent app must get its own Tauri shell under `apps/agent`.
- 2026-04-21: The first standalone version is installable but still service-backed.
- 2026-04-21: Upload flow must use hosted source-document registration, not backend-local paths.
- 2026-04-21: The first implemented slice stops at runtime config and startup health; upload and cache commands remain follow-up work.

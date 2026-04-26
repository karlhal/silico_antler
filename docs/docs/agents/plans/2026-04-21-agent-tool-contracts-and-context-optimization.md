---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development apps/api tool contracts context optimization
source_of_truth: docs/agents/execution-plans.md
---

# Agent Tool Contracts And Context Optimization

## Goal and Success Criteria

Improve the agent-facing tool and contract layer so future agent loops can use fewer, clearer, higher-signal tools with less wasted context and fewer ambiguous decisions.

Success means:

- agent-facing tools and API operations have clearer boundaries and naming
- tool outputs return only the context needed for the next decision
- overlapping or low-value tool surfaces are reduced or merged
- schemas and descriptions make correct tool choice and parameter construction easier

## Scope

- `services/method-development` recommendation, retrieval, review, and orchestration contracts
- `apps/api` helper endpoints where they are part of agent workflows
- `apps/agent` only where request shaping or client-side tool abstractions need to change
- future MCP or SDK wrappers if the repo exposes more direct tool surfaces later

## Explicit Non-Goals

- no broad rewrite of business logic
- no forced multi-agent architecture
- no proliferation of more endpoints just to match existing backend modules
- no UI redesign as part of this slice

## Current State

The repo already has strong backend capability, but its tool surface has grown organically:

- recommendation, retrieval, review-record, and orchestration routes exist
- some routes are powerful but operator-oriented
- some concepts are still expressed as low-level primitives rather than task-shaped actions
- the agent app consumes a good primary recommendation contract, but future deeper agent loops would still have to choose among several overlapping backend primitives

## Why This Should Happen

Current external guidance points in the same direction:

- Anthropic recommends building a few thoughtful tools for high-impact workflows rather than many overlapping wrappers
- the same guidance recommends namespacing, meaningful context return, and token-efficient tool responses
- OpenAI’s agent docs also emphasize that single-agent systems add nondeterminism around tool choice and argument precision, which means tool ergonomics matter directly for reliability

This repo will benefit if its internal tools are designed for agent reasoning rather than for backend modularity alone.

## Decision-Complete Implementation Approach

### Product stance

Tools should be shaped around the decisions an agent actually needs to make:

- recommend a method
- inspect trust and evidence
- create or inspect a review record
- promote a reviewed record
- debug or replay a run

Avoid exposing multiple near-synonymous primitives if one higher-signal action would do.

### Tool surface stance

Audit the current surface for:

- overlapping operations
- routes that dump too much raw data
- names that reflect backend storage rather than user intent
- arguments that are too low-level or ambiguous

Then redesign toward fewer, clearer actions.

### Context stance

Return only high-signal context:

- summaries plus linked details
- targeted search results instead of full lists where possible
- pre-assembled context objects where agents repeatedly need the same joined data

The goal is to spend tokens on decisions, not on brute-force scanning.

### Naming stance

Introduce or normalize namespacing and naming conventions:

- consistent prefixes or families for recommendation, review, promotion, and diagnostics
- parameter names that encode exactly what identifier is expected
- explicit distinction between user-facing, operator-facing, and debug-facing tools

### Description and schema stance

Where tools are defined in code, SDK wrappers, or future MCP servers:

- expand descriptions
- document caveats and non-goals
- tighten schemas
- add examples only after descriptions are already clear

### Evaluation stance

Measure tool-surface changes using the eval plan rather than relying on intuition alone.

## Primary Files And Boundaries

Likely implementation homes:

- `services/method-development/app/recommendations_router.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/review_records_router.py`
- `services/method-development/app/c12_orchestration_router.py`
- `apps/api/app/main.py`
- relevant client wrappers in `apps/agent/src/lib/api.ts`

Boundary rule:

- backend services own tool semantics and payload shape
- the agent app consumes those contracts and should avoid inventing competing abstractions

## Validation Matrix

When implemented:

- `cd services/method-development && uv run pytest -q`
- `cd apps/api && uv run pytest -q` if helper endpoints change
- `cd apps/agent && npm run build` if client wrappers change
- eval runs from the eval-flywheel plan

## Risks and Rollback Strategy

- Risk: consolidating tools removes useful low-level primitives that operators still need.
- Risk: higher-level tools become too magical and hide important distinctions.
- Risk: namespacing changes create churn without enough performance gain.

Rollback:

- keep low-level primitives for internal/operator use where necessary
- make new higher-level surfaces additive before deleting older ones

## Decision Notes

- 2026-04-20: This plan is informed by Anthropic’s September 11, 2025 guidance on writing effective tools for agents.
- 2026-04-20: The main takeaway applied here is fewer, clearer, more context-efficient tools, not more abstraction for its own sake.

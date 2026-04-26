---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: services/method-development apps/agent operator tooling hardening
source_of_truth: docs/agents/execution-plans.md
---

# Agent Operator And Developer Tooling Hardening

## Goal and Success Criteria

Harden the operator and developer tooling around the method-development service so debugging, evaluation, corpus maintenance, and demo support are faster and more reproducible.

Success means:

- the service is easier to smoke-test and diagnose locally
- CLI and operator flows share the same runtime vocabulary as the app
- evaluation and corpus-promotion work become easier to run intentionally
- dev workflows depend less on hidden repo knowledge

## Scope

- CLI and helper scripts under `services/method-development/`
- review-record and promotion support workflows
- local operator affordances that can later feed internal UI surfaces
- small docs updates in service README or adjacent ops docs

## Explicit Non-Goals

- no full internal admin platform in this slice
- no replacement of the agent app with a CLI-first workflow
- no attempt to expose every backend primitive to end users

## Current State

The service already has more tooling than most projects at this stage:

- demo smoke script
- paper evaluation and review scripts
- recommendation CLI
- review-record orchestration and promotion routes
- Milvus migration and benchmark scripts

The gap is coherence and hardening:

- many capabilities are discoverable only by reading the README carefully
- runtime semantics between CLI, scripts, and app are not yet fully aligned
- operator maintenance flows are powerful but still relatively raw

## Why This Should Happen

As the product grows, operator and developer velocity matter:

- faster diagnosis improves user-facing reliability
- better evaluation loops reduce regression risk
- easier promotion and inspection improves corpus quality

This is the "make the team faster" layer that keeps future feature work from slowing down.

## Decision-Complete Implementation Approach

### Tooling stance

Treat tooling as product infrastructure, not side scripts.

That means:

- clear naming
- consistent output formats
- explicit success/failure status
- shared config handling

### CLI stance

Normalize the recommendation CLI and helper scripts around:

- shared source-mode names
- shared runtime-status vocabulary
- machine-readable output by default when appropriate
- predictable non-zero exit codes on failure classes

### Operator workflow stance

Improve the internal maintenance loop for:

- listing recent review records
- spotting promotion candidates
- replaying problem cases
- comparing extraction output against gold fixtures
- inspecting degraded or fallback runs

The first slice can remain CLI-oriented as long as it becomes faster and clearer.

### Fixture and replay stance

Expand the ability to capture and replay interesting runs:

- failed open-access queries
- degraded-mode runs
- strong review-backed promotions
- representative local-corpus comparisons

This should support both debugging and future demo preparation.

### Docs stance

Condense common operator tasks into clearer playbooks:

- local recommendation debugging
- corpus-promotion workflow
- Milvus troubleshooting
- fallback-mode interpretation

## Primary Files And Boundaries

Likely implementation homes:

- `services/method-development/run_demo_smoke.py`
- `services/method-development/run_method_recommendation_cli.py`
- other helper scripts under `services/method-development/`
- service README and targeted tests

Boundary rule:

- method-development owns tooling and CLI behavior
- agent may later consume some of this through internal UI, but should not duplicate the same logic

## Validation Matrix

When implemented:

- `cd services/method-development && uv run pytest -q`
- script smoke tests for updated helper commands
- README command verification for touched workflows

## Risks and Rollback Strategy

- Risk: tooling complexity grows faster than actual operator need.
- Risk: scripts drift from service contracts.
- Risk: debug-only switches leak into ordinary product paths.

Rollback:

- keep new tooling layered on top of existing service contracts
- prefer improving shared helpers over multiplying scripts

## Decision Notes

- 2026-04-20: The service already has the raw ingredients for good tooling; this plan is about consolidation and reliability.
- 2026-04-20: Better internal tools are a direct product quality investment, not side work.

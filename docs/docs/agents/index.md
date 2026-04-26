---
owner: platform
last_verified: 2026-04-22
applies_to: all-agents
source_of_truth: docs/agents
---

# Agent Knowledge Index

Use this page as the entrypoint to repository-local agent guidance.

## Registry Format
Each registry row must use this exact format:

`- ENTRY | id=<slug> | path=<relative-path> | applies_to=<scope> | purpose=<one sentence>`

## Registry
- ENTRY | id=architecture-boundaries | path=./architecture-boundaries.md | applies_to=all-apps | purpose=Domain boundaries, ownership, and dependency direction.
- ENTRY | id=debuggability-and-failures | path=./debuggability-and-failures.md | applies_to=all-apps | purpose=Rules for avoiding silent failures, hidden caps, and poor debugging visibility.
- ENTRY | id=quality-gates | path=./quality-gates.md | applies_to=all-apps | purpose=Required checks and minimum validation matrix by change surface.
- ENTRY | id=security-constraints | path=./security-constraints.md | applies_to=all-apps | purpose=Security invariants for secrets, network boundaries, and data handling.
- ENTRY | id=release-and-testing | path=./release-and-testing.md | applies_to=api-method-development | purpose=Release flow expectations and test strategy per app or service.
- ENTRY | id=execution-plans | path=./execution-plans.md | applies_to=all-agents | purpose=How to write and maintain in-repo execution plans.

## Core Product Docs
- Repo README: [`../../README.md`](../../README.md)
- Repo structure: [`../architecture/repo-structure.md`](../architecture/repo-structure.md)
- Design context: [`../../CODEX_DESIGN_CONTEXT.md`](../../CODEX_DESIGN_CONTEXT.md)
- Demo instructions: [`../../DEMO_INSTRUCTIONS.md`](../../DEMO_INSTRUCTIONS.md)

## Existing Source-Of-Truth READMEs

### Agent
- [`../../apps/agent/README.md`](../../apps/agent/README.md)

### API
- [`../../apps/api/README.md`](../../apps/api/README.md)
- [`../../apps/api/app/README.md`](../../apps/api/app/README.md)
- [`../../apps/api/tests/README.md`](../../apps/api/tests/README.md)

### Method Development Service
- [`../../services/method-development/README.md`](../../services/method-development/README.md)
- [`../../services/method-development/app/README.md`](../../services/method-development/app/README.md)
- [`../../services/method-development/tests/README.md`](../../services/method-development/tests/README.md)

## Maintenance Rules
- Keep `AGENTS.md` short and map-like; move deep guidance into focused docs.
- Update `last_verified` whenever a doc is materially changed.
- Run `npm run agent:harness:check` after editing instruction or `docs/agents` files.

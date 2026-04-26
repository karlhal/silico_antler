---
owner: platform
last_verified: 2026-04-18
applies_to: all-agents
source_of_truth: docs/agents
---

# Execution Plans

Use written plans for multi-step, risky, or cross-boundary tasks.

## When A Written Plan Is Required
- Changes spanning multiple apps or runtime boundaries.
- Contract or data-shape changes.
- Release workflow, CI, or packaging changes.
- Security-sensitive changes.

## Plan Location And Naming
- Store plans in `docs/agents/plans/`.
- Filename format: `YYYY-MM-DD-<short-slug>.md`.

## Required Plan Sections
- Goal and success criteria.
- Scope and explicit non-goals.
- Decision-complete implementation approach.
- Validation matrix (tests/checks to run).
- Risks and rollback strategy.

## Plan Lifecycle
- Keep status inline (`draft`, `active`, `completed`).
- Update decision notes as execution changes direction.
- Link merged PRs and final verification evidence.

## Related Docs
- Registry/index: [`./index.md`](./index.md)
- Quality gates: [`./quality-gates.md`](./quality-gates.md)
- Architecture boundaries: [`./architecture-boundaries.md`](./architecture-boundaries.md)

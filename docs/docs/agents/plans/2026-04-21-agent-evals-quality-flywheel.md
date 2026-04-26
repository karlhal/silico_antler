---
status: draft
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development evals quality flywheel
source_of_truth: docs/agents/execution-plans.md
---

# Agent Evals And Quality Flywheel

## Goal and Success Criteria

Create a continuous evaluation system for the agent product so workflow changes, tool-surface changes, prompt changes, and runtime hardening can be measured instead of argued from intuition.

Success means:

- the repo has repeatable datasets for critical agent behaviors
- workflow-level traces can be graded
- tool choice and argument precision are measured explicitly
- evals cover happy paths, edge cases, degraded paths, and failure recovery
- future roadmap work can prove improvement instead of only sounding plausible

## Scope

- `services/method-development` recommendation and orchestration behavior
- `apps/agent` workflow and presentation behavior where it affects task success
- evaluation harnesses, fixtures, grader definitions, and trace capture strategy

## Explicit Non-Goals

- no one-shot benchmark obsession
- no requirement to adopt a specific third-party platform
- no replacing domain-expert review with model judges alone
- no eval suite so broad that it becomes impossible to maintain

## Current State

The repo already has good raw material:

- golden recommendation cases
- extraction evaluation scripts
- paper-example fixtures
- review-record and orchestration tests

What is still missing is a product-level flywheel that connects:

- traces
- curated datasets
- tool-call correctness
- user-facing workflow outcomes

## Why This Should Happen

Recent official guidance aligns strongly here:

- OpenAI recommends starting with traces to debug workflow behavior, then moving to repeatable datasets and eval runs
- OpenAI’s evaluation guidance also says single-agent architectures introduce nondeterminism around tool choice and argument precision
- OpenAI further recommends pairwise comparison, classification, and rubric-based scoring because LLMs are better at discriminating than open-ended grading

This means the next agent-quality step is not just more tests. It is a better eval system.

## Decision-Complete Implementation Approach

### Flywheel stance

Adopt a four-stage loop:

1. capture traces
2. identify failure modes
3. add or refine dataset cases
4. rerun evals before and after changes

### Trace stance

Add workflow-level trace capture for:

- source selection
- live recommendation runs
- demo fallbacks
- empty-result runs
- review-record creation and promotion flows when surfaced

The trace should show decisions, tool choices, error branches, and fallback reasons.

### Dataset stance

Maintain curated datasets for:

- common successful recommendation requests
- ambiguous or underspecified requests
- multi-impurity local-corpus requests
- open-access runs with skipped-paper failure patterns
- timeout and degraded-mode cases
- prompt-injection or conflicting-instruction cases if relevant

### Evaluator stance

Use a mix of:

- exact and executable checks where possible
- pairwise comparison for report quality
- rubric-based pass/fail or scorecard grading for trust and workflow behavior
- selective human/domain-expert review for the highest-value cases

### Coverage stance

Measure at least:

- final task success
- tool selection correctness
- argument precision
- fallback correctness
- trust-surface completeness
- user-visible error quality

### Governance stance

Tie roadmap work to named eval slices. No major change to workflow, trust, runtime semantics, or tool contracts should ship without an eval impact statement.

## Primary Files And Boundaries

Likely implementation homes:

- `services/method-development/tests/`
- `services/method-development/run_*` evaluation helpers
- new dataset or trace-grade artifacts under `docs/agents/plans/` or a dedicated eval directory
- `apps/agent` only where traces or workflow assertions need support

Boundary rule:

- backend and app both contribute data
- eval semantics should stay repository-local and not depend on tribal memory

## Validation Matrix

When implemented:

- `cd services/method-development && uv run pytest -q`
- `cd apps/agent && npm run build`
- targeted eval-run commands defined by the new harness

## Risks and Rollback Strategy

- Risk: the eval system becomes too expensive or complicated to run often.
- Risk: model-judge graders drift away from domain reality.
- Risk: the team overfits to visible evals and misses new failure classes.

Rollback:

- keep the eval suite layered: smoke, core, and extended
- preserve human review on the most important cases

## Decision Notes

- 2026-04-20: This plan is informed by OpenAI’s current agent-evals and evaluation best-practices guidance.
- 2026-04-20: The key idea is a flywheel of traces plus datasets, not a one-time benchmark report.

---
status: active
owner: opencode
source_of_truth: docs/agents/execution-plans.md
last_verified: 2026-04-19
applies_to: services/method-development
---

# Paper Example Gold Fixtures And Evaluation

## Goal And Success Criteria

- Turn the two example papers under `services/method-development/tests/paper_example/` into reusable gold-standard evaluation fixtures.
- Capture the final selected chromatographic method for each paper in compact JSON.
- Add a repeatable evaluation path that runs extraction against both HTML and PDF sources and reports how closely the current extractor matches the expected method fields.

## Scope And Non-Goals

Scope:

- Add JSON fixtures for the PLOS glucose paper and the MDPI carotenoid paper.
- Add an evaluation helper plus a CLI/report script.
- Add tests that validate fixture loading and ensure evaluation runs without crashing.

Non-goals:

- Do not yet force the current extractor to fully match the new fixtures.
- Do not yet implement all missing extraction improvements for these papers.
- Do not broaden this into a generic benchmark framework for the whole repository.

## Decision-Complete Approach

- Use one fixture per paper with:
  - title
  - source file references
  - expected chromatography system
  - expected method parameters
  - expected retention entities
  - ambiguities and pitfalls
  - must-not-extract hints for common traps
- Normalize comparisons for strings, numbers, and gradient/time lists.
- Score extraction field-by-field instead of pass/fail only.
- Support both PDF and HTML evaluation for each paper.

## Validation Matrix

- `cd services/method-development && uv run pytest -q`
- `npm run agent:harness:check`
- `cd services/method-development && uv run python run_paper_example_evaluation.py`

## Risks And Rollback Strategy

Risks:

- Gold fixtures may overfit to one source variant if PDF and HTML disagree.
- Strict comparisons can create noisy failures while the extractor is still maturing.
- The MDPI paper mixes exploratory and final method details, which can confuse fixture authorship.

Rollback:

- Keep evaluator logic isolated from extraction code.
- If a fixture proves too strict, relax the expected field or mark it as informational rather than deleting the benchmark.

## Decision Notes

- Initial fixtures will focus on strict final-method expectations rather than sample prep or validation tables.
- Evaluation should be informative first: scorecards and diffs, not hard repository blockers for extraction quality.

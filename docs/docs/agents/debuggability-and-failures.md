---
owner: platform
last_verified: 2026-04-20
applies_to: all-apps
source_of_truth: AGENTS.md
---

# Debuggability And Failures

## Core Rule
- Do not introduce silent failures, swallowed exceptions, or hidden fallback behavior that obscures the real problem.

## Observability Expectations
- Prefer explicit errors or structured warnings over best-effort behavior that quietly changes outcomes.
- Log enough context to debug boundary conditions such as item counts, truncation, filtering, retries, timeouts, and source selection.
- Keep logs actionable: include the configured limit, the observed value, and the code path or subsystem involved.
- If work is skipped, dropped, capped, or downgraded, make that decision visible in logs, tests, or returned diagnostics.

## Limits And Thresholds
- Avoid unexplained hard-coded caps in retrieval, ranking, batching, pagination, or orchestration flows.
- When a fixed limit is necessary, document why it exists and surface it near the code path that enforces it.
- Add tests for realistic high-side cases when limits, caps, or filtering can change system behavior.
- Prefer configuration names and error messages that make mis-sized limits obvious during debugging.

## Failure Design
- Fail early when inputs, counts, or assumptions violate the contract in a way that would otherwise produce misleading output.
- Use fallbacks only when they preserve correctness or clearly communicate degraded behavior.
- Do not replace real failures with empty results, partial success, or default values unless the degraded path is explicit and inspectable.

## Review Checklist
- Can an operator tell why the system returned fewer results than expected?
- Can a developer see which limit, filter, or fallback changed the outcome?
- Would the current logs and tests catch an average-case input that exceeds a hidden threshold?

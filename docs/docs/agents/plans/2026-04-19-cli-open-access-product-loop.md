---
status: active
owner: opencode
source_of_truth: docs/agents/execution-plans.md
last_verified: 2026-04-19
applies_to: services/method-development
---

# CLI Open-Access Product Loop

## Goal And Success Criteria

- Provide a CLI-first product flow that can be tested without a UI.
- Support two source modes:
  - local already-downloaded papers
  - open-access web search and fetch
- Accept a user request, extract methods from candidate papers, compare those methods to the request, and print a recommendation with citations and evidence.

## Scope And Non-Goals

Scope:

- Add a CLI entrypoint for method recommendation.
- Add open-access discovery and fetch support.
- Add request-aware recommendation scoring on top of existing extraction/review/retrieval primitives.
- Keep deterministic extraction as the source of truth.

Non-goals:

- No paywalled publisher support in the first version.
- No broad crawling or scraping outside explicit open-access discovery/fetch.
- No requirement for a frontend before the CLI is usable.

## Decision-Complete Implementation Approach

- Phase 1: local-papers CLI
  - input request + local HTML/PDF paths
  - ingest -> extract -> score -> recommend
- Phase 2: open-access search/fetch
  - search OpenAlex for relevant HPLC papers
  - prefer best open-access URL/PDF links only
  - cache or stage fetched artifacts locally before ingestion
- Phase 3: recommendation synthesis
  - combine request relevance, extraction completeness, review/validation quality, and chemistry similarity when available
  - print concise recommendation plus citation/evidence blocks

## Validation Matrix

- `cd services/method-development && uv run pytest -q`
- `npm run agent:harness:check`
- CLI smoke tests for:
  - local paper mode
  - open-access discovery mode with mocked search/fetch responses

## Risks And Rollback Strategy

Risks:

- open-access fetch reliability may vary by source host
- request-aware recommendation could overfit to benchmark papers if scoring is too heuristic
- web fetch logic may blur the boundary between demo-safe and production-safe behavior

Rollback:

- keep discovery/fetch isolated from extraction internals
- keep local-papers mode working independently of web mode
- keep deterministic extraction and C12 orchestration untouched if discovery changes need rollback

## Decision Notes

- First web-search scope is open-access only.
- The CLI is the primary product test surface before any new UI.
- Recommendation output must include source title plus URL/DOI/evidence so users can inspect why the method was suggested.

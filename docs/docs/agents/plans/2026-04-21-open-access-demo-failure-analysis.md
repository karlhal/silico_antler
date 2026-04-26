---
status: active
owner: platform
last_verified: 2026-04-20
last_updated: 2026-04-20
applies_to: apps/agent services/method-development open-access demo path
source_of_truth: docs/agents/execution-plans.md
source_plan: ./2026-04-21-agent-retrieval-scoring-iteration-breakdown.md
source_report: ../../agent-app-implementation-report.md
---

# Open-Access Demo Failure Analysis

## Goal

Document the open-access demo failure mode seen in `apps/agent`, the fixes landed during this debugging slice, and the remaining work to explore.

## User-Facing Failure Pattern

The common failure state was:

`Found 10 papers, but none produced a trustworthy method candidate.`

In practice that meant:

- search returned papers
- screening allowed some candidates through
- fetch usually succeeded for HTML and/or PDF
- extraction completed without crashing
- no fetched paper produced a complete final method with trustworthy mobile phases plus flow rate

This was not a transport or server-availability failure. It was a retrieval-quality and extraction-completeness failure.

## What We Observed

### 1. The original demo query was weak for live literature

The original live-demo style case used a common analyte plus a generic matrix:

- analyte: `caffeine`
- matrix: `organic solvent`
- require MS: `true`

That query regularly pulled:

- broad coffee chemistry papers
- compositional food-analysis papers
- secondary methods literature
- unrelated LC-MS/MS papers that looked method-like in title/abstract metadata

This is a poor open-access demo shape because the matrix is too generic and the analyte is heavily represented in broad literature.

### 2. Metadata screening was necessary but not sufficient

The open-access path screens on title/abstract/source metadata before fetching full text. That removes obvious junk, but it still cannot guarantee that a paper contains one recoverable final HPLC method.

### 3. Some failures were extractor robustness bugs, not true literature misses

During debugging, several candidates failed before recommendation ranking because:

- HTML extraction failed while a usable PDF existed
- extracted `statement_text` exceeded schema limits
- extracted `section_label` exceeded schema limits
- short token matching produced false MS signals from unrelated words

### 4. The UI hid the useful diagnostics

The first app failure card only said that papers were found but methods were not extracted. It did not surface per-paper skip reasons, so operators could not distinguish:

- screening miss
- fetch failure
- extraction failure
- trust rejection due to incomplete method recovery

## What We Changed

### UI changes

- The failure state now surfaces `skipped_papers` diagnostics instead of only a generic error.
- Diagnostics are prioritized so `extraction` and `fetch` failures show before `screening` failures.
- The `Quick Demo` preset now loads a more open-access-friendly case:
  - request: `Find a final LC-MS/MS method for carotenoids in human plasma`
  - analyte: `carotenoids`
  - matrix: `Human Plasma`
  - require MS: `true`
  - source: `open_access`

Primary files:

- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/types/index.ts`

### Backend open-access retrieval and ranking changes

- Open-access candidate building now retries PDF when HTML extraction fails or produces an untrustworthy candidate.
- Search now uses multiple query variants instead of one fragile string.
- Generic matrices such as `organic solvent` are kept out of the primary query so they do not dominate retrieval.
- Screening no longer treats short MS tokens as plain substrings, which previously created false positives.
- Broad or secondary-method titles now receive explicit penalties, especially for matrix-generic queries.
- Caffeine/coffee-style broad literature is now demoted relative to direct validated method papers.

Primary files:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/open_access_client.py`

### Backend extraction hardening changes

- Overlong `EvidenceSnippet.text` and `EvidenceSnippet.section_label` values are now bounded before schema validation.
- Overlong extraction candidate `statement_text` fields are now bounded before schema validation.

Primary files:

- `services/method-development/app/retrieval_schemas.py`
- `services/method-development/app/hplc_extraction_schemas.py`

## Validation Completed During This Slice

Backend:

- `cd services/method-development && uv run pytest -q tests/test_recommendation_engine.py`
- `cd services/method-development && uv run pytest -q tests/test_hplc_extraction.py tests/test_recommendation_engine.py tests/test_open_access_client.py`

Frontend:

- `cd apps/agent && npm run build`

Regression coverage added for:

- HTML-to-PDF fallback after extraction failure
- multi-query open-access search behavior
- caffeine-query demotion of broad coffee literature
- overlong `statement_text` handling
- overlong `section_label` handling
- frontend display of prioritized skip diagnostics

## Current Status

The open-access path is now materially clearer and more robust than the pre-debug state:

- extraction no longer fails on the overlong text cases seen in live papers
- fetch and extraction failures are visible in the UI
- the demo preset is more aligned with papers that are likely to contain a final LC-MS/MS method
- the backend is better at demoting broad or secondary literature

However, the path is still opportunistic:

- open-access search is only as good as live metadata plus accessible full text
- some analyte/matrix combinations still yield only partial or non-final methods
- a run can still legitimately end with `0` trustworthy candidates even when search and fetch succeed

Important implementation detail:

- the app sends `max_papers: 10`
- the backend oversamples beyond that during search (`_open_access_search_budget`) before selecting the final candidate set

So `10` is not the only recall limit, although the final kept-candidate cap may still be worth revisiting.

## What Is Left To Change Or Explore

### 1. Demo strategy

- Decide whether `Quick Demo` should remain an open-access preset or whether the product should expose two distinct presets:
  - reliable `local_corpus` demo
  - best-effort `open_access` demo

### 2. Retrieval budget tuning

- Evaluate raising app `max_papers` from `10` to `15` or `20`.
- Measure whether this improves open-access success rate enough to justify the extra latency and fetch volume.

### 3. Stronger UI observability

- Surface the executed `search_query_used` in the app.
- Consider showing the top screened-in paper titles before extraction begins.
- Consider showing screening-stage skips separately from fetch/extraction skips.

### 4. Softer failure handling

- Evaluate a fallback mode that returns "best partial literature hits" when no complete trustworthy method is found, instead of only hard-failing.
- If implemented, this must remain clearly labeled as partial or manually review-required output.

### 5. Retrieval precision for generic matrices

- Continue tuning analyte/title precision for common analytes under matrix-generic prompts.
- Consider stronger hard filters for generic matrices where title-level final-method signals are absent.

### 6. Better open-access demo candidates

- Benchmark additional live-demo analyte/matrix pairs and record success rates.
- Current best candidates to keep exploring:
  - `carotenoids in human plasma`
  - `fat-soluble vitamins in human plasma`

## Practical Product Guidance Right Now

- Use `local_corpus` when the goal is a deterministic product demo.
- Use `open_access` when the goal is to probe live literature behavior and collect failure diagnostics.
- Treat open-access failures as informative product signals, not necessarily bugs, unless they reveal:
  - bad retrieval precision
  - fetch fallback gaps
  - extractor crashes
  - misleading trust labeling

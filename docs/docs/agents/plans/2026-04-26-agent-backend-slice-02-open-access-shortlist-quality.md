---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development open-access screening shortlist retrieval
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
  - ./2026-04-21-open-access-demo-failure-analysis.md
---

# Slice 02: Open-Access Shortlist Quality

## Goal And Success Criteria

Improve which open-access papers are fetched and extracted before changing final ranking weights.

Success means:

- known good title-like method papers are not displaced by newer equal-score but weaker papers
- clinical plasma queries demote plant, food, broad composition, review, and non-final-method papers before fetch
- skip reasons explain why papers were screened out
- existing smoke/core evals still pass

## Current Context

On 2026-04-23, live probes showed:

- broad carotenoids, glucose, metformin, and paclitaxel live searches with `max_papers=3` returned `no_trustworthy_candidates`
- exact-title glucose query succeeded and selected the PLOS paper with score `0.764`, validation `needs_review`
- broad glucose query found the known PLOS paper but skipped it because it tied on screening score and newer papers sorted ahead of it

Concrete observed issue:

- `Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization`
- got screening score `4.50`
- was skipped when newer equal-score papers filled the shortlist

Relevant files:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/open_access_client.py`
- `services/method-development/app/recommendation_context_optimizer.py`
- `services/method-development/tests/test_recommendation_engine.py`
- `services/method-development/tests/test_open_access_client.py`
- `services/method-development/tests/fixtures/recommendation_golden_cases.json`
- `services/method-development/tests/paper_example/expected/evaluation_prompts.json`

Important functions in `recommendation_engine.py`:

- `_build_search_queries()`
- `_screen_open_access_candidates()`
- `_open_access_candidate_screen_score()`
- `_open_access_candidate_screen_reason_parts()`
- `_open_access_candidate_screen_summary()`
- `_open_access_candidate_dedupe_key()`
- `_merge_open_access_candidates()`
- `_has_conflicting_matrix_context()`
- `_has_primary_method_signal()`
- `_has_broad_scope_penalty()`
- `_looks_like_secondary_methods_literature()`

Current shortlist sort:

```python
scored_candidates.sort(
    key=lambda item: (
        item[1],
        item[0].published_year or 0,
        item[0].title,
    ),
    reverse=True,
)
```

This can favor recent broad papers over older exact final-method titles when scores tie.

## Scope

Backend open-access retrieval and screening only:

- deterministic screening features
- tie-breaking in shortlist selection
- stronger method-title and matrix-context rules
- tests for known positive and negative examples

## Explicit Non-Goals

- Do not add LLM reranking in this slice.
- Do not change final ranking weights.
- Do not change the frontend.
- Do not add fetch/extract concurrency yet.

## Decision-Complete Implementation Approach

### 1. Add Positive And Negative Screening Fixtures

In `tests/test_recommendation_engine.py`, add tests around `_screen_open_access_candidates()` or public `recommend_methods()` with fake clients.

Positive cases:

- exact title: MDPI carotenoids human plasma LC-MS/MS
- exact title: PLOS glucose Shewanella PMP derivatization
- direct metformin human plasma LC-MS/MS method title

Negative cases:

- broad carotenoid health/nutrition review
- plant carotenoid extraction or food composition paper for a human plasma query
- glucose sensor or review paper for final HPLC method query
- generic bioanalytical validation guidance with no analyte match

Use `OpenAccessPaperCandidate` fixtures directly so tests stay deterministic.

### 2. Improve Tie-Breaking

Add explicit tie-break components before year:

- exact analyte/title match
- exact matrix/title match
- title-level final-method signal
- title-level method plus derivatization signal when request mentions derivatization
- source/query provenance from an exact-title query
- then year

Keep the sort deterministic and inspectable. A helper like `_open_access_candidate_sort_key(request, candidate, score)` is preferable to embedding more tuple logic inline.

### 3. Strengthen Matrix Context Rules

Add or refine a small deterministic matrix ontology:

- clinical: `human plasma`, `plasma`, `serum`, `whole blood`, `urine`
- nonclinical/food/plant: `plant`, `leaf`, `fruit`, `vegetable`, `food`, `extract`, `oil`, `milk`, `tissue`
- cell/culture: `cell`, `culture`, `media`, `Shewanella`

Rules:

- for clinical matrix requests, penalize plant/food/tissue contexts unless title explicitly states human/plasma/serum
- do not over-penalize matrix-generic requests when the title is a direct final-method paper
- preserve glucose Shewanella as valid for glucose derivatization prompts because the request itself mentions that context in exact/title mode

### 4. Keep Search Recall Broad Enough

Do not hard-filter all low-scoring papers before selected fallback behavior. The existing logic falls back to top scored candidates if none are positive. Preserve that behavior unless tests prove it is harmful.

### 5. Make Reasons Testable

Add stable reason fragments for major skip causes:

- missing analyte
- missing matrix
- conflicting matrix context
- lacks chromatography signal
- lacks MS signal
- broad/compositional title
- secondary/review/protocol title

Do not replace human-readable reasons yet; structured reason codes are slice 05 or later.

## Validation Matrix

```bash
cd services/method-development
uv run pytest -q tests/test_recommendation_engine.py tests/test_open_access_client.py
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
```

Manual smoke probes:

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization" \
  --analyte-name "glucose" \
  --preferred-mode rp_lc \
  --open-access-search \
  --search-query "Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization" \
  --max-papers 8 \
  --json --debug
```

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "Find a final LC-MS/MS method for carotenoids in human plasma" \
  --analyte-name "carotenoids" \
  --matrix "human plasma" \
  --require-ms \
  --open-access-search \
  --max-papers 5 \
  --json --debug
```

## Risks And Rollback Strategy

Risk: stricter matrix penalties can suppress valid unusual methods.

Mitigation:

- prefer tie-break and scoring changes over hard filters
- keep exact-title query matches strong
- test matrix-generic and exact-title cases separately

Rollback:

- revert new tie-break helper and restore previous score/year/title sort.

## Definition Of Done

- known PLOS glucose paper wins or remains in shortlist for exact/title and derivatization prompts
- broad/irrelevant clinical plasma negatives are skipped before fetch in tests
- smoke and core evals pass

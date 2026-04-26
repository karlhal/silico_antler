---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development ranking scoring calibration
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-22-agent-ranking-scoring-retrieval-refresh.md
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
---

# Slice 03: Ranking Calibration And Score Semantics

## Goal And Success Criteria

Make final recommendation scores easier to understand, calibrate, and regression-test after shortlist quality is improved.

Success means:

- retrieval relevance and final scientific fit are visible as different concepts
- score features do not obviously double-count the same lexical evidence
- `review_trust_prior` either affects ranking in a bounded way or is removed from ranking explanations
- pairwise ordering tests cover top candidate decisions
- existing golden cases pass or are intentionally updated with documented score changes

## Current Context

Relevant files:

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/recommendation_schemas.py`
- `services/method-development/app/retrieval_store.py`
- `services/method-development/tests/test_recommendation_engine.py`
- `services/method-development/tests/test_recommendation_golden_cases.py`
- `services/method-development/tests/fixtures/recommendation_golden_cases.json`

Current weights in `recommendation_engine.py`:

```python
RANKING_FEATURE_WEIGHTS = {
    "target_chemistry_fit": 0.24,
    "impurity_compatibility": 0.08,
    "system_fit": 0.16,
    "detector_compatibility": 0.10,
    "matrix_fit": 0.10,
    "runtime_fit": 0.08,
    "extraction_completeness": 0.10,
    "evidence_quality": 0.10,
    "review_trust_prior": 0.00,
    "literature_specificity": 0.04,
}
MISSING_DATA_PENALTY_WEIGHT = 0.08
```

Known issues:

- `matrix_fit`, `literature_specificity`, and parts of target fit can all depend on descriptor-text overlap
- `system_match` can default to midpoint when source data is missing
- `review_trust_prior` is calculated but has zero ranking weight
- current score explanations can look more sophisticated than the actual rank signal

Important functions:

- `_score_extraction_against_request()`
- `_score_local_corpus_match_against_request()`
- `_build_score_breakdown()`
- `_build_decision_trace()`
- `_build_ranking_context()`
- `_matrix_fit_score()`
- `_literature_specificity_score()`
- `_target_chemistry_fit_score()`
- `_system_match_score()`
- `_missing_data_penalty()`

## Scope

Backend ranking only:

- feature semantics
- ranking weights
- score/debug metadata
- pairwise fixture tests
- local corpus and open-access final ranking behavior after candidate extraction

## Explicit Non-Goals

- Do not change OpenAlex query planning in this slice.
- Do not change extraction heuristics.
- Do not implement learned ranking.
- Do not make the frontend compute scores.

## Decision-Complete Implementation Approach

### 1. Define Three Score Layers In Code Comments Or Helpers

Keep final output compatible, but separate internal concepts:

- retrieval relevance: how likely the paper/record matched the request before extraction
- method viability/trust: whether extraction produced a complete method with evidence
- final fit: whether the method is useful for the requested analyte, matrix, detector, system, runtime, and impurities

Implementation options:

- add fields to `RecommendationDecisionTrace` if schema already has room
- or include under existing trace/debug fields without breaking public contract

Do not remove existing score fields unless all app consumers are checked.

### 2. Reduce Lexical Double-Counting

Recommended first pass:

- keep `matrix_fit` focused on extracted sample/matrix evidence
- keep `literature_specificity` focused on paper/title/request method specificity
- keep `target_chemistry_fit` focused on molecular/entity match, not broad title overlap where possible
- move title/abstract screening contribution into `retrieval_score` or `screening_summary`, not final scientific fit

### 3. Decide Trust Prior Behavior

Choose one:

- assign a small bounded weight, for example `0.02` to `0.04`, and rebalance elsewhere
- or remove `review_trust_prior` from displayed ranking labels while preserving near-tie review-backed preference

Preferred behavior:

- trust should help within near ties
- trust should not beat a clearly better scientific fit
- existing `REVIEW_BACKED_NEAR_TIE_EPSILON = 0.02` should remain explicit and tested

### 4. Add Pairwise Ordering Fixtures

Add tests in `tests/test_recommendation_engine.py` or a new fixture-backed test file.

Pairwise cases:

- exact caffeine match with better system fit beats exact caffeine match with worse system fit
- review-backed near-tie beats seeded record within epsilon
- clinical plasma method beats plant/food carotenoid paper after both pass screening
- complete method with evidence beats partial extraction even if title match is strong
- local corpus target plus impurity match beats target-only when impurity is requested

### 5. Update Golden Scores Deliberately

`tests/fixtures/recommendation_golden_cases.json` pins exact score numbers.

If weights change:

- run `tests/test_recommendation_golden_cases.py`
- inspect differences
- update expected numbers only when ordering and rationale are correct
- document score-shape change in this plan under Decision Notes

## Validation Matrix

```bash
cd services/method-development
uv run pytest -q tests/test_recommendation_engine.py tests/test_recommendation_golden_cases.py tests/test_retrieval_store.py
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
```

Run paper extraction to ensure extraction quality was not accidentally affected:

```bash
uv run python run_paper_example_evaluation.py
```

## Risks And Rollback Strategy

Risk: score changes may make demos look different.

Mitigation:

- preserve candidate ordering before changing displayed numbers where possible
- use pairwise tests as the primary truth
- update exact numeric golden fixtures only after reviewing rationales

Rollback:

- restore previous `RANKING_FEATURE_WEIGHTS`
- keep added pairwise fixtures as expected-failing notes only if needed for follow-up.

## Decision Notes

- 2026-04-23: added explicit score-layer trace metadata for retrieval relevance, method viability, and final fit while preserving existing scalar score fields.
- 2026-04-23: gave `review_trust_prior` a bounded `0.03` ranking weight and retained `REVIEW_BACKED_NEAR_TIE_EPSILON = 0.02` as the explicit near-tie sort policy.
- 2026-04-23: narrowed `matrix_fit` to extracted evidence snippets and field evidence instead of title/request overlap. The carotenoid plasma golden fixtures now score `matrix_fit = 0.0` because the current extractor does not recover separate sample/matrix evidence outside the paper title; ordering remains unchanged.
- 2026-04-23: narrowed `literature_specificity` to title and method-specific evidence snippets, and limited title-based target support to specific method-title matches rather than broad title overlap.

## Definition Of Done

- ranking feature meanings are documented in code or schema comments
- pairwise ranking tests pass
- golden fixtures pass with intentional score expectations
- no frontend score computation is introduced

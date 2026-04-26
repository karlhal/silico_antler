# Method Development Test Suite

## Purpose
This folder holds tests for the HPLC method-development service.

## Intent
- Validate retrieval-domain contracts and service behavior.
- Keep tests deterministic and fixture-driven.
- Catch regressions in schema validation, chemistry normalization, retrieval, ingestion, extraction, and validation logic.
- Use small local fixtures to exercise representative journal-style HTML and PDF ingestion paths.
- Cover extraction heuristics with focused fixtures so parser changes stay explainable and deterministic.
- Keep recommendation acceptance cases in fixture-backed tests so ranking, scaling, and trust regressions are visible before heuristic changes land.
- Keep cross-source scaling checks in focused recommendation tests so `open_access`, `local_files`, and `local_corpus` do not drift into different user-facing formulas.

## Agent Evaluation Suite
The agent evaluation suite (`run_agent_eval_suite.py`) provides a backend-first flywheel for testing complex agent behaviors across recommendation and orchestration.

### Usage
```bash
uv run python run_agent_eval_suite.py --suite smoke|core|extended [--json-output <path>]
```

### Coverage
- **Recommendation**: local_files, open_access, screening_skip, fetch_degraded, no_trustworthy_candidates, local_corpus_exact_match, local_corpus_impurity_ranking, and request_invalid.
- **Orchestration**: review_record_reuse, approve_and_promote, budget_cutoff, and ai_observer_summary.

The suite uses deterministic mocks for open-access search, fetch, and LLM observer calls to ensure results are repeatable.

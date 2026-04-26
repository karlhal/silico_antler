---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development apps/agent recommendation validation tuning
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
  - ./2026-04-22-agent-ranking-scoring-retrieval-refresh.md
  - ./2026-04-21-open-access-demo-failure-analysis.md
  - ./2026-04-26-agent-backend-slice-01-eval-status-hardening.md
  - ./2026-04-26-agent-backend-slice-02-open-access-shortlist-quality.md
  - ./2026-04-26-agent-backend-slice-03-ranking-calibration.md
  - ./2026-04-26-agent-backend-slice-04-demo-corpus-growth.md
  - ./2026-04-26-agent-backend-slice-05-diagnostics-surfacing.md
---

# Agent Backend Validation And Tuning Plan Set

## Goal And Success Criteria

Prepare the method-development backend for reliable scientist-facing demos and follow-on tuning by implementing the remaining recommendation quality work as vertical slices.

Success means:

- a fresh agent can pick one slice and start implementation without rediscovering the codebase
- backend evals clearly distinguish quality regressions from expected live open-access uncertainty
- known demo cases are deterministic enough for live presentation
- ranking and skip diagnostics become easier to tune with evidence rather than ad hoc score changes

## Current State Snapshot

The recommendation backend lives in `services/method-development`.

Core files:

- `app/recommendation_engine.py`: recommendation orchestration, open-access screening, final ranking, local-corpus candidate building
- `app/recommendation_schemas.py`: request, report, runtime, candidate, trust, score, discovery schemas
- `app/recommendation_runtime.py`: runtime metadata and branch decision tracking
- `app/open_access_client.py`: OpenAlex search and source artifact fetching
- `app/recommendation_context_optimizer.py`: open-access run planning, evidence units, extraction/cache helpers
- `app/hplc_text_extraction.py`: text-first HPLC extraction
- `app/retrieval_store.py`: seeded and review-promoted local corpus retrieval
- `app/review_record_materialization.py`: approved review record to retrieval record conversion
- `app/recommendations_router.py`: synchronous and job-based recommendation API shaping

Existing eval and debug commands:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite smoke --json-output /tmp/silico-agent-eval-smoke.json
uv run python run_agent_eval_suite.py --suite core --json-output /tmp/silico-agent-eval-core.json
uv run python run_paper_example_evaluation.py
uv run python run_paper_prompt_check.py --prompt "Extract the final LC-MS/MS method for carotenoids in plasma"
uv run python run_method_recommendation_cli.py recommend --request "..." --json --debug
```

Recent verification from 2026-04-23:

- smoke eval: `3/3` passed
- core eval: `11/12` passed
- failing core case: `recommendation.open_access_fetch_degraded`
- paper example extraction: `66/69` matched, aggregate `0.957`
- prompt checks correctly select the MDPI carotenoid fixture and PLOS glucose fixture

Known demo-safe examples:

- local fixture: carotenoids and fat-soluble vitamins in human plasma, LC-MS/MS
- exact live/open-access query: PLOS glucose Shewanella PMP derivatization paper, returned score `0.764`, validation `needs_review`
- live metformin human plasma can return a candidate, but validation was `unvalidated`, so use as secondary only

Known live-open-access risk:

- broad live prompts with small budgets returned `no_trustworthy_candidates` for carotenoids, glucose, metformin, and paclitaxel
- open-access should be framed as best-effort unless using exact title-like queries or cached/promoted corpus entries

## Slice Order

Implement in this order:

1. `2026-04-26-agent-backend-slice-01-eval-status-hardening.md`
2. `2026-04-26-agent-backend-slice-02-open-access-shortlist-quality.md`
3. `2026-04-26-agent-backend-slice-03-ranking-calibration.md`
4. `2026-04-26-agent-backend-slice-04-demo-corpus-growth.md`
5. `2026-04-26-agent-backend-slice-05-diagnostics-surfacing.md`

The first slice fixes correctness and observability in the existing harness. The second improves which papers get fetched. The third makes score behavior easier to tune. The fourth builds more deterministic demo inventory. The fifth exposes enough UI/operator diagnostics to explain what happened.

## Global Non-Goals

- Do not build de novo method generation in these slices.
- Do not move ranking logic into `apps/agent`.
- Do not make an unconstrained LLM the final ranker.
- Do not widen network/security defaults.
- Do not hide open-access failures behind silent fallback results.

## Global Validation Matrix

Run per slice as specified in the slice plan. Before considering the plan set complete:

```bash
cd services/method-development
uv run pytest -q
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
uv run python run_paper_example_evaluation.py

cd ../../apps/agent
npm run build
```

If docs or agent instruction files are changed:

```bash
cd /Users/nick/silico_website/silico
npm run agent:harness:check
```

## Decision Notes

- 2026-04-23: prioritize deterministic backend validation before additional UI polish.
- 2026-04-23: do not treat live OpenAlex failures as inherently bugs; treat misleading runtime status, bad shortlist ordering, extractor crashes, and hidden diagnostics as bugs.
- 2026-04-23: exact-title open-access queries can be useful in demos, but local fixtures and promoted local corpus records remain the reliable path.

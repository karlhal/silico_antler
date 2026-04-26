---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development demo corpus review promotion fixtures
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-22-agent-review-and-corpus-growth-spec.md
  - ./2026-04-21-open-access-demo-failure-analysis.md
---

# Slice 04: Demo Corpus Growth And Promotion

## Goal And Success Criteria

Build a small set of deterministic, professionally credible HPLC/LC-MS demo cases by converting known-good papers into review-backed or fixture-backed corpus records.

Success means:

- at least three demo cases can run without relying on fragile live OpenAlex search
- each case has a clear paper title, analyte/matrix, method family, score, trust state, and caveat
- local corpus recommendations can demonstrate exact match, similarity, scaling, and review-backed provenance
- open-access remains available for live exploration, but the demo no longer depends on it

## Current Context

Existing local fixtures:

- `services/method-development/tests/paper_example/Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html`
- `services/method-development/tests/paper_example/ijms-17-01719.pdf`
- `services/method-development/tests/paper_example/Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization _ PLOS One.html`
- `services/method-development/tests/paper_example/paper_test2.pdf`

Existing gold files:

- `services/method-development/tests/paper_example/expected/mdpi_carotenoid_method.json`
- `services/method-development/tests/paper_example/expected/plos_glucose_method.json`
- `services/method-development/tests/paper_example/expected/evaluation_prompts.json`

Existing seeded corpus:

- `services/method-development/app/data/seed_methods.json`

Current seed records include:

- ethanol
- isopropanol
- acetone
- caffeine
- several metformin HILIC/RP-LC examples

Review/promotion implementation files:

- `app/review_records_router.py`
- `app/review_record_store.py`
- `app/sqlite_review_record_store.py`
- `app/review_record_materialization.py`
- `app/c12_orchestration.py`
- `app/c12_orchestration_router.py`
- `app/retrieval_store.py`

Useful commands:

```bash
cd services/method-development
uv run python run_demo_smoke.py
uv run python run_demo_smoke.py --fixture tests/paper_example/Development\ of\ an\ Advanced\ HPLC–MS_MS\ Method\ for\ the\ Determination\ of\ Carotenoids\ and\ Fat-Soluble\ Vitamins\ in\ Human\ Plasma.html --debug
uv run python run_paper_example_evaluation.py
uv run python run_method_recommendation_cli.py recommend --request "..." --paper-dir tests/paper_example --json --debug
```

## Scope

Backend corpus and fixtures:

- identify 3 to 5 demo cases
- create or promote review-backed records
- add deterministic eval cases
- document exact demo prompts and expected outputs

## Explicit Non-Goals

- Do not claim production scientific validation.
- Do not add model weights or private external assets.
- Do not rely on a live network call for the core demo path.
- Do not bulk-ingest a large paper corpus in this slice.

## Decision-Complete Implementation Approach

### 1. Define The Demo Case Set

Minimum set:

1. Carotenoids and fat-soluble vitamins in human plasma, LC-MS/MS
   - best for evidence-rich extraction and scaled method presentation
   - source: existing MDPI HTML/PDF fixture
2. Glucose in Shewanella media with PMP derivatization, RP-HPLC
   - best for selected-final-method vs optimization discussion
   - source: existing PLOS HTML/PDF fixture
3. Metformin in human plasma, HILIC or LC-MS/MS
   - best for local-corpus exact/similarity and HILIC preference
   - source: existing seeded records initially; live paper can be review candidate later

Optional set:

- caffeine local-corpus exact match for a fast simple query
- ethanol plus acetone impurity to demonstrate mixture-aware local-corpus retrieval

### 2. Decide Storage Strategy

Preferred for demo:

- keep paper fixtures under `tests/paper_example`
- create review-backed records through existing review/promotion flow when possible
- avoid manually editing `seed_methods.json` unless creating small synthetic retrieval bootstrap records is explicitly desired

If adding seed records:

- keep titles honest as seeded/demo records
- include evidence snippets and validation status
- avoid implying peer-reviewed provenance if the record is synthetic

### 3. Add Deterministic Eval Cases

Extend:

- `tests/fixtures/agent_eval_dataset.json`
- `tests/fixtures/recommendation_golden_cases.json`
- `tests/paper_example/expected/evaluation_prompts.json`

Add coverage for:

- carotenoid local file recommendation
- glucose local file recommendation
- local corpus metformin HILIC recommendation
- optional impurity-aware local corpus demonstration

Expected outputs should include:

- top paper/record id
- trust state
- validation status
- minimum evidence count where applicable
- score/rationale fragments rather than only exact score where score calibration is still changing

### 4. Create A Demo Runbook

Add or update a doc only if useful, likely under `docs/` or `services/method-development/README.md`.

Include exact commands and prompts:

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final LC-MS/MS method for carotenoids in human plasma" \
  --analyte-name "carotenoids" \
  --matrix "human plasma" \
  --require-ms \
  --paper-dir tests/paper_example \
  --json --debug
```

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization" \
  --analyte-name "glucose" \
  --preferred-mode rp_lc \
  --paper-dir tests/paper_example \
  --json --debug
```

For app demo:

- use `local_corpus` when demonstrating deterministic recommendations
- use exact-title `open_access` only when explicitly showing live literature uncertainty

## Validation Matrix

```bash
cd services/method-development
uv run python run_paper_example_evaluation.py
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
uv run pytest -q tests/test_recommendation_golden_cases.py tests/test_paper_example_evaluation.py tests/test_paper_example_review.py
```

If app demo behavior is touched:

```bash
cd apps/agent
npm run build
```

## Risks And Rollback Strategy

Risk: demo corpus looks synthetic or over-claimed.

Mitigation:

- label seeded records as seeded
- label local file extraction as paper-backed but still needs review
- keep validation/trust caveats visible

Risk: adding exact numeric golden cases makes later ranking calibration noisy.

Mitigation:

- prefer ordering and rationale-fragment assertions for new cases until slice 03 is complete

Rollback:

- remove new fixture/eval entries without touching core recommendation code.

## Definition Of Done

- three demo cases have exact prompts, expected result IDs, and validation commands
- smoke/core evals include the core demo path
- demo guidance says which cases are deterministic and which are live best-effort

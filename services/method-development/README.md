# Method Development Service

Hosted backend service for HPLC method-development retrieval, literature ingestion, structured extraction, and future recommendation workflows.

## Dev

```bash
cd services/method-development
uv sync --group dev
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

Why this command:

- `apps/agent` proxies `/method-dev/*` to port `8001`
- the checked-in dependencies do not currently include the extra needed for the `fastapi` CLI
- `USE_MILVUS=false` avoids local Milvus file-lock issues during routine app testing and falls back to the seeded retrieval store

For local LLM-backed demo work, copy `services/method-development/.env.example` to a local `.env` and load it into your shell before starting the service:

```bash
cd services/method-development
cp .env.example .env
set -a
source .env
set +a
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

For a command-line smoke test of the current demo path without starting a separate server process:

```bash
cd services/method-development
uv run python run_demo_smoke.py
```

The smoke test loads `services/method-development/.env` if present, validates the AI runtime settings, runs the C12 orchestration flow against a built-in fixture, and confirms the approved and promoted review-backed record is retrievable. When `SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION=true`, it also performs a live connectivity probe against the configured LLM provider before the orchestration call.

For paper-level extraction benchmarking against the two example papers under `tests/paper_example`:

```bash
cd services/method-development
uv run python run_paper_example_evaluation.py
```

This command writes a detailed scorecard to `services/output/method-development/paper-example-evaluation.json` so you can compare the current extractor output against the curated gold fixtures.

For the core backend-first agent evaluation flywheel, including recommendation and orchestration behavior:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite smoke|core|extended
```

This command executes deterministic evaluation cases against the current recommendation and orchestration logic, writes a JSON scorecard, and exits non-zero on mismatches. Use `--suite smoke` for a fast representative check or `--suite core` for full behavior coverage.

For a Rich-based side-by-side review of the remaining mismatches and the sample positive/negative prompts:

```bash
cd services/method-development
uv run python run_paper_example_review.py
```

For a quick prompt-style benchmark check against the two example papers:

```bash
cd services/method-development
uv run python run_paper_prompt_check.py --prompt "Extract the final LC-MS/MS method for carotenoids in plasma"
```

If you omit `--prompt`, the script will ask interactively.

For a real CLI-first recommendation loop using local papers:

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Recommend an LC-MS/MS method for carotenoids in human plasma" \
  --analyte-name "carotenoids" \
  --matrix "human plasma" \
  --require-ms \
  --paper-dir tests/paper_example
```

For open-access discovery mode:

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Recommend an HPLC method for glucose derivatization analysis" \
  --analyte-name "glucose" \
  --open-access-search \
  --max-papers 3
```

Use `--json` to get machine-readable output from the same CLI.

## Deterministic Demo Corpus

Use these cases when the demo must avoid live OpenAlex variability:

| Case | Source | Prompt | Expected result | Caveat |
| --- | --- | --- | --- | --- |
| Carotenoids and fat-soluble vitamins in human plasma | local paper fixture | `Extract the final LC-MS/MS method for carotenoids in human plasma` | `Development-of-an-Advanced-HPLC-MS_MS-Method-for-the-Determination-of-Carotenoids-and-Fat-Soluble-Vitamins-in-Human-Plasma`, trust `local_file_extracted` | Paper-backed extraction; still marked for manual verification. |
| Glucose in Shewanella media with PMP derivatization | local paper fixture | `Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization` | `paper_test2`, trust `local_file_extracted` | Paper-backed extraction; fixture title is file-derived and validation is `needs_review`. |
| Metformin in human plasma by HILIC LC-MS/MS | seeded local corpus | `Recommend a HILIC LC-MS/MS method for metformin in human plasma` | `seed-metformin-hilic-beh-amide`, trust `seeded_corpus` | Seeded demo record, not a claim of production scientific validation. |

Recommended validation commands:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_agent_eval_suite.py --suite core
uv run pytest -q tests/test_recommendation_golden_cases.py tests/test_paper_example_evaluation.py tests/test_paper_example_review.py
```

Direct CLI checks for the paper-backed cases:

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final LC-MS/MS method for carotenoids in human plasma" \
  --analyte-name "carotenoids" \
  --matrix "human plasma" \
  --require-ms \
  --paper tests/paper_example/Development\ of\ an\ Advanced\ HPLC–MS_MS\ Method\ for\ the\ Determination\ of\ Carotenoids\ and\ Fat-Soluble\ Vitamins\ in\ Human\ Plasma.html \
  --json --debug
```

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization" \
  --analyte-name "glucose" \
  --preferred-mode rp_lc \
  --paper tests/paper_example/paper_test2.pdf \
  --json --debug
```

For an interactive CLI that prompts you for the request and lets you toggle `local` vs `open_access` mode:

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py
```

You can also call the explicit interactive subcommand:

```bash
uv run python run_method_recommendation_cli.py interactive
```

In interactive `local` mode, if you leave the paper directory blank, the CLI now defaults to the bundled demo corpus in `tests/paper_example` so you can test the product immediately.

For local agent-app work, the service should listen on `http://127.0.0.1:8001`.

## Operator Playbooks

Common tasks for maintaining and debugging the service.

### Local Recommendation Debugging

When a recommendation run behaves unexpectedly (e.g., unexpected fallback or poor scoring), use the `--debug` flag to see the internal branch decisions and diagnostic metadata.

```bash
uv run python run_method_recommendation_cli.py recommend \
  --request "..." \
  --debug
```

In the output, look for the **Runtime Diagnostics** panel. It contains `branch_decisions` which explain why the engine chose specific candidates or triggered a fallback.

### Replaying Problem Cases

If a specific literature source (HTML or PDF) is causing extraction issues, use the smoke test with the `--fixture` flag to isolate and replay the orchestration flow against that single file.

```bash
uv run python run_demo_smoke.py --fixture path/to/problematic_paper.html --debug
```

This bypasses the full discovery loop and focuses strictly on the C12 orchestration and extraction steps for that fixture.

### Machine-Readable Monitoring

For automated health or regression monitoring, use the `--json` flag on helper scripts to get machine-readable output.

```bash
uv run python run_demo_smoke.py --json
uv run python run_agent_eval_suite.py --suite smoke --json-output scorecard.json
```

### Corpus Maintenance

1. **Identify**: Use `GET /review-records` or the internal UI to find approved records.
2. **Promote**: Use the `/promotion` endpoint (see [Operator Promotion Workflow](#operator-promotion-workflow)) to add them to the recommendation corpus.
3. **Verify**: Run a recommendation query that should now return the promoted record.

## Scaling Backend (Milvus)

The service now supports [Milvus](https://milvus.io/) (via Milvus Lite) for high-performance chemical similarity search. This provides near-constant search time even as the document corpus grows to thousands of records.

To enable Milvus:
1. Ensure `pymilvus` and `milvus-lite` are installed (`uv sync`).
2. Set `USE_MILVUS=true` in your environment.
3. (Optional) Set `MILVUS_DB_PATH` to your desired database file (defaults to `silico_retrieval.db`).

### Migration

To migrate your current seed methods to Milvus:

```bash
uv run python migrate_to_milvus.py
```

### Benchmarking

To compare the performance of the in-memory store vs Milvus:

```bash
uv run python benchmark_retrieval.py
```

## Roadmap

### Phase 1: Recommendation MVP (Current)
- **Enhanced Scoring**: Methods are ranked based on System Match, Analyte Match, Matrix Fit, and Practical Fit.
- **Canonical Scaling**: One backend scaling utility now serves `open_access`, `local_files`, and `local_corpus` recommendation outputs with shared runtime, gradient, notes, and warning fields.
- **Agentic Extraction**: Custom "C12" orchestration for reliable method extraction from scientific literature.
- **Evaluation Harness**: Continuous accuracy measurement against curated "Golden Dataset" fixtures.

### Phase 2: Predictive Capabilities (Deferred)
- **Surrogate ML Model**: Long-term goal to implement `XGraphBoost`/GNN prediction models for novel method generation.
- **Large-Scale Data Collection**: Focus on building a massive, clean dataset of HPLC methods to train future predictive models.

## Tests

```bash
cd services/method-development
uv run pytest -q
```

## Current API

- `POST /recommendation/recommend` runs the recommendation loop across `open_access`, `local_files`, or `local_corpus`, returns ranked candidates in a unified contract, applies one canonical backend scaling payload across source modes, and now reports additive `runtime` metadata plus normalized `search_query_used`, planned query variants and shortlist budget metadata, per-candidate query provenance in discovery and decision traces, and per-paper `skipped_papers` diagnostics for screened, fetch-failed, or extraction-failed open-access candidates.
- `POST /recommendation/jobs` creates an asynchronous recommendation job and returns a `job_id` plus a polling URL immediately.
- `GET /recommendation/jobs/{job_id}` returns the current recommendation job state, stage, progress counters, additive runtime metadata, and the final report once the job completes.
- `POST /retrieval/query` ranks seeded and promoted review-backed method records for a target SMILES plus optional impurity SMILES query, switches to deterministic mixture-aware scoring when impurities are present, and returns a structured `match_rationale` for each hit.
- `POST /source-documents/` registers and ingests inline HTML or base64-encoded PDF source documents.
- `GET /source-documents/{source_document_id}` returns a previously registered in-memory source document.
- `POST /source-documents/{source_document_id}/extract-hplc` runs the current text-first HPLC extractor against a registered source document and returns extracted method components plus chromatography-system candidates, mobile-phase candidates, mobile-phase detail candidates, gradient candidates, timing candidates, anchored entity candidates, molecular-entity drafts with linkage lookup keys, a safe record draft, record validation, and evidence.
- The extractor now also supports a narrow C11 table path for captioned in-document tables, including retention-time tables with extra index columns and multicolumn gradient tables where `%B` must be recovered from structured headers.
- `POST /source-documents/{source_document_id}/review-records` snapshots an extracted source document into a reviewable record.
- `GET /review-records` lists stored review-record summaries.
- `GET /review-records/{review_record_id}` returns a full review-record snapshot with provenance and validation.
- `POST /review-records/{review_record_id}/status` updates the lightweight review state (`draft`, `approved`, `rejected`) and can approve without immediate local-corpus promotion by setting `promote_to_local_corpus=false`.
- `POST /review-records/{review_record_id}/promotion` explicitly promotes or removes an approved review record from the local recommendation corpus.
- `POST /c12/review-records/orchestrate` coordinates registration, review-record creation/reuse, and optional approval/materialization in one deterministic orchestration call.
- The orchestration route now reports per-step state plus an explicit execution budget so retry behavior is bounded instead of open-ended.
- Promoted review records are added to the retrieval corpus from a frozen approved-record snapshot, and `/retrieval/query` now returns a `review_summary` that distinguishes seeded vs review-promoted corpus records.

## Operator Promotion Workflow

Use the review-record endpoints when you want a strong open-access extraction to become part of future `local_corpus` recommendation runs.

1. Create or inspect a review record.
2. Approve it with entity resolutions.
3. Either let approval promote it immediately, or approve first and promote later.

Approve and promote in one call:

```bash
curl -sS -X POST http://127.0.0.1:8000/review-records/review-0001/status \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "approved",
    "entity_resolutions": [
      {
        "local_identifier": "intermediate 2",
        "smiles_string": "c1ccccc1",
        "display_name": "Intermediate 2"
      }
    ]
  }'
```

Approve now, promote later:

```bash
curl -sS -X POST http://127.0.0.1:8000/review-records/review-0001/status \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "approved",
    "promote_to_local_corpus": false,
    "entity_resolutions": [
      {
        "local_identifier": "intermediate 2",
        "smiles_string": "c1ccccc1",
        "display_name": "Intermediate 2"
      }
    ]
  }'
```

Promote or unpromote later:

```bash
curl -sS -X POST http://127.0.0.1:8000/review-records/review-0001/promotion \
  -H 'Content-Type: application/json' \
  -d '{"promote_to_local_corpus": true}'
```

```bash
curl -sS -X POST http://127.0.0.1:8000/review-records/review-0001/promotion \
  -H 'Content-Type: application/json' \
  -d '{"promote_to_local_corpus": false}'
```

## Demo Safety Defaults

- LLM provider configuration belongs on this backend boundary via `services/method-development/.env.example`, not in `apps/marketing` or any `VITE_*` variable.
- `SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION` defaults to `true`; model-backed orchestration still requires provider credentials before any LLM client is created.
- `SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER` selects the backend transport. `openrouter` uses OpenRouter's OpenAI-compatible endpoint and now defaults both planner and worker to `google/gemma-4-31b-it:free`, a free 262k-context Gemma 4 model.
- Blank `SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL=` or `SILICO_METHOD_DEVELOPMENT_WORKER_MODEL=` entries no longer wipe out provider defaults; empty values now fall back to the provider default model automatically.
- `SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED=false` keeps local testing on OpenRouter only, so Gemini, Groq, and Z.AI quotas are not consumed when those keys are present.
- `SILICO_METHOD_DEVELOPMENT_QUERY_PLANNER_PARALLELISM` runs multiple query-planner calls at the same time and merges unique planned searches; keep it at `1` for OpenRouter free models because every planner call counts against the free request quota.
- `SILICO_METHOD_DEVELOPMENT_EXTRACTION_CONCURRENCY=2` is the current OpenRouter-free default for extracting shortlisted papers in parallel; raising it further increases LLM and fetch pressure. OpenRouter currently caps `:free` model variants at 20 requests/minute and either 50 free-model requests/day or 1000/day after the account has purchased at least $10 credits.
- `SILICO_METHOD_DEVELOPMENT_FULL_DOCUMENT_LLM_FALLBACK_LIMIT=8` controls how many shortlisted papers may use full-document PDF LLM recovery after targeted extraction fails. The fallback still only runs for PDFs without deterministic method parameters, but it now covers the full default shortlist instead of only the target number of viable recommendations.
- OpenRouter PDF recovery sends the PDF URL or original PDF bytes through OpenRouter's `file-parser` plugin with the free `cloudflare-ai` engine. If OpenRouter rejects or cannot parse the file, the service converts the PDF locally with PyMuPDF4LLM and asks the worker model to normalize that Markdown before falling back to the older text-only full-document prompt. HPLC validation and ranking still run locally after parser-backed extraction.
- `SILICO_METHOD_DEVELOPMENT_OPEN_ACCESS_TIMEOUT_SEC` bounds live literature search and fetch operations, while `SILICO_METHOD_DEVELOPMENT_ENABLE_RUNTIME_DEBUG_METADATA` controls whether extra runtime branch metadata is returned for local diagnosis.
- `SILICO_METHOD_DEVELOPMENT_LLM_TIMEOUT_SEC`, `SILICO_METHOD_DEVELOPMENT_LLM_MAX_CALLS_PER_RUN`, `SILICO_METHOD_DEVELOPMENT_MAX_STEP_ATTEMPTS_PER_RUN`, and `SILICO_METHOD_DEVELOPMENT_MAX_TOTAL_STEPS_PER_RUN` define the demo guardrails.
- The C12 orchestration flow applies server-side caps to request budgets, so callers cannot widen retries beyond the backend safety settings.
- When LLM orchestration is enabled, the current model-backed branch only adds an observer summary and fallback extraction assist on top of the deterministic C12 result; it does not replace the core extraction, validation, or approval logic.

## Runtime Persistence

- Review records persist by default to `tmp/method-development/review_records.json`.
- Override the path with `SILICO_METHOD_DEVELOPMENT_REVIEW_RECORDS_PATH` when needed.
- Approved review records persist with an immutable materialized retrieval-record snapshot, and only records marked as promoted are rehydrated into the retrieval corpus from that frozen artifact on service startup.

## Notes

- This service is intentionally separate from `apps/api`, which remains the lightweight public backend for marketing, demo, contact, and analytics flows.
- Retrieval-first MVP work lives here, including chemistry normalization, retrieval schemas, ingestion, extraction, and validation.
- Heavy scientific dependencies should stay scoped to this service unless they become truly shared primitives.

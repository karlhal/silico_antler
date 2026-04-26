# Agent App Deep-Dive

Date: 2026-04-19

Scope:
- `apps/agent`
- `services/method-development`
- supporting `apps/api` lookup behavior only where it affects the agent flow

## Executive Summary

The biggest quality issues in the current agent app are not visual. They are retrieval and ranking quality problems in the method-development service plus a few app-side choices that make the workflow feel slower and less explainable than it really is.

The highest-signal findings were:

1. Open-access relevance is still driven mostly by lexical title/abstract heuristics.
2. The backend had explicit artificial sleeps between paper attempts.
3. The frontend enforced a multi-second minimum wait even after a job had already completed.
4. Degraded runs were not being marked as degraded, which hid important fallback behavior.
5. The agent-mode payload compaction dropped skipped-paper diagnostics in the UI metadata layer.

This pass fixed the low-risk regressions and left the larger scoring roadmap below.

## Fixed In This Pass

### 1. Query builder regressions

Files:
- `services/method-development/app/recommendation_engine.py`

What was wrong:
- `_build_search_queries()` had drifted away from the expected high-precision behavior.
- It stopped preferring clean, title-like request text for exact literature-style prompts.
- The first heuristic query lost important anchors such as `quantification`.
- Family-term expansion cases were not reliably surfacing `bioanalytical` and related clinical anchors.

Impact:
- Broader or lower-signal search queries reach OpenAlex.
- Irrelevant papers have a better chance of surviving early screening.

What changed:
- Restored a cleaned exact-request query path for title-like prompts.
- Reintroduced stronger method anchors in the primary query.
- Preserved family-term and clinical-context expansions in the generated query set.

Validation:
- The previously failing query-builder tests now pass.

### 2. Degraded runtime status was under-reported

Files:
- `services/method-development/app/recommendation_engine.py`

What was wrong:
- Fetch failures, extraction failures, and HTML-to-PDF fallbacks were recorded as branch decisions but not consistently marked as degraded.
- That meant runs could succeed with partial failure or fallback behavior while still reporting `completed` instead of `completed_with_degraded_source`.

Impact:
- The UI could show a clean live result even when the engine had already encountered blocked pages, fallback extraction, or partial source loss.
- This made debugging harder and weakened operator trust.

What changed:
- Degraded state is now set when the pipeline hits fetch failure, extraction failure, or HTML-to-PDF fallback paths.

Validation:
- The degraded-runtime tests now pass.

### 3. Agent UI lost discovery diagnostics in agent-mode responses

Files:
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `services/method-development/app/recommendations_router.py`

What was wrong:
- The backend intentionally strips full `discovered_papers` and `skipped_papers` arrays for `response_detail=agent`.
- The frontend metadata builder only looked at those stripped arrays and ignored `discovery_summary`.

Impact:
- The agent UI dropped skipped-paper previews and accurate discovered-paper counts.
- That made it harder to understand why the engine skipped irrelevant papers or why nothing useful survived extraction.

What changed:
- `buildReportMeta()` now uses `discovery_summary.skipped_papers_preview` and `discovery_summary.discovered_paper_count` when the full arrays are compacted away.

### 4. Artificial latency padding

Files:
- `services/method-development/app/recommendation_engine.py`
- `apps/agent/src/hooks/useAgentWorkflow.ts`

What was wrong:
- The backend inserted `time.sleep(1.0)` between open-access extraction attempts.
- The frontend enforced a `MIN_DISCOVERY_MS = 4500` wait even after the backend had already finished.

Impact:
- Slow feel even when the underlying work is done.
- Local-corpus runs are especially affected because they can be fast but still feel slow.

What changed:
- Removed the explicit one-second backend sleeps.
- Reduced the frontend post-completion floor to a short anti-flicker delay instead of a multi-second hold.

## Bugs Found

### Fixed bugs

1. Open-access query generation regression.
   - Evidence: six focused recommendation-engine tests were failing before the patch set.
   - Result: fixed.

2. Degraded runtime status was not set for partial-failure runs.
   - Evidence: degraded-path tests expected `completed_with_degraded_source` but received `completed`.
   - Result: fixed.

3. Agent-mode report metadata dropped skip diagnostics.
   - Evidence: compacted backend responses zeroed `skipped_papers`, while the frontend metadata builder ignored `discovery_summary`.
   - Result: fixed.

4. Perceived latency was inflated by intentional waits.
   - Evidence: explicit sleeps in both the backend recommendation loop and the frontend workflow hook.
   - Result: reduced.

### Remaining bugs or sharp edges

1. `OpenAccessPaperClient` creates a fresh `httpx.Client` for each search call and each fetch call.
   - Files:
     - `services/method-development/app/open_access_client.py`
   - Effect:
     - No connection reuse across the query/fetch sequence.
     - Extra TLS and redirect overhead during live runs.

2. Open-access de-duplication is weaker than it should be.
   - Files:
     - `services/method-development/app/recommendation_engine.py`
   - Current behavior:
     - candidates are de-duped by `(doi, paper_id, title)` together.
   - Problem:
     - the same work can still survive as separate candidates when IDs or titles vary across sources.
   - Better behavior:
     - canonicalize DOI first, then normalized URL, then title fallback.

3. Agent-mode still only returns the top three candidates.
   - Files:
     - `services/method-development/app/recommendations_router.py`
   - Effect:
     - Great for payload size, not great for auditability.
     - The UI cannot fully expose ranking tails or full skip diagnostics during debugging.

## Why Irrelevant Papers Still Slip Through

## 1. Screening is mostly lexical

Files:
- `services/method-development/app/recommendation_engine.py`

Current screening inputs:
- title
- abstract
- source name

Current screening signals:
- analyte token overlap
- matrix token overlap
- chromatography keywords
- MS keywords
- broad-scope penalties
- non-primary-literature penalties

Why that is not enough:
- It works for obvious misses.
- It struggles on semantically close but wrong literature, for example:
  - plant/tissue/pigment papers for a clinical plasma request
  - broad chemistry or composition papers that mention the analyte family but not a final validated method
  - review-like or survey-like papers that still contain lots of method vocabulary

The main issue:
- lexical overlap is doing too much work before extraction.
- there is no stronger semantic or structure-aware reranker between “search result” and “expensive extraction attempt”.

## 2. Final ranking double-counts some text-driven signals

Files:
- `services/method-development/app/recommendation_engine.py`

The final score blends:
- target chemistry fit
- impurity compatibility
- system fit
- detector compatibility
- matrix fit
- runtime fit
- extraction completeness
- evidence quality
- review trust prior
- literature specificity

Problems:
- `matrix_fit`, `literature_specificity`, and parts of `target_chemistry_fit` are all partly driven by the same descriptor-text overlap.
- `system_match` returns a default midpoint when data is missing, which can flatten the ranking.
- `review_trust_prior` is computed but has zero weight, so it contributes explanation complexity without affecting ranking.

Net effect:
- the ranker looks richer than it really is.
- several features are correlated enough that they can amplify a merely text-relevant paper.

## 3. The open-access search source is too broad for the current precision budget

Files:
- `services/method-development/app/open_access_client.py`

Current behavior:
- search OpenAlex with `search=<query>` and `filter=is_oa:true`
- sort by OpenAlex relevance

This is pragmatic, but broad:
- no fielded search
- no query-time negative constraints
- no per-query diversification rules
- no host/source trust prior beyond fetchability ranking

That means precision depends heavily on query quality and local screening heuristics.

## Where The Time Goes

## 1. Open-access runs are still fully serial

Files:
- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/open_access_client.py`

Current flow:
1. search query 1
2. search query 2
3. search query 3
4. screen all results
5. fetch shortlisted paper 1
6. extract paper 1
7. fetch shortlisted paper 2
8. extract paper 2
9. continue linearly

Even after removing the explicit sleeps, the architecture is still serial.

Practical consequence:
- latency grows roughly linearly with the number of shortlisted papers
- a blocked or slow publisher can stall the entire open-access path

## 2. Connection reuse is missing

Files:
- `services/method-development/app/open_access_client.py`

Every search and fetch creates a new client:
- extra handshake overhead
- less efficient redirect-heavy publisher flows

## 3. The app was adding delay after completion

Files:
- `apps/agent/src/hooks/useAgentWorkflow.ts`

This was especially noticeable for:
- `local_corpus` runs
- any future cached or fast-path recommendations

## Best Next Improvements

## High ROI

1. Add a real reranking layer before extraction.
   - Input:
     - title
     - abstract
     - year
     - source host
     - generated query that matched
   - Output:
     - relevance score
     - matrix confidence
     - “final method paper” confidence

2. Reuse one HTTP client per recommendation run.
   - Keep a single `httpx.Client` alive across search and fetch.
   - This is a low-risk latency improvement.

3. Add bounded concurrency for fetch/extract.
   - Fetch the top 2 to 4 shortlisted papers in parallel.
   - Stop once enough viable candidates are found.
   - This matters more than micro-optimizing the current scoring math.

4. Improve de-duplication.
   - Canonical DOI
   - normalized landing page URL
   - normalized PDF URL
   - fallback fuzzy title key

5. Promote better diagnostics into the agent UI.
   - show per-query search variants attempted
   - show top skipped-paper reasons
   - show how many papers were screened, fetched, extracted, and rejected

## Medium ROI

1. Build a matrix ontology instead of raw token overlap.
   - Example:
     - `human plasma`
     - `plasma`
     - `serum`
     - `whole blood`
     - `plant tissue`
     - `food extract`
   - Use family-aware proximity rather than literal token overlap.

2. Separate ranking into clearer layers.
   - Retrieval relevance
   - Method applicability
   - Extraction trust
   - System adaptation fit

3. Revisit feature weights.
   - `review_trust_prior` should either matter or disappear from the ranking explanation.
   - missingness should be uncertainty-aware rather than a neutral midpoint.

4. Track paper provenance by query.
   - Which query produced this paper?
   - Did it survive because of analyte match, matrix match, or pure OpenAlex relevance?

## Creative Ideas Worth Trying

1. Hard-negative query repair.
   - If the first screened batch is dominated by plant/food literature, issue a repair query tuned for clinical bioanalysis.

2. Candidate family clustering.
   - Avoid spending extraction budget on five near-duplicate papers from the same topic family or journal source.

3. Extraction-aware reranking.
   - Do a very cheap evidence sniff first:
     - look for method tables
     - look for gradient/runtime clues
     - look for detector/mode clues
   - Only run full extraction on papers with actual method-bearing evidence.

4. Continuous corpus flywheel.
   - Every approved review-backed open-access extraction should strengthen the local corpus.
   - Over time, shift more traffic from open-access search to trusted local retrieval plus near-neighbor expansion.

## Recommended Follow-Up Sequence

## Sprint 1

1. Reuse one `httpx.Client` per run.
2. Add canonical DOI/URL de-duplication.
3. Add per-query provenance to search results and runtime metadata.
4. Keep the agent UI showing discovery-summary previews.

## Sprint 2

1. Add lightweight reranking before extraction.
2. Add bounded fetch/extract concurrency.
3. Refactor score layers so the explanation matches the actual ranking logic.

## Sprint 3

1. Add matrix ontology and analyte-family playbooks.
2. Feed approved open-access results back into the local corpus more aggressively.
3. Add a “why this paper was skipped” operator/debug view.

## Validation Run From This Pass

Checks run:

```bash
cd apps/agent
npm run build

cd services/method-development
uv run pytest -q tests/test_recommendation_engine.py tests/test_retrieval_store.py
```

Results:
- `apps/agent`: build passed
- `services/method-development`: 30 focused tests passed

Not run:
- full method-development test suite
- live OpenAlex network profiling
- end-to-end browser workflow timing

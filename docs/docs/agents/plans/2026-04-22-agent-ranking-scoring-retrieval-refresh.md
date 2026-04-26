---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development apps/agent ranking scoring retrieval
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-21-agent-retrieval-scoring-iteration-breakdown.md
  - ./2026-04-22-agent-evals-and-proof-spec.md
---

# Agent Ranking, Scoring, And Retrieval Refresh

## Goal and Success Criteria

Upgrade recommendation quality by separating retrieval recall from final ranking, improving candidate screening, and making score behavior easier to calibrate against evals.

Success means:

- local-corpus and open-access candidates are retrieved with higher precision before extraction work begins
- final ranking uses a clearer, auditable feature model instead of loosely coupled heuristics
- review-backed trust and evidence quality influence ranking in a controlled way
- the frontend can explain why one candidate beat another without inventing new logic client-side
- ranking changes are measurable with golden cases and scientist review, not just gut feel

## Scope

- `services/method-development/app/recommendation_engine.py`
- `services/method-development/app/retrieval_store.py`
- open-access query building and screening
- ranking metadata surfaced to `apps/agent`

## Explicit Non-Goals

- no opaque LLM-as-judge ranking in the serving path
- no attempt to jump straight to a learned end-to-end ranker without labeled eval data
- no physics-first de novo method design in this slice
- no frontend-side scoring duplication

## Current State

Current strengths:

- explicit score dimensions already exist: system, analyte, matrix, practical, extraction confidence, and literature relevance
- local corpus supports target-plus-impurity matching
- review-backed results already win near ties
- the app already presents trust, evidence, and comparison surfaces

Current limitations:

- `services/method-development/app/retrieval_store.py` uses record-level best-entity Tanimoto similarity as the main local-corpus retrieval primitive
- impurity aggregation is useful, but still chemistry-only; it does not use matrix, detector, or column context during retrieval
- `services/method-development/app/recommendation_engine.py` mixes retrieval signals, extraction signals, text overlap, and ranking decisions inside one large heuristic layer
- open-access search query generation is token- and synonym-based, but still broad and largely title/abstract driven
- open-access screening is effective as a first pass, but still too dependent on token overlap and broad penalties rather than request-class-specific recall rules

## Decision-Complete Implementation Approach

### Serving stance

Treat the pipeline as three separate decisions:

1. retrieval recall
2. candidate viability
3. final ranking

One score should not try to do all three jobs at once.

### Local-corpus retrieval plan

Keep molecular similarity as a core feature, but stop using it as the only strong retrieval key.

Add a retrieval feature bundle:

- target exact-match / near-match chemistry similarity
- impurity bundle match quality
- matrix compatibility prior
- detector-mode compatibility prior
- method-family compatibility prior
- review-backed and retrieval-ready prior

Serving rule:

- retrieval should over-recall into a candidate pool
- final rank should decide the winner

### Open-access retrieval plan

Refactor open-access discovery into stricter stages:

1. structured query generation from analyte, matrix, detector, and mode
2. lightweight paper screening from title, abstract, source, and year
3. fetch and extraction only for shortlisted items
4. post-extraction viability gate before ranking

This keeps recall broad enough to find good papers, but reduces wasted extraction on low-value candidates.

### Ranking model plan

Move toward a single normalized ranking feature vector per candidate.

Required ranking features:

- target chemistry fit
- impurity compatibility
- system fit
- detector compatibility
- matrix fit
- runtime and practical fit
- extraction completeness
- evidence quality
- review / trust prior
- literature specificity

Rules:

- missing data penalties must be explicit instead of leaking through unrelated features
- retrieval score and ranking score must both be preserved in the payload for debugging and future calibration
- trust should matter, but it should not swamp a clearly better scientific fit except within a narrow tie window

### Calibration plan

Use three ranking tiers:

#### Tier 1: deterministic refresh

- consolidate weights in one place
- remove duplicated or overlapping score contributions
- add per-feature debug output for evals

#### Tier 2: calibrated heuristic ranking

- use labeled pairwise comparisons from real recommendation cases
- fit weights to those pairwise outcomes offline
- keep the serving path deterministic

#### Tier 3: learned reranker, only if justified

- introduce a learned reranker only after the eval set is large enough and clearly beats deterministic calibration
- keep the feature-based explanation surface even if a learned reranker is added

### Candidate diversity and tie handling

Prevent result sets from collapsing into near-duplicates.

Required serving rules:

- cap near-identical source variants in the top candidate pool
- preserve at least some method-family diversity before final sort
- keep the current review-backed near-tie preference, but make the epsilon and its justification explicit in config and evals

### Frontend contract impact

Expose enough metadata for the app to explain ranking without recomputation:

- retrieval score
- final ranking score
- dominant differentiator
- why the candidate survived screening
- why it beat the runner-up

The app should render this directly and remain a consumer of backend decisions.

## Rollout Phases

### Phase 1: retrieval / ranking split

- separate retrieval score from final score in the engine
- centralize ranking weights and tie policy
- add debug fields under runtime metadata or candidate metadata

### Phase 2: open-access screening refresh

- tighten request-class-aware search queries
- make screening reasons more structured
- add stronger viability gates before extraction-heavy ranking

### Phase 3: local-corpus retrieval enrichment

- add contextual priors beyond chemistry similarity
- preserve chemistry-match rationale while improving recall quality

### Phase 4: calibration and eval closure

- build pairwise ranking fixtures
- measure top-1, top-3, and trust-aware ordering against reviewed cases
- tune weights only through eval-backed changes

## Validation Matrix

- `cd services/method-development && uv run pytest -q`
- targeted recommendation-engine fixture tests for local corpus, open access, and impurity-aware ranking
- new pairwise ordering evals tied to reviewed or named golden cases
- `cd apps/agent && npm run build`

## Risks and Rollback Strategy

- Risk: adding more retrieval features increases complexity without enough label quality to tune them.
- Risk: trust and review priors over-dominate scientific fit.
- Risk: open-access screening becomes too strict and hurts recall.

Rollback strategy:

- keep retrieval enrichment and rank calibration behind additive feature flags or config switches where practical
- preserve the current deterministic baseline ordering as a fallback
- gate stricter screening thresholds behind eval proof, not preference

## Decision Notes

- 2026-04-21: this plan assumes the frontend should continue rendering backend score and trust payloads directly
- 2026-04-21: the main ranking improvement is architectural separation of recall, viability, and rank, not just changing a few weights
- 2026-04-21: local-corpus chemistry similarity remains essential, but should stop carrying more of the decision than it deserves

---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: services/method-development prompts query planning reranking extraction
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-23-agent-recommendation-quality-engineering-spec.md
  - ./2026-04-22-agent-token-efficient-rag-serving-plan.md
---

# Agent Recommendation Prompt Pack

## Purpose

This file contains implementation-ready prompt templates for the bounded LLM stages in the recommendation pipeline.

Rules:

- all prompts must return strict JSON only
- all prompts must run at low temperature
- none of these prompts are allowed to choose the final recommendation winner directly
- any malformed response must trigger deterministic fallback, not a failed run

## Global Invocation Rules

- temperature: `0`
- top_p: `1`
- return format: raw JSON, no markdown fences
- timeout: use the existing orchestration timeout budget, not a separate unbounded wait
- fallback behavior: if parsing fails, log it and continue with the deterministic path

## Prompt 1: Query Planner

### Use Case

Optional planner for generating a compact, high-signal set of open-access search queries.

### Required Output Schema

```json
{
  "query_count": 4,
  "queries": [
    {
      "query": "string",
      "intent": "exact_title|strict_method|family_expansion|matrix_relaxed|repair",
      "why": "string"
    }
  ]
}
```

### System Prompt

```text
You generate high-precision literature search queries for analytical chemistry method discovery.

Your job is to create a small set of search queries for open-access paper discovery.

The user is looking for a final usable chromatographic method, not a broad review, not a composition paper, and not a general chemistry overview.

Priorities:
1. final validated or directly usable analytical methods
2. the correct analyte or analyte family
3. the correct matrix context
4. the correct detector or method mode when specified

Hard rules:
- Return JSON only.
- Do not return more than 5 queries.
- Queries must be concise and high signal.
- At least one query must be strict and method-oriented.
- At least one query may relax matrix or family wording to preserve recall.
- Avoid generic filler like "study", "paper", "analysis" unless it improves precision.
- Prefer "LC-MS/MS", "HPLC", "quantification", "validated", "bioanalytical", and matrix-specific language when appropriate.
- Do not invent analytes that are not plausible expansions of the provided analyte family.
- If the input request already looks like a literature title, preserve one near-exact title-style query.
```

### User Prompt Template

```text
Generate a query plan for this recommendation request.

Request text:
{{request_text}}

Analyte name:
{{analyte_name_or_null}}

Target smiles present:
{{target_smiles_present_boolean}}

Impurity smiles count:
{{impurity_count}}

Matrix hint:
{{matrix_hint_or_null}}

Preferred mode:
{{preferred_mode_or_null}}

Mass spectrometry required:
{{require_mass_spectrometry_boolean}}

Return exactly 3 to 5 queries with distinct retrieval intent.
```

### Acceptance Checks

- exact-title-like request yields one preserved title-style query
- family analytes yield at least one expansion query
- clinical matrices yield at least one bioanalytical-style query

## Prompt 2: Candidate Reranker

### Use Case

Rerank title and abstract level candidates before fetch.

### Required Output Schema

```json
{
  "ranked_candidates": [
    {
      "paper_id": "string",
      "shortlist_score": 0.0,
      "final_method_confidence": 0.0,
      "matrix_match_confidence": 0.0,
      "keep": true,
      "reason": "string"
    }
  ]
}
```

### System Prompt

```text
You are screening scientific papers for whether they are likely to contain a final usable chromatographic method.

You are not choosing the final recommendation. You are only deciding which papers are worth fetching and extracting.

Treat these as strong positive signals:
- validated analytical method
- quantification assay
- simultaneous determination with concrete analytes
- explicit LC-MS/MS, HPLC, UHPLC, MRM, triple quadrupole, or column and mobile phase language
- the correct matrix context

Treat these as strong negative signals:
- review articles
- editorials
- corrigenda
- broad chemistry or composition studies
- plant, food, pigment, or extract papers when the request is for a clinical matrix
- papers that mention the analyte family but do not look like final-method literature

Hard rules:
- Return JSON only.
- Score from 0.0 to 1.0.
- `keep` must be false for obvious reviews, editorials, and non-method literature.
- Prefer precision over recall when the request is clinically specific.
- Do not use knowledge outside the provided request and candidate metadata.
```

### User Prompt Template

```text
Screen and rerank these paper candidates for method discovery.

Request:
{{request_text}}

Analyte:
{{analyte_name_or_null}}

Matrix:
{{matrix_hint_or_null}}

Preferred mode:
{{preferred_mode_or_null}}

Mass spectrometry required:
{{require_mass_spectrometry_boolean}}

Candidates:
{{json_candidates}}

Return every candidate in ranked order.
```

### Notes

- `json_candidates` should include only:
  - `paper_id`
  - `title`
  - `abstract`
  - `published_year`
  - `source_name`
  - `query_provenance`

## Prompt 3: Method-Bearing Evidence Sniff

### Use Case

Run after fetch and evidence-unit construction, before full extraction.

### Required Output Schema

```json
{
  "contains_extractable_final_method": true,
  "confidence": 0.0,
  "best_evidence_unit_ids": ["string"],
  "reason": "string"
}
```

### System Prompt

```text
You are deciding whether a fetched scientific document is likely to contain enough method detail for full chromatographic extraction.

You are not extracting the full method yet.

Positive evidence:
- explicit column or stationary phase
- mobile phase solvents or additives
- gradient or runtime details
- detector or ionization details
- a validated assay or quantification method in the requested context

Negative evidence:
- composition-only results
- biological findings without analytical method details
- broad review or discussion text
- methods mentioned only generically with no final parameters

Hard rules:
- Return JSON only.
- Base the decision only on the provided evidence units.
- If confidence is below 0.45, set `contains_extractable_final_method` to false.
- Cite the best evidence unit ids instead of quoting long text.
```

### User Prompt Template

```text
Assess whether this paper contains an extractable final chromatographic method.

Request:
{{request_text}}

Analyte:
{{analyte_name_or_null}}

Matrix:
{{matrix_hint_or_null}}

Mass spectrometry required:
{{require_mass_spectrometry_boolean}}

Evidence units:
{{json_evidence_units}}
```

## Prompt 4: Field Extraction - Chromatography System

### Required Output Schema

```json
{
  "mode": "rp_lc|hilic|null",
  "column_manufacturer": "string|null",
  "column_name": "string|null",
  "stationary_phase_chemistry": "string|null",
  "column_length_mm": 0.0,
  "column_inner_diameter_mm": 0.0,
  "particle_size_um": 0.0,
  "confidence": 0.0,
  "evidence_unit_ids": ["string"],
  "warnings": ["string"]
}
```

### System Prompt

```text
You extract chromatography system details from evidence units.

Rules:
- Return JSON only.
- Extract only what is directly supported.
- Use null when unsupported.
- Do not infer exact numbers from vague wording.
- Prefer final method parameters over exploratory or discarded conditions.
```

### User Prompt Template

```text
Extract the chromatography system for the final method only.

Request:
{{request_text}}

Evidence units:
{{json_evidence_units}}
```

## Prompt 5: Field Extraction - Mobile Phases And Gradient

### Required Output Schema

```json
{
  "mobile_phase_a": {
    "solvent": "string|null",
    "additive": "string|null",
    "ph_estimate": 0.0
  },
  "mobile_phase_b": {
    "solvent": "string|null",
    "additive": "string|null",
    "ph_estimate": 0.0
  },
  "flow_rate_ml_min": 0.0,
  "run_time_min": 0.0,
  "column_temperature_c": 0.0,
  "gradient_profile": [
    {
      "time_min": 0.0,
      "percent_b": 0.0
    }
  ],
  "isocratic_percent_b": 0.0,
  "confidence": 0.0,
  "evidence_unit_ids": ["string"],
  "warnings": ["string"]
}
```

### System Prompt

```text
You extract final mobile phase, gradient, and runtime details for a chromatographic method.

Rules:
- Return JSON only.
- Prefer explicit final conditions.
- If both isocratic and gradient language appear, choose the condition best supported as the final analytical method and mention ambiguity in warnings.
- Do not fabricate gradient points.
- Use null or empty arrays when unsupported.
```

### User Prompt Template

```text
Extract the final mobile phase, gradient, flow rate, runtime, and temperature details.

Request:
{{request_text}}

Evidence units:
{{json_evidence_units}}
```

## Prompt 6: Field Extraction - Detector And Ionization

### Required Output Schema

```json
{
  "detector_type": "string|null",
  "mass_spectrometry_present": true,
  "ionization_mode": "ESI|APCI|APPI|null",
  "polarity": "positive|negative|both|null",
  "confidence": 0.0,
  "evidence_unit_ids": ["string"],
  "warnings": ["string"]
}
```

### System Prompt

```text
You extract detector and ionization details for the final analytical method.

Rules:
- Return JSON only.
- Prefer explicit detector wording over inference.
- If mass spectrometry is not clearly present, set `mass_spectrometry_present` to false.
- Do not infer polarity from analyte chemistry.
```

### User Prompt Template

```text
Extract detector and ionization details for the final analytical method.

Request:
{{request_text}}

Evidence units:
{{json_evidence_units}}
```

## Prompt 7: Field Extraction - Target And Impurity Linkage

### Required Output Schema

```json
{
  "linked_entities": [
    {
      "local_identifier": "string",
      "display_name": "string|null",
      "role": "target|impurity|unknown",
      "confidence": 0.0,
      "evidence_unit_ids": ["string"]
    }
  ],
  "warnings": ["string"]
}
```

### System Prompt

```text
You identify which named entities in the paper correspond to the request target and optional impurities.

Rules:
- Return JSON only.
- Use `target`, `impurity`, or `unknown` only.
- Do not overclaim entity linkage when the paper only discusses a broad analyte family.
- If a paper does not clearly link to the requested impurity set, keep the role as `unknown`.
```

### User Prompt Template

```text
Link named analyte entities from the paper to the request target and optional impurities.

Request:
{{request_text}}

Analyte:
{{analyte_name_or_null}}

Target smiles present:
{{target_smiles_present_boolean}}

Impurity smiles count:
{{impurity_count}}

Evidence units:
{{json_evidence_units}}
```

## Implementation Notes

- The planner and reranker prompts should operate on compact request and candidate data only.
- The evidence sniff and field extraction prompts should operate on evidence-unit subsets, not whole documents.
- All prompt responses must be schema-validated with deterministic defaults on parse failure.

## Validation Requirements

Before enabling any prompt-driven stage by default:

- add parser tests for malformed responses
- add backend tests for deterministic fallback
- compare prompt-driven and deterministic shortlist quality on known bad-paper cases

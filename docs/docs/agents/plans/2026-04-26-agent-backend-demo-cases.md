---
status: active
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: services/method-development apps/agent demo cases HPLC recommendation
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-26-agent-backend-validation-tuning-plan-set.md
  - ./2026-04-26-agent-backend-slice-04-demo-corpus-growth.md
  - ./2026-04-21-open-access-demo-failure-analysis.md
---

# Agent Backend Demo Cases

## Purpose

This file defines the HPLC/LC-MS demo cases to use with life-science professionals while the backend is still being tuned.

Use these cases to show:

- evidence-backed paper retrieval
- final method extraction
- scaling to available hardware
- trust and validation posture
- open-access uncertainty without over-claiming reliability

## Demo Stance

Use deterministic paths for the main demo:

- `local_files` for paper-backed extraction from known fixtures
- `local_corpus` for fast recommendation from seeded or promoted records

Use `open_access` only for:

- exact-title paper lookup
- best-effort live literature diagnostics
- showing skipped-paper and degraded-source behavior

Do not lead with broad live OpenAlex search unless the goal is explicitly to show current limitations.

## Pre-Demo Validation

Run these before the demo:

```bash
cd services/method-development
uv run python run_agent_eval_suite.py --suite smoke
uv run python run_paper_example_evaluation.py
```

Expected as of 2026-04-23:

- smoke eval: `3/3` passed
- paper example evaluation: `66/69` matched, `0.957` aggregate match ratio

Optional broader check:

```bash
uv run python run_agent_eval_suite.py --suite core
```

Known current issue:

- core eval was `11/12` on 2026-04-23
- failing case: `recommendation.open_access_fetch_degraded`
- this is a runtime status semantics issue, not a blocker for deterministic demo cases

## Case 1: Carotenoids And Fat-Soluble Vitamins In Human Plasma

### Why Use It

This is the strongest main demo case. It is a real LC-MS/MS method paper with rich method details, strong extraction coverage, and a clear clinical matrix.

Use it to show:

- final method extraction from a paper
- LC-MS/MS method details
- mobile phases and gradient
- retention-time evidence
- method scaling to a Waters-style system
- trust caveat: paper-backed extraction still needs scientific review

### Recommended Demo Mode

Primary:

- source mode: `local_files`
- source: bundled MDPI HTML fixture

Secondary:

- source mode: exact-title `open_access`
- only use if network behavior is acceptable and there is time to discuss degraded-source caveats

### Prompt

```text
Extract the final LC-MS/MS method for carotenoids and fat-soluble vitamins in human plasma.
```

### CLI Command

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final LC-MS/MS method for carotenoids and fat-soluble vitamins in human plasma" \
  --analyte-name "carotenoids and fat-soluble vitamins" \
  --matrix "human plasma" \
  --require-ms \
  --col-manuf "Waters" \
  --col-name "XBridge BEH C18" \
  --col-chem "C18" \
  --col-len 100 \
  --col-id 2.1 \
  --col-psize 3.5 \
  --paper "tests/paper_example/Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html" \
  --json --debug
```

### Expected Result

Expected paper:

```text
Development of an Advanced HPLC-MS/MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma
```

Expected DOI:

```text
10.3390/ijms17101719
```

Expected behavior:

- recommendation status: `completed`
- trust state: `local_file_extracted`
- validation likely requires review
- scaled flow and runtime should be present
- rationale should mention system fit, analyte fit, practical fit, and runtime

Known fixture score from golden cases:

- total score around `0.692` for local fixture golden case
- scaled flow around `0.13 mL/min`
- scaled run time around `20.0 min`
- gradient points: `8`

### Presenter Notes

Say:

```text
This is the reliable paper-backed path. The agent is not inventing a method; it is extracting a published method, checking fit against the requested system, and making the scaling assumptions visible.
```

Avoid saying:

```text
This is a validated method ready to run without review.
```

## Case 2: Glucose Derivatization By RP-HPLC

### Why Use It

This is a good second case because it demonstrates that the system can distinguish a selected final method from optimization-heavy paper content.

Use it to show:

- RP-HPLC, not LC-MS/MS
- derivatization-specific method retrieval
- selected/final method extraction
- why exact paper/title context matters for live search

### Recommended Demo Mode

Primary:

- source mode: `local_files`
- source: bundled PLOS HTML fixture

Secondary:

- exact-title `open_access`
- this succeeded in live probing on 2026-04-23 with degraded-source caveats

### Prompt

```text
Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization.
```

### CLI Command

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization" \
  --analyte-name "glucose" \
  --preferred-mode rp_lc \
  --paper "tests/paper_example/Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization _ PLOS One.html" \
  --json --debug
```

### Exact Open-Access Command

```bash
cd services/method-development
uv run python run_method_recommendation_cli.py recommend \
  --request "Extract the final RP-HPLC method for glucose in Shewanella oneidensis cultures utilizing PMP derivatization" \
  --analyte-name "glucose" \
  --preferred-mode rp_lc \
  --open-access-search \
  --search-query "Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization" \
  --max-papers 8 \
  --json --debug
```

### Expected Result

Expected paper:

```text
Development of a RP-HPLC method for determination of glucose in Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone derivatization
```

Expected DOI:

```text
10.1371/journal.pone.0229990
```

Live exact open-access result observed on 2026-04-23:

- status: `completed_with_degraded_source`
- score: `0.764`
- trust state: `open_access_extracted`
- validation: `needs_review`
- discovered papers: `7`
- skipped papers: `7`

### Presenter Notes

Say:

```text
This is a useful case for talking with method-development scientists because the paper contains optimization context. The important product behavior is selecting the final usable method rather than treating every experimental condition as equally authoritative.
```

If using live open-access, say:

```text
This is a live literature path. The degraded-source status is expected when some open-access hosts are blocked or incomplete; the useful point is that the system exposes those failures instead of hiding them.
```

## Case 3: Metformin In Human Plasma

### Why Use It

This is useful as a local-corpus or HILIC/RP-LC comparison case. It is less strong as a live open-access case today because the live result may be `unvalidated`.

Use it to show:

- local-corpus retrieval
- HILIC preference
- multiple possible methods for the same analyte
- ranking tradeoffs

### Recommended Demo Mode

Primary:

- source mode: `local_corpus`
- use existing seeded metformin records

Secondary:

- live `open_access` only as a “candidate found, needs review” example

### Prompt

```text
Find a HILIC-MS/MS method for metformin in human plasma.
```

### Backend Request Shape

Use this in app/API contexts:

```json
{
  "request_text": "Find a HILIC-MS/MS method for metformin in human plasma",
  "analyte_name": "metformin",
  "target_smiles": "CN(C)C(=N)N=C(N)N",
  "matrix_hint": "human plasma",
  "preferred_mode": "hilic",
  "require_mass_spectrometry": true,
  "source_mode": "local_corpus",
  "system_specs": {
    "column_manufacturer": "Waters",
    "column_name": "Acquity BEH Amide",
    "column_chemistry": "HILIC",
    "column_length_mm": 100.0,
    "column_inner_diameter_mm": 2.1,
    "particle_size_um": 1.7,
    "detector_types": ["MS/MS"]
  }
}
```

### Expected Local Corpus Records

Seeded records currently include:

- `seed-metformin-hilic-beh-amide`
- `seed-metformin-rplc-ion-pair`
- `seed-metformin-hilic-zic`
- `seed-metformin-hilic-beh-gradient`

Expected behavior:

- recommendation should prefer a metformin HILIC-compatible record when `preferred_mode` is `hilic`
- score/rationale should expose system and practical fit
- trust state should be seeded/local corpus, not open-access extracted

### Live Open-Access Observation

Live `max_papers=8` probe on 2026-04-23 returned:

```text
OPTIMIZATION OF LC-MS/MS METHOD FOR THE SIMULTANEOUS DETERMINATION OF METFORMIN AND ROSIGLITAZONE IN HUMAN PLASMA WITH BOX-BEHNKEN DESIGN
```

Observed:

- status: `completed_with_degraded_source`
- score: `0.745`
- validation: `unvalidated`
- discovered papers: `8`
- skipped papers: `53`

Use this only if discussing open-access uncertainty and review workflow.

### Presenter Notes

Say:

```text
For repeated lab use, the product should become stronger as reviewed methods enter the local corpus. This case is useful for showing that direction without depending on live publisher availability.
```

## Case 4: Caffeine Exact Local Corpus Match

### Why Use It

This is a fast, simple local-corpus case for explaining chemistry-native retrieval.

Use it if the audience asks:

- how molecule identity is represented
- whether the system can retrieve prior methods directly
- how local corpus differs from live literature search

### Recommended Demo Mode

- source mode: `local_corpus`
- existing seeded record

### Prompt

```text
Find a method for caffeine.
```

### Backend Request Shape

```json
{
  "request_text": "Find a method for caffeine",
  "analyte_name": "caffeine",
  "target_smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
  "source_mode": "local_corpus",
  "system_specs": {
    "column_manufacturer": "Waters",
    "column_name": "Acquity BEH C18",
    "column_chemistry": "C18",
    "column_length_mm": 100.0,
    "column_inner_diameter_mm": 2.1,
    "particle_size_um": 1.7
  }
}
```

### Expected Result

Expected record:

```text
seed-caffeine-rp18
```

Expected behavior from core eval:

- status: `completed`
- trust state: `seeded_corpus`
- top record: `seed-caffeine-rp18`
- match rationale includes exact molecular match

### Presenter Notes

Say:

```text
This path is deterministic and fast because it searches reviewed or seeded local method records. It is the right path when a lab has built its internal method memory.
```

## Case 5: Ethanol With Acetone Impurity

### Why Use It

This is useful for showing target-plus-impurity ranking in the local corpus.

Use it if the audience cares about:

- impurity separation
- mixture-aware retrieval
- why a target-only method may not be enough

### Recommended Demo Mode

- source mode: `local_corpus`
- test fixture builds target-only and multi-analyte records
- production/demo corpus should eventually include a persistent multi-analyte example

### Prompt

```text
Find a method for ethanol with acetone as an impurity.
```

### Backend Request Shape

```json
{
  "request_text": "Find a method for ethanol with acetone as an impurity",
  "analyte_name": "ethanol",
  "target_smiles": "CCO",
  "impurity_smiles": ["CC(=O)C"],
  "source_mode": "local_corpus",
  "system_specs": {
    "column_manufacturer": "Waters",
    "column_name": "Acquity BEH C18",
    "column_chemistry": "C18",
    "column_length_mm": 100.0,
    "column_inner_diameter_mm": 2.1,
    "particle_size_um": 1.7
  }
}
```

### Expected Result

Core eval fixture expects:

- recommended paper/record id: `record-multi-analyte`
- ranking mode: `target_plus_impurities`
- impurity count: `1`

Important caveat:

- this specific multi-analyte record is created inside the eval harness
- to use this in the app demo, add or promote a persistent corpus record first

### Presenter Notes

Say:

```text
The retrieval layer can treat impurities as first-class constraints instead of searching only by the target analyte. This is important because a method that detects the target may still be a poor starting point if it does not separate the impurity family.
```

## Cases To Avoid As Main Demo

### Broad Caffeine In Organic Solvent

Reason:

- historically pulls broad coffee chemistry and compositional papers
- poor open-access precision

### Broad Carotenoids In Human Plasma Without Exact Title

Reason:

- with small live budgets, current OpenAlex retrieval can find broad metabolomics or biomarker papers rather than the known MDPI method
- use exact-title open-access or local fixture instead

### Broad Glucose HPLC Without Derivatization Context

Reason:

- current live search finds many glucose sensors, sugar quantification, and review-like papers
- the known PLOS paper can be displaced by newer equal-score papers
- use exact-title or local fixture

### Paclitaxel In Human Plasma

Reason:

- live probe on 2026-04-23 returned `no_trustworthy_candidates`
- discovered papers included related taxane/docetaxel and nanovesicle papers, not a clean final paclitaxel plasma method

## Suggested Demo Flow

1. Start with Case 1, carotenoids local fixture.
2. Show the extracted method, scaled method, evidence, and trust caveat.
3. Run Case 2, glucose derivatization local fixture or exact-title open-access.
4. Explain selected final method vs optimization context.
5. Switch to Case 4 or Case 3 for local corpus.
6. Explain the corpus flywheel: reviewed methods become reusable retrieval records.
7. If time allows, run exact-title open-access and point out degraded-source diagnostics.

## Open-Access Framing

Use this language:

```text
Live open-access search is intentionally transparent. If a source blocks fetches, if a paper does not contain a complete final method, or if extraction cannot recover mobile phases and flow rate, the system reports that instead of pretending it has a trustworthy method.
```

Do not use this language:

```text
The agent always finds the best paper live.
```

## Follow-Up Implementation Needs

To make these cases stronger:

- fix runtime status semantics from slice 01
- improve open-access tie-breaking from slice 02
- add persistent demo corpus records from slice 04
- surface query/skipped-paper diagnostics from slice 05

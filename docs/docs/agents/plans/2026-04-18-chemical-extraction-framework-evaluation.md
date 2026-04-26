---
status: completed
owner: platform
last_verified: 2026-04-18
last_updated: 2026-04-18
applies_to: services/method-development
source_of_truth: docs/agents/execution-plans.md
---

# Chemical Extraction Framework Evaluation

## Goal and Success Criteria

Assess whether the HPLC method-development MVP should be built directly on top of existing open-source systems referenced in the specification, specifically:

- `Librarian of Alexandria (LoA)`
- `ChemEAGLE`

Success means making a concrete recommendation on whether to adopt, fork, or build bespoke inspired by these systems.

## Scope and Explicit Non-Goals

In scope:

- public repo/code availability
- apparent maturity and licensing signals
- fit for the retrieval-first HPLC MVP
- what to borrow architecturally

Out of scope:

- a full code audit of either repo
- benchmarking either framework locally
- implementing adapters or integrations

## Findings Summary

Recommendation:

- do not adopt either framework wholesale for the retrieval-first MVP
- build the product core bespoke in `services/method-development`
- borrow the best ideas from both systems selectively

High-level split:

- `LoA` is closer to our literature retrieval and schema-driven extraction needs
- `ChemEAGLE` is stronger as inspiration for future multimodal agent orchestration

Best current stance:

- bespoke retrieval
- bespoke ingestion/extraction pipeline
- selective borrowing of patterns
- no framework-level dependency until there is a clear reason

## Evidence Reviewed

### LoA

Public repo evidence:

- GitHub repo found: `https://github.com/arwalkerlab/LoA-Stable`
- Repo description: "The unchanged version of LoA released along with the paper."
- Visible signals from repo page:
  - public repo
  - 3 releases
  - 15 commits on main
  - folders for `src`, `dataModels`, `job_scripts`, `paper_data`
  - README emphasizes scraping, schema-based extraction, resumability, local-doc processing, and DECIMER-assisted image SMILES insertion

Observed weaknesses:

- README install flow still says a `requirements.txt` will be created later
- clone instructions reference `MorganRO8/LoA.git` while the visible public repo is `arwalkerlab/LoA-Stable`
- no obvious CI/testing signals from the public landing page
- no obvious license surfaced on the public repo page content fetched here
- environment/setup looks research-heavy and conda-first

Fit assessment:

- good conceptual fit for literature retrieval and schema-configured extraction
- weak fit as a direct production dependency for our service boundary today

### ChemEAGLE

Public repo evidence:

- GitHub repo found: `https://github.com/CYF2000127/ChemEagle`
- Repo description: "This is the official code of the paper 'A Multi-Agent System Enables Versatile Information Extraction from the Chemical Literature'"
- Visible signals from repo page:
  - public repo
  - MIT license
  - 267 commits on main
  - 87 stars / 15 forks at fetch time
  - explicit agent decomposition in README
  - supports PDF and image-based extraction
  - includes planner, observer, specialized extraction agents, and multiple toolkits

Observed weaknesses:

- still looks research-oriented rather than productionized
- no obvious CI/test posture from the repo landing page
- depends on heavy multimodal models and external downloads
- architecture is centered on broad chemical literature and reaction/image extraction, not HPLC-first prose/table extraction

Fit assessment:

- strong inspiration for future multimodal orchestration
- overbuilt and misaligned for the retrieval-first MVP if adopted directly now

## Detailed Recommendation

### LoA: Use As Inspiration, Not As A Base Repo

Borrow:

- schema-driven extraction configuration
- retrieval plus extraction pipeline framing
- resumable job execution
- local-doc processing mode
- invalid-result buckets and post-extraction validation ideas

Do not adopt directly because:

- maturity signals are not strong enough for direct service adoption
- licensing clarity is weaker than ideal from the public evidence gathered
- the install/runtime story looks research-first
- we would still need to reshape the product heavily around our HPLC-specific schema, provenance model, and service boundaries

Recommendation:

- bespoke inspired by LoA

### ChemEAGLE: Use As Architectural Inspiration, Not As The MVP Foundation

Borrow:

- planner / specialist-agent / observer decomposition
- modality-specific extraction before unification
- structured output assembly after specialist steps
- validation and consistency checks around tool outputs

Do not adopt directly because:

- it is optimized for multimodal chemical extraction broadly, especially reaction graphics
- our MVP bottleneck is not yet reaction-image understanding, it is reliable HPLC record retrieval and provenance
- we would inherit heavy model/runtime complexity too early

Recommendation:

- bespoke inspired by ChemEAGLE

## What Should Be Bespoke In Our Service

The following should be native to `services/method-development`:

- retrieval schemas
- provenance and page-level evidence model
- chemistry normalization and fingerprinting
- retrieval ranking for target plus impurity inputs
- HPLC validation rules
- storage model for extracted method records
- service HTTP contracts

## What We Should Borrow Conceptually

From LoA:

- job configuration and schema-driven extraction framing
- resumability and local document modes
- verification after extraction

From ChemEAGLE:

- modular extraction steps
- explicit validator/observer roles
- future multimodal orchestration patterns

## Final Decision

For the retrieval-first MVP:

- build bespoke in `services/method-development`
- do not fork either repo as the main product base
- use LoA as the closer reference for early ingestion/extraction shape
- use ChemEAGLE as the stronger reference for later multimodal agent orchestration if and when we reach that stage

In short:

- `LoA`: closer fit, but still not adoptable as-is
- `ChemEAGLE`: better orchestration reference, but too heavy and misaligned for MVP foundation
- product direction: bespoke core, framework-inspired design

## Risks and Revisit Conditions

Revisit the decision if any of the following become true:

- we need image-to-structure extraction as a first-class requirement sooner than expected
- we discover either repo has much stronger tests, licensing clarity, and maintainership than the public surface suggested
- our bespoke extraction pipeline starts recreating large parts of a framework that already works well enough

Until then, the fastest and safest path is to keep the product core bespoke.

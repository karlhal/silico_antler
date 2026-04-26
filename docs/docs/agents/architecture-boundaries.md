---
owner: platform
last_verified: 2026-04-22
applies_to: all-apps
source_of_truth: docs/architecture/repo-structure.md
---

# Architecture Boundaries

## Domain Ownership
- `apps/agent`: retrieval-and-scoring web experience for evidence-backed HPLC method recommendation.
- `apps/api`: hosted API for SMILES resolution and follow-up Q&A.
- `services/method-development`: hosted HPLC retrieval, ingestion, extraction, and validation service.
- `services/surrogate-backend-model`: gradient physics engine and compound prediction data.
- `packages/brand`: shared brand tokens and primitives.

## Dependency Direction
- Apps and services are product boundaries; avoid direct cross-boundary imports.
- Share only neutral primitives through `packages/*`.
- Agent consumes `apps/api` and `services/method-development` through HTTP/runtime contracts, not direct source imports.

## Contract Boundaries
- Agent request/response behavior against `/api` and `/method-dev` is part of the product contract and must stay explicit in docs when it changes.
- Public HTTP/API behavior must remain stable unless intentionally versioned.
- Method-development service HTTP contracts must remain stable for future service consumers unless intentionally versioned.
- Environment variable behavior is part of runtime contract and must be documented.

## Where To Deep Dive
- Repo structure: [`../architecture/repo-structure.md`](../architecture/repo-structure.md)
- Global guidance: [`../../AGENTS.md`](../../AGENTS.md)
- Release/testing conventions: [`./release-and-testing.md`](./release-and-testing.md)

---
status: completed
date: 2026-04-19
owner: platform
last_verified: 2026-04-20
applies_to: apps/agent services/method-development open-access extraction
source_of_truth: docs/agents/execution-plans.md
---

# Open Access Live Extraction to Web UI

## Goal and Success Criteria
**Goal**: Transition the Silico Agent dashboard from a hardcoded simulation to a fully functional interface that performs live Open Access searches, LLM extraction, and physics-based scaling.
**Success Criteria**:
- The web UI natively controls live `open_access` searches by communicating constraints over REST.
- The `method-development` backend router surfaces `recommend_methods`.
- The user is accurately presented with scaled methodology generated dynamically rather than statically sourced.

## Scope and Non-Goals
**Scope**:
- Backend REST API router `app/recommendations_router.py`.
- Hooking the backend `MethodRecommendationRequest` into `app/main.py`.
- Frontend `api.ts` mapping layer from SystemSpecs to backend schema.
- Agent hook `useAgentWorkflow.ts` executing the backend and gracefully unwrapping `report.considered_candidates`.

**Explicit Non-Goals**:
- Expanding retrieval databases for other extraction types.
- Modifying UI design structure (done in prior tasks).

## Implementation Approach
1. **Backend Route Definition**: Created `POST /recommendation/recommend` invoking existing logic within `recommendation_engine.py` using `OpenAccessPaperClient`. Also implemented basic graceful traceback logging for PDF ingestion errors. 
2. **Frontend Orchestration**: In `api.ts`, added `runRecommendationFlow`. The map accounts for Pydantic string validation (e.g., swapping `""` for `null` in `column_name`). The request specifically pulls down `max_papers=10` to handle publishers aggressively rate-limiting PDF parsing bots.
3. **Frontend Presentation**: Handled gracefully missing Open Access papers. If candidates fall out (which happens dynamically when Open/Elsevier blocks us), the UI gracefully guides the user to retry or unset MS/MS constraints instead of showing misleading "Agent error".

## Validation Matrix
- [x] Backend endpoint `POST /recommendation/recommend` exists.
- [x] Tested manually against a robust JSON payload for `Caffeine` simulating `MethodRecommendationRequest`.
- [x] Tested frontend build pipeline `npm run build` succeeds seamlessly indicating strict typing coherence mapping frontend properties accurately.
- [x] Tested fallback logic correctly surfaces an "empty array" warning visually rather than unhandled API errors when API pulls down purely irrelevant or non-OA papers.

## Status Updates
- **2026-04-19**: Implementation and testing completed successfully. Noted that `require_mass_spectrometry` prunes OpenAlex results quite severely in certain contexts.

---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent UI redesign workflow presentation report workspace
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-22-agent-pitch-ui-system-spec.md
  - ./2026-04-22-agent-scientist-copilot-product-spec.md
---

# Agent Clean UI Redesign Plan

## Goal and Success Criteria

Redesign the `apps/agent` experience so it feels cleaner, calmer, and more decision-oriented without hiding the scientific trust story.

Success means:

- the app reads as a scientist workspace rather than a dense diagnostics dashboard
- the top recommendation, why-it-fits logic, and trust posture are obvious within the first screen
- workflow input, live progress, and report review are separated into clearer visual modes
- detailed diagnostics remain available, but they stop competing with primary decision content
- implementation complexity drops by breaking the current monolithic screen into smaller shells and sections

## Scope

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- app-level layout, section hierarchy, status language, disclosure rules, and motion
- report workspace, run composer, and live progress surfaces

## Explicit Non-Goals

- no change to backend scoring math in this plan
- no new scientific claims or product narrative beyond what existing contracts support
- no design-system rewrite across the monorepo
- no investor-deck styling inside the app

## Current State

The app already has strong material to work with:

- ranked recommendation cards
- trust, validation, and review posture
- evidence snippets and diagnostics
- recent runs, export, and runtime-health handling

The main issue is composition and concentration, not missing capability.

Current hotspots:

- `apps/agent/src/pages/Dashboard.tsx` is about 2.8k lines and currently owns launch state, input workflow, runtime banners, progress UI, report workspace, comparison surfaces, trust rail, recent-run history, and export actions
- `apps/agent/src/hooks/useAgentWorkflow.ts` is about 2.0k lines and carries orchestration, persistence, recovery, clarifications, and report-state shaping in one hook
- the current screen places many elements at the same visual weight: pills, bordered panels, notices, cards, disclosures, and diagnostics often compete rather than ladder
- the app uses a lot of status chrome above the fold before the scientist gets to the single most important answer

The result is a product that is feature-rich, but still noisier than it needs to be.

## Decision-Complete Implementation Approach

### Product stance

The redesign should treat the app as a focused scientific workspace with three explicit modes:

1. compose a run
2. watch a run
3. review a report

The user should feel which mode they are in immediately. The current one-screen blend of all three should be reduced.

### Screen model

#### 1. Run Composer

Primary job:

- define system context
- define target and matrix
- choose evidence source

Rules:

- show only one expanded stage at a time
- keep the active stage large and quiet
- demote secondary metadata and helper copy
- move recent runs and runtime health into slim side or top utilities instead of equal-weight hero content

#### 2. Live Run Trace

Primary job:

- show what is happening now
- preserve confidence during waiting

Rules:

- keep one dominant active step
- keep completed steps compact
- do not show all report-level chrome during an in-flight run
- preserve the last good result in the background when rerunning, but visually separate it from live progress

#### 3. Report Workspace

Primary job:

- answer “what should I try and why?”

Rules:

- top recommendation gets the visual center
- ranked alternatives stay visible, but secondary
- trust and evidence stay anchored, not buried
- diagnostics move into a lower-priority utilities layer

### New information hierarchy

The report workspace should be organized into five zones:

1. Recommendation hero
   - title
   - total fit
   - core method summary
   - one-sentence reason it won
   - primary actions only
2. Why it fits
   - system fit
   - analyte fit
   - matrix fit
   - practical fit
   - runner-up comparison
3. Trust and evidence
   - trust state
   - validation posture
   - review posture
   - one visible evidence preview
   - source metadata
4. Ranked alternatives
   - compact list with score delta and one tradeoff sentence
5. Diagnostics and provenance
   - skipped-paper details
   - warnings
   - runtime details
   - extended evidence

### Noise-reduction rules

Apply these as hard constraints:

- one primary CTA per major state
- no more than two notice banners visible at once without explicit user expansion
- pills become grouped metadata rows when they are descriptive rather than actionable
- all diagnostics default below the recommendation narrative
- repeated bordered cards should be reduced; larger section wrappers should do more structural work
- keep a single trust signature surface instead of re-explaining the same trust state in multiple card types

### Visual direction

Keep the current warm/editorial DNA, but simplify the interface:

- fewer hard borders per viewport
- more whitespace between major zones
- stronger contrast between primary and secondary text blocks
- less constant uppercase metadata
- less simultaneous emphasis on both left rail and right detail rail

The redesign should feel quieter, not emptier.

### Component architecture

Refactor the current screen into a smaller set of feature components:

- `RunComposerShell`
- `LiveRunShell`
- `ReportWorkspaceShell`
- `RecommendationHero`
- `WhyItFitsPanel`
- `TrustEvidencePanel`
- `AlternativeList`
- `DiagnosticsDrawer`

Refactor workflow logic into narrower hooks:

- `useWorkflowDraft`
- `useWorkflowRunState`
- `useWorkflowReportState`
- `useWorkflowRecovery`

This is not just code cleanup. It is needed so layout and state can evolve without one 2.8k-line screen fighting every change.

### Rollout phases

#### Phase 1: hierarchy and shell extraction

- split the single `Dashboard` screen into composer, run, and report shells
- keep existing data contracts
- reduce duplicated banners and top-level status surfaces

#### Phase 2: report redesign

- ship the recommendation hero
- rebuild alternatives list and runner-up comparison
- keep trust and evidence anchored in one clearer panel

#### Phase 3: composer cleanup

- simplify stage cards
- tighten copy
- reduce helper chrome
- improve mobile layout and keyboard flow

#### Phase 4: diagnostics retune

- move low-frequency details into drawers or disclosures
- make empty/degraded/error states shorter and more actionable

## Validation Matrix

- `cd apps/agent && npm run build`
- desktop-width manual QA for new run, live run, completed report, degraded runtime, cached result, and demo-safe result
- mobile-width manual QA for composer and report workspace
- verify that backend payloads are rendered directly and no frontend score recomputation is introduced

## Risks and Rollback Strategy

- Risk: oversimplifying the screen hides scientific caveats that advanced users rely on.
- Risk: a major visual rewrite lands before component boundaries are cleaned up, making the code harder to maintain.
- Risk: the recommendation hero becomes too pitch-oriented and stops feeling like real software.

Rollback strategy:

- land shell extraction and hierarchy cleanup before stronger visual changes
- keep diagnostics available behind a stable disclosure until usage proves they can be reduced further
- preserve current report data density in lower sections while simplifying only the first-screen experience

## Decision Notes

- 2026-04-21: this plan is intentionally more implementation-oriented than `agent-pitch-ui-system-spec`; it is about reducing noise in the existing app, not just describing the ideal pitch surface
- 2026-04-21: the current UI problem is hierarchy, not capability gap
- 2026-04-21: the redesign should make the app feel cleaner by subtraction first, not by adding more chrome

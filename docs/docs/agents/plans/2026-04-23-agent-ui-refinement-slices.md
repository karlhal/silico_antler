---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent ui refinement workflow presentation motion
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-22-agent-clean-ui-redesign-plan.md
  - ./2026-04-21-agent-workflow-presentation-hardening.md
  - ./2026-04-22-agent-pitch-ui-system-spec.md
---

# Agent UI Refinement Slices

## Goal and Success Criteria

Preserve the agent app's bottom-composer, chat-adjacent workflow while making it feel more professional, calmer, and more legible for repeated scientific use.

Success means:

- the app still feels like a copilot workflow rather than a form wizard
- the UI feels closer to Codex or Claude in restraint, composure, and state clarity
- the first screen after a completed run answers three questions immediately:
  - what should I try
  - why did it win
  - how trustworthy is it
- active runs feel informative rather than theatrical
- hardware, structure, and trust details stay available without overpowering the main task
- each improvement can ship as an independent slice without backend contract changes

## Scope

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- new presentational components under `apps/agent/src/components/` as needed
- `apps/agent/src/index.css`
- only frontend workflow presentation, motion, hierarchy, and interaction refinements

## Explicit Non-Goals

- no change to recommendation ranking or backend scoring logic
- no new chat backend or general-purpose conversational agent
- no operator-review workflow expansion in this document
- no investor-deck styling inside the product UI
- no removal of the current staged scientific workflow

## Current Read

The app already has a credible foundation:

- the empty state and anchored composer create the right overall interaction model
- the report has strong scientific content and a useful trust payload
- the workflow hook already handles clarifications, reruns, cached recovery, and degraded modes

The main UI issue is not missing capability. It is mixed presentation logic and competing metaphors.

Current friction points:

- the calm editorial shell conflicts with the theatrical hardware drawer and faux instrument-console styling
- top-level notices, status pills, and bordered panels compete for attention above the fold
- the composer keeps the right chat feel, but hides too much context about source mode, structures, and constraints
- clarification questions behave like detached forms instead of part of a serious copilot exchange
- the report makes users tab to understand the recommendation, evidence, and diagnostics instead of leading with a single coherent narrative
- motion and shadows sometimes read as demo polish rather than professional product behavior

## Product Stance

The right direction is not "more visual design." The right direction is better composure.

The app should feel like:

- a serious scientific copilot
- calm under degraded conditions
- explicit about trust and result freshness
- fast to revise and rerun

It should not feel like:

- a lab hardware simulator
- a dashboard full of equally important boxes
- a generic AI app with flashy transitions

## Slice Order

Recommended sequence:

1. shell extraction and mode boundaries
2. composer context and source clarity
3. hardware and structures panel retune
4. inline clarification conversation
5. live-run trace retune
6. report hierarchy rewrite
7. banner and status consolidation
8. motion and polish pass

## Implementable Slices

### Slice 0: Shell Extraction Before Design Changes

Why first:

- the current dashboard is too monolithic for safe UI iteration
- extracting stable shells reduces the risk of mixing presentation cleanup with workflow regressions

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- new files under `apps/agent/src/components/`

Exact prompt:

```text
Refactor the agent dashboard into smaller UI shells before changing behavior. Split `apps/agent/src/pages/Dashboard.tsx` into focused presentational components for the anchored composer, settings panels, live run surface, report workspace, notices, and recommendation detail surfaces. Preserve current behavior, state flow, and backend contracts exactly. Do not change copy, hierarchy, or visual styling in this slice except where extraction requires small mechanical adjustments. The goal is a safer foundation for later UI refinements, not a redesign. Run `cd apps/agent && npm run build` when done.
```

Success criteria:

- no user-facing workflow change
- build passes
- `Dashboard.tsx` becomes materially smaller and easier to reason about
- later UI slices can touch isolated surfaces instead of one 2.8k-line file

### Slice 1: Composer Context Rail and Source Clarity

Intent:

- keep the bottom composer as the primary action surface
- make current run context visible without opening drawers
- remove ambiguity from the current source-mode toggle

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- extracted composer components
- `apps/agent/src/index.css`

Exact prompt:

```text
Keep the anchored bottom composer and chat-like interaction model, but redesign it so the user can understand the current run context at a glance. Add a compact context rail tied to the composer that summarizes source mode, hardware readiness, structure status, matrix, and runtime limit before the user presses Run. Replace the current one-button source toggle with a clear two-option segmented control for `open_access` and `local_corpus`, including short helper copy that explains the difference and signals when local corpus benefits from structure-aware inputs. Do not change workflow contracts, payload shapes, or Enter-to-run behavior. Keep one primary CTA. Run `cd apps/agent && npm run build`.
```

Success criteria:

- above the fold, the user can tell which source mode is active and whether hardware and structure context are present
- source selection no longer behaves like an ambiguous toggle
- the composer still feels like a copilot input box, not a traditional form footer
- no extra backend state is introduced

### Slice 2: Retune Hardware and Structures Panels

Intent:

- preserve fast access to advanced inputs
- remove the current lab-console theatrics that conflict with the editorial shell
- make advanced controls feel closer to serious settings surfaces in Codex or Claude

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- extracted settings components
- `apps/agent/src/index.css`

Exact prompt:

```text
Redesign the hardware and structures editing surfaces so they feel like restrained professional settings panels rather than a theatrical overlay. Keep all existing fields, validation hooks, and one-click access from the composer, but replace the current bottom overlay, faux LCD readout, monospace console treatment, and visually noisy module chrome with calmer sheets or utility panels. When the panels are closed, show concise read-only summaries in the composer context rail so users do not need to reopen them repeatedly. Preserve keyboard access, field semantics, and workflow data exactly. Run `cd apps/agent && npm run build`.
```

Success criteria:

- no faux hardware-simulator styling remains
- advanced inputs remain one interaction away from the composer
- users can understand their current hardware and structure state without reopening panels
- validation issues still attach to the same fields

### Slice 3: Clarification Questions as Inline Copilot Turns

Intent:

- make the agent feel conversational without changing the core workflow
- unify local missing-runtime prompts and backend clarification questions into one interaction pattern

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- small helper/view-model additions if needed

Exact prompt:

```text
Refactor the agent clarification UI so missing-runtime prompts and backend clarification questions render as inline copilot turns inside the main workspace rather than detached alert boxes. The user should see their request, the agent's follow-up question, and the available answer controls as part of one coherent conversation-like flow. Preserve the current `agentPrompt`, `pendingClarification`, and `submitClarification` logic. Do not add new backend calls or invent a general chat transcript product. This is a presentation refinement only. Respect reduced motion and run `cd apps/agent && npm run build`.
```

Success criteria:

- clarification states feel like part of the same copilot interaction
- the user can tell what the agent is waiting on and what happens after answer or skip
- missing-runtime and backend clarification flows share a common visual pattern
- no backend or contract change is required

### Slice 4: Live-Run Trace That Preserves Confidence

Intent:

- make active runs feel calm and informative
- keep the last good result available during reruns
- reduce UI-level theatrics during discovery

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- `apps/agent/src/index.css`

Exact prompt:

```text
Create a clearer live-run mode for the agent app. During discovery, show one dominant active step, compact completed steps, and a concise explanation of what the system is doing now. When rerunning from an existing report, keep the previous report visible in a subdued preserved state instead of replacing it with a full blank progress block. Remove avoidable UI theatrics and minimize artificial waiting once real results are ready. Keep the existing step model, polling model, and backend contracts unless a small frontend-only timing adjustment is needed. Respect reduced motion and run `cd apps/agent && npm run build`.
```

Success criteria:

- the current active step is obvious during a run
- reruns do not erase the last good report
- progress feels calmer and faster than the current multi-card trace
- results appear promptly once the backend is ready

### Slice 5: Report Workspace Hierarchy Rewrite

Intent:

- make the completed report answer the main decision questions on first view
- reduce tab-hunting
- keep diagnostics available without letting them dominate

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- extracted report components
- `apps/agent/src/index.css`

Exact prompt:

```text
Rebuild the completed report layout into five clear zones: recommendation hero, why it fits, trust and evidence, ranked alternatives, and diagnostics/provenance. Keep the existing recommendation payloads, trust rail logic, comparison content, and export/rerun actions, but change the hierarchy so the first screen answers three questions immediately: what should I try, why did it win, and how trustworthy is it. Make one evidence preview visible without tab-switching. Compress alternative candidates into a secondary list with concise tradeoff summaries. Move skipped-paper details, long warnings, and extended provenance lower or behind disclosure. Avoid generic card grids and keep the calm editorial tone. Run `cd apps/agent && npm run build`.
```

Success criteria:

- the top recommendation, its winning rationale, and its trust posture are legible without switching tabs
- one evidence snippet is visible on the main report screen
- runner-up comparison remains available but secondary
- diagnostics are still accessible without competing with primary decision content

### Slice 6: Banner and Status Consolidation

Intent:

- reduce the number of equal-weight status surfaces
- preserve important runtime and result-freshness semantics without cluttering the top of the page

Likely files:

- `apps/agent/src/pages/Dashboard.tsx`
- extracted notice/status components

Exact prompt:

```text
Audit every top-level status surface in the agent dashboard and consolidate runtime health, restore state, stale-result notices, run outcome notices, runtime mode, and result origin into fewer higher-signal surfaces. Keep severe errors and degraded states obvious, but collapse descriptive status chrome into grouped metadata rows or an expandable utilities strip instead of stacking multiple banners and pills above the main content. Preserve existing semantics and actions. The goal is to make the interface feel more composed, not to hide important states. Run `cd apps/agent && npm run build`.
```

Success criteria:

- at most one critical banner and one secondary utility strip are visible at the same time
- runtime mode, result freshness, and recovery state are still discoverable
- primary content starts higher on the page
- the app uses fewer all-caps pills for descriptive metadata

### Slice 7: Motion and Micro-Polish Retune

Intent:

- keep motion purposeful and professional
- support state transitions without making the app feel showy

Likely files:

- `apps/agent/src/index.css`
- any touched presentational components

Exact prompt:

```text
Retune motion, shadows, and micro-interactions across the agent app so it feels like a professional copilot rather than a demo. Remove decorative zooms, loud glows, and attention-seeking shadow growth. Keep only purposeful transitions for composer focus, panel entry and exit, progress-state changes, recommendation selection, and tab or disclosure changes. Use calm easing, short durations, and strong reduced-motion fallbacks. Do not introduce novelty animation. Run `cd apps/agent && npm run build`.
```

Success criteria:

- motion clarifies state changes rather than calling attention to itself
- no flashy first-load animation remains
- panel, selection, and progress transitions feel smooth and restrained
- reduced motion meaningfully simplifies nonessential animation

## Validation Matrix

For each implemented slice:

- `cd apps/agent && npm run build`
- manual QA at desktop width for:
  - fresh empty state
  - hardware edit
  - structure edit
  - clarification flow
  - live discovery
  - rerun from an existing report
  - cached result
  - demo-safe result
  - degraded or failed runtime
- manual QA at mobile or narrow width for composer layout and report hierarchy

## Recommended Delivery Strategy

Best low-risk path:

1. do slice 0 first
2. ship slices 1 and 2 together
3. ship slices 3 and 4 together
4. ship slices 5 and 6 together
5. finish with slice 7

Why this order:

- the first pair improves the empty-state and composition experience immediately
- the second pair improves the live copilot feel
- the third pair makes the report more professional and legible
- the last pass prevents motion and polish from fighting the new hierarchy

## Risks and Rollback Strategy

- Risk: the UI becomes too quiet and hides scientific detail advanced users still need.
- Risk: a more conversational clarification flow starts to feel like generic AI chat.
- Risk: report cleanup accidentally removes important trust cues.
- Risk: motion cleanup lands before hierarchy cleanup and produces shallow polish.

Rollback strategy:

- preserve current data density behind disclosure rather than deleting it outright
- keep clarification logic and backend behavior unchanged so only the surface can be reverted
- land report hierarchy changes before heavy polish
- ship each slice behind isolated components so reversal is surgical

## Decision Notes

- 2026-04-21: The app already has the right core workflow; the opportunity is presentation, composure, and state handling.
- 2026-04-21: "More professional like Codex or Claude" should be interpreted as calmer hierarchy, clearer state continuity, and restrained motion, not as a direct visual clone.
- 2026-04-21: The hardware overlay is the clearest tonal mismatch in the current UI and should be treated as a high-priority refinement.

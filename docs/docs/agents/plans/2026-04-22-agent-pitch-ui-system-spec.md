---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent pitch UI design system workflow presentation
source_of_truth: docs/agents/execution-plans.md
---

# Agent Pitch UI System Spec

## Goal and Success Criteria

Define the UI system for the investor/demo build so the app communicates credibility, recommendation quality, and trust traceability within seconds.

Success means:

- the main report is readable without narration
- the top candidate, why-it-fits story, and trust posture are immediately legible
- fallback and degraded states still feel intentional
- the UI stays aligned with `CODEX_DESIGN_CONTEXT.md`: calm, credible, sparse, and precise

## Scope

- information hierarchy for the main report
- Trust Rail and comparison surfaces
- tooltip and microcopy rules
- loading, empty, degraded, and error states
- calm vs cinematic motion guidance for the pitch build

## Explicit Non-Goals

- no new visual brand direction
- no generic AI-dashboard styling
- no attempt to turn the UI into an investor deck inside the app

## Current State

The current app already has:

- strong recommendation cards
- evidence and diagnostics disclosures
- trust and validation posture labels
- comparison and method-summary content

The missing piece is not raw capability. The missing piece is hierarchy and framing:

- what matters most is still distributed across multiple sections
- the app needs one stronger “trustworthy copilot” visual system for the pitch

## Decision-Complete Implementation Approach

### UI stance

The app should feel like professional scientific software with editorial restraint.

The pitch should be won through:

- clarity
- confidence
- explicit evidence
- strong hierarchy

Not through:

- novelty styling
- ornamental complexity
- showy motion

### Main report information hierarchy

The report should be organized into three primary zones:

#### Zone 1: Recommendation

Always visible at first glance.

Contents:

- top recommendation title
- total fit
- runtime and core method summary
- concise why-it-won summary
- primary actions:
  - export
  - send to review
  - rerun

#### Zone 2: Why It Fits

Visible without deep expansion.

Contents:

- system match
- analyte match
- matrix fit
- practical fit
- comparison against runner-up
- scaling/adjustment summary

#### Zone 3: Trust And Evidence

Always visibly anchored, even if details are collapsible.

Contents:

- trust state
- validation posture
- review posture
- evidence snippet preview
- source metadata
- result origin: live, cached, demo-safe, or degraded

### Trust Rail

Introduce a persistent Trust Rail as the signature UI element.

Purpose:

- make the recommendation decision path visually obvious

Required steps:

1. source origin
2. extraction status
3. validation/review status
4. scaling/system-fit status
5. recommendation outcome
6. corpus reuse status when applicable

Behavior:

- compact at top-level
- expandable for more detail
- color and tone remain restrained
- avoid decorative diagrams; keep it readable and factual

### Comparison surface

Add one compact “Top fit vs next best” surface near the primary recommendation.

Required fields:

- total fit
- runtime
- trust/review posture
- strongest differentiator

Purpose:

- help investors and judges understand that the system is ranking among alternatives, not hallucinating a single answer

### Evidence preview rules

At least one evidence preview should be visible without opening a deep disclosure.

The user should see:

- one short supporting snippet
- section/page metadata if available
- one source identifier such as DOI, title, or URL

The full evidence panel can remain expandable.

### Tooltip rules

Tooltips should exist only where terminology is domain-heavy or easy to misread.

Use tooltips for:

- trust state labels
- validation posture
- review posture
- ranking mode
- degraded/live/cached/demo-safe result origin

Do not use tooltips to explain obvious UI elements.

Tooltip tone:

- short
- factual
- non-marketing

### Copy tone

Copy should feel:

- credible
- sparse
- exact

Avoid:

- hype language
- vague AI wording
- anthropomorphic assistant copy

Prefer:

- “Reviewed record”
- “Needs operator review”
- “Cached result”
- “Live degraded result”

### Loading and progress states

Loading should communicate forward motion without drama.

Required rules:

- show current stage
- show what the system is doing in plain language
- keep prior successful results visible if applicable
- do not blank the screen during reruns

### Empty states

Empty states should teach the interface.

Required cases:

- no prior runs
- no evidence snippets
- no review summary
- empty review queue

Each empty state should answer:

- what is missing
- why it is missing
- what the user can do next

### Error and degraded states

Errors must not collapse the product narrative.

Required behavior:

- show whether the failure is service, search, fetch, extraction, or timeout related
- preserve any prior valid result where possible
- offer one recovery action
- if cached/demo-safe alternatives exist, present them inline

### Calm vs cinematic motion

Calm by default:

- transitions between stages
- panel open/close
- result refresh

Cinematic only in controlled moments:

- initial report reveal
- Trust Rail activation
- top-candidate transition on first completed run

Rules:

- motion supports comprehension
- no decorative flourish on every interaction
- respect reduced-motion preferences

## Interfaces / Contracts / Types Affected

Potential frontend additions:

- `AgentResultOrigin`
- `TrustRailStep`
- comparison-summary view model
- tooltip copy map for trust and runtime labels

No backend contract changes are required to start the UI work, but the UI assumes:

- stable trust and review fields
- explicit runtime summaries
- source-document metadata

## Validation Matrix

When implemented:

- `cd apps/agent && npm run build`
- visual review in desktop and web shells
- scripted acceptance run covering:
  - first-load comprehension
  - live degraded run
  - cached result inspection
  - send-to-review handoff

## Risks and Rollback

- Risk: UI work becomes too decorative and harms credibility.
- Risk: too many visible diagnostics drown the core recommendation story.
- Risk: fallback labels make the interface feel broken instead of trustworthy.

Rollback:

- keep the top-level layout fixed around Recommendation, Why It Fits, and Trust/Evidence
- push secondary details back behind disclosures

## Decision Notes

- 2026-04-21: The Trust Rail is the signature UI element for the pitch build.
- 2026-04-21: The UI must stay calm and credible even when demo-optimized.

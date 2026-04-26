---
status: draft
owner: codex
created: 2026-04-23
last_verified: 2026-04-23
last_updated: 2026-04-23
applies_to: apps/agent component system motion typewriter shadcn
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-25-agent-chat-first-plan-set.md
  - ./2026-04-25-agent-conversational-run-loop-spec.md
---

# Agent Presentation, Motion, and Component System Spec

## Goal and Success Criteria

Define the UI-system and motion rules for the chat-first agent so implementation stays fast, reusable, and visually premium without collapsing into custom one-off component work.

Success means:

- the implementation reuses the existing shadcn/Radix setup already present in `apps/agent`
- missing primitives are added intentionally through CLI rather than hand-built from scratch
- the app gains cinematic motion in a few high-value moments
- evidence and trust surfaces remain calmer and more sober than the pitch surfaces
- the typewriter effect feels controlled and product-grade instead of gimmicky

## Scope

- `apps/agent/components.json`
- `apps/agent/src/index.css`
- shared UI primitives used by the new chat-first surfaces
- motion dependency decisions
- typewriter implementation strategy

## Explicit Non-Goals

- no third primitive system alongside existing app UI and studio UI layers
- no dependency sprawl for one-off animation effects
- no decorative motion on every surface
- no third-party typewriter package

## Current State

`apps/agent` already has:

- a shadcn-compatible `components.json`
- existing Radix dependencies
- a current canonical primitive path at `@/studio/components/ui`
- custom app-level UI components under `apps/agent/src/components/ui`
- existing CSS animation tokens in `apps/agent/src/index.css`

What is missing is a documented rule set for when to reuse, when to add components, and where motion should actually live.

## Decision-Complete Implementation Approach

### Resource Strategy

Implementation must prefer:

1. existing shadcn/Radix primitives
2. new shadcn components added through CLI
3. small app-local wrappers around those primitives

Implementation must avoid:

- bespoke overlays when `Dialog`, `Sheet`, or `Drawer` already solve the problem
- custom tabs, popovers, toggle groups, and scroll areas when the ecosystem already provides them
- a third UI source tree for the new experience

`@/studio/components/ui` remains the current canonical primitive source for this app in v1 unless a separate future refactor intentionally consolidates it.

### Required Component Workflow

Before adding a missing primitive:

1. inspect already installed components
2. run `npx shadcn@latest docs <component>`
3. add only the missing component needed for the flow
4. verify imports and composition after adding it

Do not hand-roll primitives first and “maybe refactor later.”

### Component Additions To Evaluate First

The first pass should evaluate and add these components if missing:

- `sheet`
- `popover`
- `hover-card`
- `scroll-area`
- `skeleton`
- `toggle-group`
- `tabs`
- `sonner`
- `drawer` only if mobile fallback proves necessary

These are enough to cover modal editing, plan-summary disclosure, animated loading states, transcript polish, and popup detail flows without a bespoke component spree.

### Motion Dependency Strategy

Install `framer-motion` as the primary motion dependency.

Use it for:

- composer-to-recognition transitions
- staggered transcript turn reveals
- implementation-plan reveal
- result-card entrance choreography
- popup deep-view enter and exit

Do not add separate libraries for each animation niche.

### Typewriter Strategy

Do not install a third-party typewriter package.

Implement the typewriter effect as a small app-local transcript utility so it can support:

- interruption when the next state arrives early
- finish-on-click or finish-on-interaction
- reduced-motion fallback
- deterministic completion for tests
- future streaming compatibility

The typewriter effect should apply to short agent text moments only, not every paragraph in the app.

### Motion Distribution

High-motion surfaces:

- first recognized analyte moment
- agent typing turn
- implementation-plan reveal
- run-start transition
- result reveal
- popup opening

Calm surfaces:

- evidence detail
- trust panels
- provenance
- warnings
- hardware forms

The app must feel premium at the edges and credible at rest.

### Visual Direction

The chat-first agent should feel:

- premium
- editorial
- scientific
- cinematic in transitions
- restrained in resting state

Avoid:

- dashboard-card mosaics
- generic chatbot bubbles
- noisy glassmorphism
- neon “AI app” tropes
- motion that competes with evidence reading

## Validation Matrix

Docs and dependency decisions:

- `npm run agent:harness:check`

Implementation minimum:

- `cd apps/agent && npm run build`

Required QA scenarios:

- transcript turns animate correctly with reduced-motion fallback
- typewriter text can complete deterministically and be skipped cleanly
- high-motion moments are limited to defined surfaces
- trust and evidence views remain readable without theatrical motion
- newly added shadcn components use documented composition patterns

## Risks and Rollback Strategy

- Risk: engineers bypass the component workflow and build custom UI too quickly.
- Risk: motion spreads beyond the intended moments and makes the app feel unserious.
- Risk: typewriter behavior becomes flaky or blocks interactions.

Mitigations:

- enforce CLI-first component additions
- define motion zones explicitly
- implement the typewriter effect locally with deterministic controls and reduced-motion support

Rollback path:

- if typewriter behavior proves unstable, fall back to instant text rendering while preserving the rest of the motion system
- if `framer-motion` becomes too invasive, retain only the high-value transitions and revert the rest to CSS-based reveals

## Decision Notes

- 2026-04-23: the app should be smart about reuse and dependency choice rather than rebuilding primitives manually
- 2026-04-23: `framer-motion` is the one approved motion dependency for this wave
- 2026-04-23: the typewriter effect is app-local by design because transcript control requirements exceed what a generic package should own

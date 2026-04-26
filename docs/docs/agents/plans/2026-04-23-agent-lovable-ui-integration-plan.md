---
status: draft
owner: codex
created: 2026-04-21
last_verified: 2026-04-21
last_updated: 2026-04-21
applies_to: apps/agent apps/marketing apps/api auth UI integration planning
source_of_truth: docs/agents/execution-plans.md
related_docs:
  - ./2026-04-22-agent-clean-ui-redesign-plan.md
---

# Agent Lovable UI Integration Plan

## Goal and Success Criteria

Integrate the interface and interaction quality of `Niclindm/liquid-smart-agent` into Silico's real agent product without importing the wrong product model, state model, or backend assumptions.

Success means:

- the public website can route authenticated users into a production-ready `/agent` experience
- the agent app adopts the stronger shell, navigation, and workflow framing from the Lovable UI
- the Silico-specific HPLC recommendation workflow remains the source of truth for system setup, target setup, source selection, live discovery, trust, and report review
- the app preserves Lovable-style conversational interaction, including asking questions and filling workflow fields from chat
- authentication, session ownership, and user persistence are introduced intentionally rather than copied from the Lovable repo's Supabase defaults
- `apps/marketing`, `apps/agent`, and `apps/api` keep clear ownership boundaries

## Scope

- `apps/agent` shell, routing, authenticated entry, and workflow presentation
- `apps/agent` conversational copilot behaviors for question answering, draft assistance, and controlled field updates
- `apps/marketing` website entry points and handoff into authenticated agent access
- `apps/api` support for identity-adjacent and account/session bootstrap APIs if needed
- shared visual tokens and shell primitives only where neutral reuse makes sense

## Explicit Non-Goals

- no direct port of the Lovable repo's Supabase schema, edge functions, or local-only workspace store
- no rewrite of `services/method-development` recommendation contracts to fit the borrowed UI
- no collapse of `apps/marketing` and `apps/agent` into one app boundary
- no introduction of fake IDE concepts like local project trees or versioned methods unless mapped to real Silico objects

## Current State

### Silico repo today

The current repo already has the right product boundary split:

- `apps/marketing` is the public website and already proxies `/agent` to the agent app in development
- `apps/agent` is the real retrieval-and-scoring client and already owns runtime boot, workflow state, degraded handling, recent-run recovery, and report presentation
- `apps/api` exists as the hosted public backend and is the natural place for website-facing auth/session bootstrap work if Silico keeps the current architecture
- `services/method-development` is already the domain backend for recommendation, clarification, extraction, and trust payloads

Important current implementation facts:

- `apps/agent/src/App.tsx` is still a lightweight path switcher rather than a routed app shell
- `apps/agent/src/pages/Dashboard.tsx` and `apps/agent/src/components/dashboard/DashboardView.tsx` carry most of the UX in a single workflow surface
- `apps/agent/src/hooks/useAgentWorkflow.ts` is the real product state model and already includes explicit degraded, cached, demo-safe, stale, and clarification states
- `apps/marketing` already has a showcase-to-agent handoff shape and does not need to be rethought from zero

### External Lovable repo today

The referenced repo contributes strong UI ideas, but it is not aligned to Silico's current product architecture:

- it uses a protected app shell with `/auth` and `/`
- it uses Supabase directly in the frontend for auth and edge-function chat calls
- it stores the workspace locally in Zustand persistence
- its core domain model is "project -> method versions -> predicted chromatograms", not "run discovery against real recommendation services"
- its shell is the most reusable part: top bar, left navigation, center workbench, right copilot, command palette, account menu, and hardware panel framing

## What To Reuse vs Reject

### Reuse directly in spirit

- authenticated shell pattern
- top navigation and account affordances
- left rail for recent work and context switching
- right rail for copilot / conversational guidance
- question-first interaction where the user can describe the task in natural language
- agent-assisted field population and workflow drafting from chat input
- editorial scientific-software visual language
- clearer separation between "compose", "work", and "review" modes
- keyboard-first affordances such as command palette and panel toggles

### Rebuild for Silico instead of porting

- auth implementation
- route protection
- workspace state model
- "project" and "method version" semantics
- tool-calling chat architecture, mapped to Silico workflow fields and actions
- hardware and solvent storage
- persistence model for user work

### Reject entirely

- direct Supabase dependency as the default architectural choice unless Silico explicitly decides on it
- local-only persisted project state as the system of record
- edge-function chat loop as the primary workflow engine
- any UI section that hides or downgrades current trust, validation, degraded-runtime, or provenance states

## Decision-Complete Implementation Approach

### Product stance

Silico should treat the Lovable repo as a UI reference implementation, not as an application base.

The implementation should preserve this repo's current product boundary model:

- `apps/marketing` remains the public site
- `apps/agent` remains the authenticated app experience under `/agent`
- `apps/api` becomes the account/session boundary if new web auth is added
- `services/method-development` remains a recommendation backend, not an auth or workspace backend

### Recommended integration strategy

Adopt the Lovable shell and interaction framing around Silico's existing workflow, rather than forcing Silico's workflow into the Lovable data model.

That means:

1. keep the current Silico workflow engine and HTTP contracts
2. introduce routing and auth gate into `apps/agent`
3. extract a new shell made of:
   - authenticated app layout
   - left context rail
   - center workflow workspace
   - right copilot / guide rail
4. add a controlled action layer so the copilot can answer questions, propose changes, and fill fields in the real Silico workflow
5. recompose the current `DashboardView` content into that shell in phases

## Target Product Architecture

### Website layer

`apps/marketing` should stay the acquisition surface.

New responsibilities:

- show clear "Sign in" and "Open agent" entry points
- route qualified users to `/agent`
- preserve showcase/demo flows for anonymous visitors
- hand off marketing context to the agent after login when relevant

### Agent layer

`apps/agent` should become a routed authenticated app, not just a standalone single-page workflow.

Recommended route model:

- `/agent/auth`
- `/agent`
- `/agent/review`
- future-safe:
  - `/agent/runs/:id`
  - `/agent/settings`

Recommended layout model:

- top app bar: brand, workspace title, search/command trigger, account menu
- left rail: recent runs, saved work, source mode shortcuts, review queue entry, settings link
- center workspace: current Silico workflow and report surfaces
- right rail: copilot guidance, clarifications, suggestions, provenance-aware assistant summaries

Recommended interaction model:

- the user can either fill forms directly or start by asking the agent in natural language
- the agent can answer workflow questions such as what a field means, what to enter next, or why a value matters
- the agent can populate draft values for system specs, target details, source selection, and rerun intent
- high-impact actions such as running discovery, rerunning, retrying live mode, or resetting state remain explicit user actions unless deliberately confirmed

### Backend layer

`apps/api` should own any new user/account concerns.

Recommended responsibilities:

- sign-in/session bootstrap endpoints or auth callback integration
- authenticated user profile payload
- user-scoped recent runs / saved sessions metadata if persistence moves server-side
- website-to-agent redirect/session handoff
- copilot action endpoint or orchestration endpoint if chat-assisted field filling is server-mediated

Not recommended:

- placing auth inside `services/method-development`
- placing durable user data only in browser local storage

## Authentication Plan

### Recommendation

Do not start by copying the Lovable repo's Supabase frontend auth directly.

Instead, make an explicit auth decision first:

- Option A: Supabase Auth for speed
- Option B: first-party auth behind `apps/api`
- Option C: external identity provider integrated through `apps/api`

Recommended default for this repo:

- use `apps/api` as the application boundary
- allow the auth provider behind it to remain replaceable
- keep the frontend dependent on "session exists / user profile exists" contracts, not provider-specific SDK assumptions

### Why this recommendation

- it matches repo boundaries better
- it avoids leaking auth concerns into `services/method-development`
- it keeps the website and agent app on one product identity model
- it avoids hard-wiring the product to the current Lovable stack before requirements are decided

### Minimum auth feature set for phase one

- sign in
- sign up or invite flow
- sign out
- session restore on refresh
- protected agent routes
- post-login redirect back to intended `/agent` destination
- clear anonymous behavior on the marketing site

### Copilot minimum feature set for phase one

- ask free-form questions about the workflow and receive grounded answers
- ask the agent to populate fields from natural-language input
- show exactly which fields the agent changed
- preserve a visible distinction between suggested values and user-confirmed execution actions
- support current clarification questions in the same right-rail interaction model

### Phase-two auth/account features

- password reset
- email verification if required
- account settings
- workspace ownership and auditability
- role distinction if operator/reviewer tools remain separate from normal users

## Workflow Mapping

### Lovable concept -> Silico target mapping

- Lovable `Auth` page -> Silico `AgentAuthPage`
- Lovable `AppShell` -> Silico authenticated shell
- Lovable `ProjectsPanel` -> Silico `RunsAndWorkspacePanel`
- Lovable `Workbench` -> Silico workflow/report workspace
- Lovable `CopilotPanel` -> Silico clarifications/copilot/recommendation guide rail
- Lovable `HardwarePanel` -> Silico system setup and lab inventory panel
- Lovable command palette -> Silico quick actions for recent runs, review queue, source switching, and settings

### Conversational workflow mapping

- "design a method for caffeine in coffee" -> populate target, matrix, and likely request text fields in Silico draft state
- "fill in my system based on this instrument" -> map chat output into `systemSpecs`
- "what should I enter here?" -> answer against real field definitions and current backend expectations
- backend clarification questions -> render inside the copilot rail and allow answers to update workflow state directly
- "run this" -> translate to a visible ready-to-run draft, with explicit confirmation for the actual discovery action

### Important semantic changes

Silico should not mimic the external repo's "project + method version" IA one-for-one.

The center workspace should instead be built around real Silico objects:

- draft run inputs
- live recommendation job state
- completed report
- recent report snapshots
- review queue

If future persistence introduces saved workspaces, name them after actual Silico concepts such as:

- "sessions"
- "runs"
- "workspaces"
- "reports"

Do not introduce "method v3" or IDE-style branching unless the product truly supports that concept.

## Copilot Action Model

### Principle

Keep the Lovable interaction feel, but bind it to Silico's existing workflow model instead of a fake local IDE workspace.

The copilot should support three classes of actions:

1. explain
2. draft
3. apply

### Explain

Examples:

- what does source mode mean
- should I use open access or local corpus
- why is max runtime important

Behavior:

- no state mutation
- answer using current field definitions, runtime context, and report state

### Draft

Examples:

- fill out the target section from this description
- draft my system setup from this instrument list
- add likely impurities based on this analyte and matrix

Behavior:

- produce structured proposed field updates
- show pending changes in UI before they are applied, or mark them as freshly applied in an inspectable activity log

### Apply

Examples:

- update `requestText`
- set source mode to `open_access`
- add impurity rows
- answer clarification questions

Behavior:

- restricted to safe workflow mutations
- every applied change is inspectable by field and value
- no silent mutation of trust, runtime, or report data returned from the backend

### Guardrails

- no hidden field edits
- no auto-run on ambiguous intent
- no silent reset of current report or draft
- no recomputation of backend trust or ranking in the frontend
- destructive actions require explicit confirmation

## Execution Phases

### Phase 0: Architecture and auth decision

Deliverables:

- choose auth strategy and session contract
- define whether saved work is browser-only, API-backed, or hybrid
- define protected route behavior for `/agent`
- define website header/account states

Acceptance criteria:

- frontend work can proceed without unresolved auth ambiguity
- ownership between `apps/marketing`, `apps/agent`, and `apps/api` is explicit

### Phase 1: Shell extraction in `apps/agent`

Deliverables:

- add router to `apps/agent`
- add `AuthPage`, authenticated shell, and protected routes
- split current monolithic workflow screen into shell-friendly center content
- add a right-rail copilot shell even if its first version only hosts current clarifications and guided prompts
- keep current `useAgentWorkflow` and API contracts intact

Acceptance criteria:

- current discovery workflow still works inside the new shell
- the user can ask questions and see guided answers without leaving the workflow
- no loss of runtime banners, stale-result notices, clarification flows, or trust surfaces

### Phase 2: Left rail and right rail integration

Deliverables:

- left rail for recent runs, review queue, and future saved work
- right rail for copilot guidance, clarification prompts, field-filling, and result explanation
- top app bar with account entry and global navigation
- structured copilot actions that can update draft workflow fields

Acceptance criteria:

- rails add structure without duplicating current content
- current central workflow becomes more readable, not more crowded
- copilot-applied field changes are inspectable and reversible

### Phase 3: Website integration

Deliverables:

- add website CTAs for authenticated agent access
- decide anonymous vs authenticated `/agent` entry behavior
- add post-login return handling for marketing-to-agent handoff
- align visual identity between marketing and agent without making them identical

Acceptance criteria:

- marketing can send users into the real agent experience cleanly
- demo/showcase flows remain available without forcing login prematurely

### Phase 4: Persistence and account-backed work

Deliverables:

- move recent runs and saved work to a user-scoped persistence layer if required
- define server-backed run metadata model
- preserve current local snapshot recovery as fallback or offline convenience

Acceptance criteria:

- users can return to prior work across devices if that is a product requirement
- persistence behavior is inspectable and does not hide missing or stale state

### Phase 5: Copilot upgrade

Deliverables:

- replace placeholder shell-style chat with a Silico-native assistant rail
- use real clarification requests, recommendation context, recent run context, and trust/provenance payloads
- support natural-language field filling and question answering against the live workflow draft
- define an action schema for safe frontend workflow mutations
- expose assistant failure states explicitly

Acceptance criteria:

- copilot improves workflow comprehension without fabricating state changes
- chat and tool surfaces remain auditable
- users can complete most draft setup by talking to the agent, while still seeing exactly what changed

## File-Level Implementation Starting Points

### `apps/agent`

Primary starting points:

- `apps/agent/src/App.tsx`
- `apps/agent/src/pages/Dashboard.tsx`
- `apps/agent/src/components/dashboard/DashboardView.tsx`
- `apps/agent/src/hooks/useAgentWorkflow.ts`
- new shell area suggested:
  - `apps/agent/src/components/shell/*`
  - `apps/agent/src/pages/Auth.tsx`
  - `apps/agent/src/router/*` or equivalent

### `apps/marketing`

Primary starting points:

- `apps/marketing/src/components/layout/SiteHeader.tsx`
- `apps/marketing/src/pages/LandingPage.tsx`
- `apps/marketing/src/components/showcase/ShowcaseExperience.tsx`
- any CTA and redirect logic that currently points users toward the agent

### `apps/api`

Primary starting points once auth is chosen:

- `apps/api/app/main.py`
- `apps/api/app/config.py`
- new auth/session route modules
- CORS/trusted-host settings to support website + agent production origins explicitly

## Risks and Constraints

- Risk: directly porting the Lovable repo imports a misleading app model and forces Silico into local-first pseudo-IDE semantics.
- Risk: auth gets added in the frontend only, creating a second architecture that does not align with the rest of the repo.
- Risk: new shell chrome buries current runtime, trust, and degraded-state visibility.
- Risk: chat-driven field filling becomes opaque and users lose confidence in what the system changed.
- Risk: website and agent adopt inconsistent account models and redirect flows.
- Risk: saved work semantics are designed before the real persistence requirement is clear.

## Rollback Strategy

- keep shell extraction separate from auth-provider choice where possible
- land routing and shell composition before deeper persistence changes
- preserve current `useAgentWorkflow` and existing HTTP contracts until the new shell is stable
- keep current local run snapshot recovery available until account-backed persistence is proven
- ship explain-only and draft-only copilot modes before broader apply actions if mutation safety is unclear

## Validation Matrix

Planning pass:

- `npm run agent:harness:check`

Implementation pass minimum checks by phase:

- shell/auth changes in `apps/agent`: `cd apps/agent && npm run build`
- website integration changes: `cd apps/marketing && npm run build`
- auth/session API changes: `cd apps/api && uv run pytest -q`
- cross-boundary release slice: run all affected app checks together

## Recommended Build Order

1. Decide auth boundary and session contract.
2. Add routing plus protected shell in `apps/agent`.
3. Port the Lovable layout primitives, not the Lovable app state.
4. Introduce a safe copilot action schema for question answering and field filling.
5. Move Silico workflow panels into the new center workspace.
6. Add website account CTAs and login handoff.
7. Add server-backed persistence only after the shell and auth are stable.
8. Upgrade the right rail into a real Silico copilot surface.

## Decision Notes

- 2026-04-21: the referenced Lovable repo is valuable primarily as a shell and workflow-presentation reference, not as a direct technical base.
- 2026-04-21: `apps/marketing` already proxies `/agent` in development, so the repo is structurally ready for a tighter website-to-agent integration.
- 2026-04-21: the safest path is to wrap the current Silico workflow in the new shell rather than rewriting the workflow to match the external repo's data model.
- 2026-04-21: conversational field filling and question-first interaction are now explicit retained features from the Lovable reference and should be designed as controlled workflow mutations, not opaque chat magic.

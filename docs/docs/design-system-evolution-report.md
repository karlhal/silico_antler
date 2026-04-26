# Design System Evolution Report (April 2026)

## Overview
In April 2026, the Silico design system underwent a significant evolution from a warm, traditional "Silico" aesthetic to a refined, editorial, and chat-bot-inspired direction known as **"The Digital Curator / Premium Edition"**. This transformation was driven by the creation of a new standalone "Agent" application designed to test high-stakes, pre-lab decision-making for analytical chemists.

## Key Changes

### 1. Architectural Expansion
- **New Workspace**: Created `apps/agent`, a standalone React + Vite + Tailwind v4 application.
- **Unified Brand Package**: Refactored `packages/brand/silico-theme.css` to become the single source of truth for the new "Premium" design tokens, shared across the Agent app and the marketing site.

### 2. Aesthetic Redefinition ("Digital Curator" Style via "Impeccable" Guidelines)
- **Typography**: 
  - **Display**: `Newsreader` (Serif) – used for headings and italicized emphasis to provide an editorial, high-end feel.
  - **Body**: `Work Sans` (Sans-serif) – used for all labels, data inputs, and technical content for modern legibility. We enforce fluid typography scaling to ensure structural rhythm.
- **Palette**: Shifted to a light-first, high-contrast palette. 
  - **Base**: Tinted off-white (e.g. `oklch(98.5% 0.002 345)`) that pulls towards the primary hue. We explicitly ban pure white (`oklch(100% 0 0)`) and pure black across the application.
  - **Primary**: Sharp Cobalt Blue (`#0041c8`).
- **Geometry & Structure**: Implemented `12px` (`rounded-2xl`) corners. However, following anti-patterns against "AI slop", we have completely abandoned all drop shadows (diffuse or otherwise), glassmorphism, and nested card grids. We rely entirely on asymmetrical framing, robust typography, and sharp, high-contrast structural borders to establish component hierarchy.

### 3. Functional Workflow Innovation
- **Staged Interaction**: The Agent app introduces a "Staged Stage" UI. Instead of a scrolling list, content enters and exits the screen via vertical slide/fade transitions, guiding the user through a 5-step protocol:
  1. **System Context**: Hardware/Solvent constraints.
  2. **Separation Target**: Chemistry/Analyte goals.
  3. **Source Selection**: Evidence repository choices.
  4. **Discovery Log**: Live Agent inference visualization.
  5. **Evidence**: Physics-scaled method recommendations.
- **Professional Flexibility**: Added "Other..." logic to all dropdowns (Manufacturer, Chemistry, Matrix) to support custom professional inputs like "YMC" or "C30".
- **One-Click Demo**: Integrated a "Use demo test case" feature to instantly populate the research pipeline for rapid testing.

### 4. Technical Normalization
- **Tailwind v4 Implementation**: Fully utilized Tailwind v4's CSS-first `@theme` configuration.
- **API Integration**: Established a robust client in `apps/agent/src/lib/api.ts` capable of multi-port communication (8000 for identity resolution, 8001 for method-dev retrieval).
- **Physics-Based Scaling**: Implemented specific UI components to display how literature methods are automatically scaled for the user's specific column dimensions.

## April 2026 Update: Cinematic Workflow & Hardware Physics
Building upon the "Digital Curator" baseline, the Agent UI architecture experienced a secondary layout refactor moving away from paginated views towards a highly kinetic, cinematic experience modeled after hardware precision limits.

### 1. Absolute Deck Architecture
- The configuration steps (System Context, Target, Source) were un-nested from structural document flow and converted into an absolute-positioned cinematic "Deck".
- Navigation is controlled by a custom `WheelEvent` Delta Accumulator (requiring fixed momentum to shift views) ensuring transitions feel deliberate.
- Upon finalizing inputs, the entire Deck shrinks `scale: 0.8` and translates upward across `1200ms`, locking into a historical state.

### 2. Timeline Bridge & Historical Navigation
- To prevent users from feeling disconnected from their inputs, a structural vertical timeline bridge traces downward from the locked settings deck to the Agent's "Live Trace" visualization.
- **Tab-Navigator**: When deep in Phase 4 (Analysis), a mini tab-header generates above the locked deck, allowing users to rapidly click through their old context inputs entirely horizontally without affecting the document layout or the vertical scroll.
- The UI features an auto-scroll engine binding to `phaseIndex >= 3` utilizing a `300ms` delayed scroll hook to drag the live inferences into natural focal territory automatically.

### 3. Impeccable Accordion Engineering (Zero DOM Unmount)
- Replaced jumpy, React-conditionally-mounted components with a hardware-accelerated "Accordion." 
- We completely circumvent DOM instantiation jiggle by relying on `grid-template-rows: 0fr -> 1fr` coupled with `overflow-hidden`. 
- The inactive and active headers utilize strict overlapping absolute positioning and `opacity` cross-fading, preventing CSS margin-collapses and allowing the text underneath to be natively revealed by the expanding card exactly like a window blind physically dropping downwards.

## Implementation Files
- **Mandate**: `GEMINI.md`
- **Brand Tokens**: `packages/brand/silico-theme.css`
- **Agent App**: `apps/agent/`
- **Marketing Normalization**: `apps/marketing/src/tailwind.css`
- **Workflow Logic**: `apps/agent/src/hooks/useAgentWorkflow.ts`

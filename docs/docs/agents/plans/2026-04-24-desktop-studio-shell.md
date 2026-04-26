---
status: active
owner: codex
created: 2026-04-22
last_verified: 2026-04-22
applies_to: apps/desktop
source_of_truth: docs/agents/execution-plans.md
---

# Desktop Studio Shell Migration

## Goal And Success Criteria
- Rebuild the `apps/desktop` shell so it matches the shipped agent studio visual language while preserving the desktop workflow model.
- Keep the existing screen model (`start`, `session`, `details`, `settings`) and existing sidecar/runtime contracts intact.
- Ship desktop-local light and dark themes with persisted appearance state.
- Leave the desktop app in a passing state for `npm run test` and `npm run build`.

## Scope
- Desktop-only shell, theme, and presentation changes in `apps/desktop`.
- Desktop-local theme tokens and desktop-local shell/interaction utilities.
- Desktop tests covering theme persistence, shell navigation, rail toggles, and setup/runtime banners.

## Non-Goals
- No backend, Tauri command, or API contract changes.
- No reuse of the agent studio Tailwind/Radix component layer.
- No introduction of Apriori naming, auth flow, or report workflow into desktop.
- No changes to shared brand packages unless the desktop app must stop importing them directly.

## Decision-Complete Approach
- Add a desktop-local studio theme stylesheet and import it from `apps/desktop/src/main.tsx` before desktop app styles.
- Add desktop-local hooks/utilities for persisted theme state and resizable rail widths.
- Replace the current `DesktopShell` structure in `apps/desktop/src/App.tsx` with a three-pane shell:
  - left rail for branded sessions/history
  - center workbench for the active desktop screen
  - right rail for contextual screen-specific controls and supporting content
- Move screen switching into studio-style workspace chips in the main workbench header.
- Add a desktop command palette with `Cmd/Ctrl+K` for:
  - screen navigation
  - left/right rail toggles
  - recent-run restore
- Refactor each desktop screen to separate main content from right-rail content:
  - `start`: main editor in the center, structure preview and launch summary in the right rail
  - `session`: charts in the center, controls/metrics/peaks in the right rail
  - `details`: briefing in the center, peak selection and selected-peak metadata in the right rail
  - `settings`: runtime actions in the center, appearance/provider/runtime summary in the right rail
- Replace hardcoded chart, heatmap, molecule-preview, and status colors with desktop CSS variables so light/dark themes apply consistently.
- Keep drag/non-drag regions explicit in the new header so Tauri behavior remains correct.

## Validation Matrix
- `cd apps/desktop && npm run test`
- `cd apps/desktop && npm run build`
- Verify theme persistence and `document.documentElement.dark` behavior in tests.
- Verify rail toggle and screen navigation behavior in tests.
- Verify setup/runtime banners remain visible and actionable after the shell migration.

## Risks And Rollback
- Main risk: large CSS and composition changes could break dense screen layouts or Tauri drag behavior.
- Main mitigation: keep workflow state and view logic stable while changing shell composition and styling around them.
- Rollback path: revert the desktop-local shell/theme layer and restore the prior `App.tsx` shell composition if the migration destabilizes desktop workflow behavior.

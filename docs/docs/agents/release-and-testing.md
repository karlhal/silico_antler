---
owner: platform
last_verified: 2026-04-22
applies_to: agent-api-desktop-marketing-sidecar-method-development
source_of_truth: .github/workflows/desktop-release.yml
---

# Release And Testing

## Agent App Validation
- Current app-level gate: `cd apps/agent && npm run build`
- There is no dedicated agent-app release workflow in-repo yet; document the current build-only validation path instead of inventing one.
- If app changes alter `/method-dev` or `/api` contract assumptions, run the relevant backend tests in addition to the app build.

## Desktop Release Flow
- Canonical workflow: [`../../.github/workflows/desktop-release.yml`](../../.github/workflows/desktop-release.yml)
- Release notes template: [`../../.github/workflows/desktop-release-notes.md`](../../.github/workflows/desktop-release-notes.md)
- Pre-release metadata validation: `npm run release:verify --workspace silico-desktop`

## Hosted Deployment References
- Render + Cloudflare launch notes: [`../render-cloudflare-launch.md`](../render-cloudflare-launch.md)
- Root deployment summary: [`../../README.md`](../../README.md)

## Testing Expectations
- Run app-level or service-level tests/builds for touched surfaces (see [`./quality-gates.md`](./quality-gates.md)).
- Preserve deterministic demo behavior and avoid accidental model coupling.
- If changing release-sensitive desktop paths, run release verification and relevant packaging checks.

## Non-Blocking Harness CI
- `agent-harness-check.yml` reports issues but does not fail merges in v1.
- Use report artifacts to drive doc-gardening follow-up PRs.

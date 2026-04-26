---
owner: platform
last_verified: 2026-04-22
applies_to: all-apps
source_of_truth: README.md
---

# Quality Gates

Run the smallest check set that fully covers your touched surfaces.

## Baseline Harness Check
- Instruction/docs updates: `npm run agent:harness:check`

## App-Specific Checks
- Agent app: `cd apps/agent && npm run build`
- API: `cd apps/api && uv run pytest -q`
- Sidecar: `cd apps/sidecar && uv run pytest -q`
- Method development service: `cd services/method-development && uv run pytest -q`
- Desktop: `cd apps/desktop && npm run test`
- Marketing: `cd apps/marketing && npm run build`

## Minimum Validation Matrix
- Agent app UI/workflow changes: agent build + affected backend tests if app-to-service contracts changed.
- Python API-only changes: API tests + harness check (if docs/instructions changed).
- Method-development-only changes: method development service tests + harness check (if docs/instructions changed).
- Sidecar-only changes: sidecar tests + affected desktop smoke checks if contract touched.
- Desktop UI/runtime changes: desktop tests + release metadata verify when packaging is affected.
- Marketing changes: marketing build/type-check.
- Cross-app contract changes: run checks in each affected app boundary.

## CI Note
`agent-harness-check` is non-blocking in v1 and emits a report artifact.

## Related Docs
- Release/testing: [`./release-and-testing.md`](./release-and-testing.md)
- Security constraints: [`./security-constraints.md`](./security-constraints.md)

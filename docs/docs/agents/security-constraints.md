---
owner: platform
last_verified: 2026-04-18
applies_to: all-apps
source_of_truth: on_prem_security_baseline.md
---

# Security Constraints

## Secrets And Sensitive Data
- Never commit secrets, tokens, private keys, or populated `.env` values.
- Keep model weights and private runtime assets out of source control.
- Treat contact payloads and analytics data as sensitive operational data.

## Network And Origin Constraints
- Keep API CORS allowlists explicit and minimal.
- Keep API trusted hosts explicit (`TRUSTED_HOSTS`).
- Keep sidecar origins local-first and explicit (`SIDECAR_ALLOWED_ORIGINS`).
- Keep sidecar trusted hosts explicit (`SIDECAR_TRUSTED_HOSTS`).

## Runtime Safety
- Preserve secure defaults unless there is an explicit requirement to widen access.
- Document every security-relevant behavior change in repo docs.
- Prefer reversible, scoped changes over broad permissive flags.

## Sensitive Asset Boundary
- `apps/sidecar/legacy_runtime/builtin_ensemble_a40/` is intentionally external/private.
- Desktop bundling can include sidecar runtime code, not private model assets.

## Related Docs
- Security baseline: [`../../on_prem_security_baseline.md`](../../on_prem_security_baseline.md)
- Security report: [`../../security_best_practices_report.md`](../../security_best_practices_report.md)
- Sidecar README: [`../../apps/sidecar/README.md`](../../apps/sidecar/README.md)

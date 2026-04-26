---
owner: codex
last_verified: 2026-04-18
applies_to: apps/agent services/method-development operator review queue
source_of_truth: docs/agents/execution-plans.md
---

# Review Queue Security & Operational Risks

Identified during the implementation of the `/review` operator surface on 2026-04-22.

### 1. Authentication & Access Control (Security)
- **Risk:** The `/review` route in `apps/agent` is currently accessible via the URL without explicit operator-role authentication. 
- **Impact:** Any user with the application URL can access operator-level moderation and corpus promotion controls.
- **Required Fix:** Implement an auth guard (e.g., JWT role check or a `VITE_ENABLE_OPERATOR_CONTROLS` environment flag) to restrict access to authorized personnel before production deployment.

### 2. Promotion Friction & Corpus Integrity (Operational)
- **Risk:** The "Approve & Promote" button is highly accessible and performs both actions in one click without a confirmation step.
- **Impact:** High risk of accidental or low-quality method promotion into the local corpus, which degrades recommendation quality for other users.
- **Required Fix:** 
  - Add a confirmation modal for promotion actions.
  - Require a brief "Promotion Reason" text field to ensure intentionality and auditability.
  - Consider separating "Approval" and "Promotion" as two distinct user actions to increase friction for corpus modification.

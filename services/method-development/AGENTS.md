# Method Development Service Agent Guide

## Scope
Applies to `services/method-development` only. Use with the root `../../AGENTS.md`.

## Primary Commands
- Install/update deps: `uv sync --group dev`
- Run tests: `uv run pytest -q`
- Run service: `uv run fastapi dev app/main.py`

## Must-Read Context
- Agent docs index: [`../../docs/agents/index.md`](../../docs/agents/index.md)
- Security constraints: [`../../docs/agents/security-constraints.md`](../../docs/agents/security-constraints.md)
- Quality gates: [`../../docs/agents/quality-gates.md`](../../docs/agents/quality-gates.md)
- App README: [`./README.md`](./README.md)
- Package README: [`./app/README.md`](./app/README.md)
- Tests README: [`./tests/README.md`](./tests/README.md)

## Local Rules
- Treat this service as a separate backend boundary from `apps/api`.
- Keep retrieval, ingestion, extraction, and validation concerns local to this service.
- If logic must be shared across product boundaries, move neutral primitives into `packages/*` instead of importing from another app or service.
- Preserve explicit CORS and trusted-host defaults if network behavior is added later.
- Make caps, corpus-size assumptions, truncation, and retrieval shortfalls explicit in logs, tests, and returned diagnostics; do not turn these conditions into silent under-selection.

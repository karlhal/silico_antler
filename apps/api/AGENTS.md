# API Agent Guide

## Scope
Applies to `apps/api` only. Use with the root `../../AGENTS.md`.

## Primary Commands
- Install/update deps: `uv sync --group dev`
- Run tests: `uv run pytest -q`
- Run service: `uv run uvicorn app.main:app --reload --port 8000`

## Must-Read Context
- Agent docs index: [`../../docs/agents/index.md`](../../docs/agents/index.md)
- Security constraints: [`../../docs/agents/security-constraints.md`](../../docs/agents/security-constraints.md)
- Quality gates: [`../../docs/agents/quality-gates.md`](../../docs/agents/quality-gates.md)
- App README: [`./README.md`](./README.md)
- Package README: [`./app/README.md`](./app/README.md)
- Tests README: [`./tests/README.md`](./tests/README.md)

## Local Rules
- Keep `app/main.py` focused on wiring.
- Preserve stable API behavior unless explicitly versioned.
- Keep CORS/trusted host defaults restrictive.
- Update docs when endpoint behavior or env requirements change.
- Do not mask upstream or orchestration failures behind empty payloads or generic success responses; log the limit, filter, or dependency condition that changed the outcome.

# Backend Improvement Plan

## Problem Statement

The method-development service has three core problems:

1. **Cost & rate limits**: Groq and Gemini APIs have free-tier rate limits that will block real users. DeepSeek is ~10x cheaper and purpose-built for reasoning tasks.
2. **Extraction failures**: The LLM fallback in `hplc_text_extraction.py` fires but returns `None`, so open-access HPLC papers produce zero results even when the method is clearly present.
3. **Messy orchestration**: Settings have conflicting defaults, the provider abstraction leaks "gemini" naming everywhere even for Groq/OpenAI-compatible APIs, and the step-budget system is tangled with the recommendation engine.

## Vertical Slices (implement in order)

| Slice | File | What changes | Risk |
|-------|------|-------------|------|
| 1 | [slice-1-deepseek-provider.md](slice-1-deepseek-provider.md) | Replace Groq/Gemini split with `OpenAICompatibleClient`; add Z.AI + DeepSeek | Low — additive |
| 1b | [slice-1b-provider-pool.md](slice-1b-provider-pool.md) | Multi-provider pool: route across Z.AI + Gemini + Groq by concurrency | Low — additive, depends on Slice 1 |
| 2 | [slice-2-fix-extraction.md](slice-2-fix-extraction.md) | Fix LLM fallback; better chunking; structured extraction prompt | Medium — core path |
| 3 | [slice-3-open-access-pipeline.md](slice-3-open-access-pipeline.md) | Reliable open-access paper fetch + extract end-to-end | Medium — I/O heavy |
| 4 | [slice-4-orchestration-cleanup.md](slice-4-orchestration-cleanup.md) | Remove conflicting config, unify step budget, clean router logic | Low — refactor |

## Recommended provider for launch

Use **Z.AI** as the default provider:
- `GLM-4-Plus` as worker: 20 concurrent free requests — handles parallel batch extraction without hitting limits
- `GLM-4.6` as planner: 3 concurrent free — fine, only 1 plan runs per recommendation
- Base URL: `https://api.z.ai/api/paas/v4` — OpenAI-compatible, drops in as a thin subclass
- Switch to DeepSeek (`deepseek-chat`, $0.07/M) once you have paying users who need guaranteed SLA

## Why not LangChain?

The existing custom LLM client is 200 lines and does exactly what we need. LangChain would add ~300 MB of deps, opaque chain abstractions, and a new way for things to fail silently. The problems here are domain-specific (HPLC extraction logic, provider switching) — not framework problems. Fix the code, not the tooling.

If we later need multi-step tool-calling agents with memory, LangGraph is a better fit than LangChain for this use case.

## Implementation session checklist

- [ ] Slice 1 — provider abstraction + Z.AI + DeepSeek
- [ ] Slice 1b — provider pool (depends on 1)
- [ ] Slice 2 — extraction fix (most important)
- [ ] Slice 3 — open-access pipeline
- [ ] Slice 4 — orchestration cleanup
- [ ] Quality gate: `cd services/method-development && uv run pytest -q`

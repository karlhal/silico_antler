from __future__ import annotations

import logging
import os

import httpx

from .schemas import (
    FollowUpChatMessage,
    FollowUpChatRequest,
    FollowUpChatResponse,
    FollowUpGradientPoint,
    FollowUpMobilePhase,
    FollowUpRecommendationContext,
)

logger = logging.getLogger("silico.api.follow_up")


def _format_mobile_phase(phase: FollowUpMobilePhase | None) -> str | None:
    if not phase or not phase.solvent:
        return None

    parts: list[str] = [phase.solvent]
    if phase.additive:
        parts.append(phase.additive)
    if phase.ph_estimate is not None:
        parts.append(f"pH {phase.ph_estimate:g}")
    return " / ".join(parts)


def _format_gradient(points: list[FollowUpGradientPoint], isocratic_percent_b: float | None) -> str | None:
    if points:
        ordered = sorted(points, key=lambda point: point.time_min)
        if len(ordered) >= 4:
            start = ordered[0]
            peak = max(ordered, key=lambda point: point.percent_b)
            finish = ordered[-1]
            return (
                f"{start.percent_b:g}->{peak.percent_b:g} %B ({start.time_min:g}-{peak.time_min:g} min), "
                f"then back to {finish.percent_b:g} %B by {finish.time_min:g} min"
            )
        if len(ordered) == 3:
            first, second, third = ordered
            return (
                f"{first.percent_b:g}->{second.percent_b:g} %B ({first.time_min:g}-{second.time_min:g} min), "
                f"then {third.percent_b:g} %B at {third.time_min:g} min"
            )
        if len(ordered) == 2:
            first, second = ordered
            return f"{first.percent_b:g}->{second.percent_b:g} %B ({first.time_min:g}-{second.time_min:g} min)"
        point = ordered[0]
        return f"{point.percent_b:g} %B at {point.time_min:g} min"

    if isocratic_percent_b is not None:
        return f"{isocratic_percent_b:g} %B isocratic"

    return None


def _build_method_conditions(recommendation: FollowUpRecommendationContext) -> str:
    formatted: list[str] = []

    phase_a = _format_mobile_phase(recommendation.mobile_phase_a)
    phase_b = _format_mobile_phase(recommendation.mobile_phase_b)

    if phase_a and phase_b:
        formatted.append(f"Mobile phases {phase_a} / {phase_b}")
    elif phase_a:
        formatted.append(f"Mobile phase {phase_a}")

    if isinstance(recommendation.flow_rate_ml_min, (int, float)):
        formatted.append(f"{recommendation.flow_rate_ml_min:.2f} mL/min")
    if isinstance(recommendation.run_time_min, (int, float)):
        formatted.append(f"{recommendation.run_time_min:.2f} min runtime")
    if isinstance(recommendation.column_temperature_c, (int, float)):
        formatted.append(f"{recommendation.column_temperature_c:.1f} deg C")

    gradient_text = _format_gradient(recommendation.gradient_profile, recommendation.isocratic_percent_b)
    if gradient_text:
        formatted.append(gradient_text)

    if formatted:
        return ". ".join(formatted)

    if recommendation.core_method_summary:
        return recommendation.core_method_summary

    return "The current report does not expose a structured method block for this recommendation."


def _build_context_digest(payload: FollowUpChatRequest) -> str:
    recommendation = payload.active_recommendation
    if recommendation is None:
        return "\n".join(
            [
                f"Original request: {payload.request_text or 'Unavailable'}",
                f"Source mode: {payload.source_mode or 'Unavailable'}",
                f"Runtime mode: {payload.runtime_mode or 'Unavailable'}",
                f"Result origin: {payload.result_origin or 'Unavailable'}",
                f"System summary: {payload.system_summary or 'Unavailable'}",
                f"Search query used: {payload.search_query_used or 'Unavailable'}",
                "No active recommendation is available yet.",
            ]
        )

    return "\n".join(
        [
            f"Original request: {payload.request_text or 'Unavailable'}",
            f"Source mode: {payload.source_mode or 'Unavailable'}",
            f"Runtime mode: {payload.runtime_mode or 'Unavailable'}",
            f"Result origin: {payload.result_origin or 'Unavailable'}",
            f"System summary: {payload.system_summary or 'Unavailable'}",
            f"Search query used: {payload.search_query_used or 'Unavailable'}",
            f"Recommendation count: {payload.recommendations_count}",
            f"Active recommendation title: {recommendation.title}",
            f"Citation: {recommendation.citation or 'Unavailable'}",
            f"Rationale: {recommendation.rationale or 'Unavailable'}",
            f"Method conditions: {_build_method_conditions(recommendation)}",
            f"Trust state: {recommendation.trust_state or 'Unavailable'}",
            f"Validation status: {recommendation.validation_status or 'Unavailable'}",
            f"Scaling notes: {', '.join(recommendation.scaling_notes) or 'None'}",
            f"Warnings: {', '.join(recommendation.warning_summary) or 'None'}",
            f"Dominant differentiator: {recommendation.dominant_differentiator or 'Unavailable'}",
        ]
    )


def _build_history_digest(history: list[FollowUpChatMessage]) -> str:
    if not history:
        return "No prior follow-up turns."

    return "\n".join(f"{turn.role}: {turn.content}" for turn in history[-6:])


async def _answer_with_openai(payload: FollowUpChatRequest, api_key: str) -> str:
    model = os.getenv("OPENAI_FOLLOW_UP_MODEL", "gpt-4.1-mini")
    user_prompt = "\n\n".join(
        [
            "Use only the grounded context below. Never invent missing method settings or report results.",
            "If the context does not contain the answer, say what is missing and suggest the next grounded step.",
            "Answer in plain text, concise but helpful, usually 1-4 sentences.",
            f"Context:\n{_build_context_digest(payload)}",
            f"Recent follow-up turns:\n{_build_history_digest(payload.history)}",
            f"Operator question:\n{payload.question}",
        ]
    )

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": "You answer follow-up questions about a chromatography recommendation report. Stay grounded in the supplied report context.",
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            },
        )
        response.raise_for_status()
        payload_json = response.json()

    choices = payload_json.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        flattened = " ".join(
            item.get("text", "").strip()
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
        if flattened:
            return flattened

    raise RuntimeError("OpenAI returned an empty message.")


def _build_fallback_answer(payload: FollowUpChatRequest) -> str:
    recommendation = payload.active_recommendation
    question = payload.question.strip()
    lower = question.lower()

    if recommendation is None:
        if payload.request_text:
            return (
                f"I do not have a completed recommendation report to answer from yet. "
                f"The current request is: {payload.request_text}."
            )
        return "I do not have enough report context yet to answer that groundedly."

    method_conditions = _build_method_conditions(recommendation)

    if any(
        phrase in lower
        for phrase in [
            "experimental condition",
            "experimental setup",
            "conditions",
            "settings",
            "best one",
            "method",
            "flow rate",
            "gradient",
            "mobile phase",
            "runtime",
            "temperature",
        ]
    ):
        return f"Best current method: {method_conditions}."

    if any(phrase in lower for phrase in ["why", "rationale", "win", "best"]):
        rationale = (
            recommendation.rationale
            or recommendation.dominant_differentiator
            or "It currently has the strongest grounded fit in the report."
        )
        return f"Best current recommendation: {recommendation.title}. {rationale}"

    if any(phrase in lower for phrase in ["warning", "risk", "caution"]):
        warnings = recommendation.warning_summary or []
        if warnings:
            return "Current warnings: " + "; ".join(warnings[:3])
        return "The current best method does not carry any surfaced warning summary in the report."

    tail = recommendation.rationale or recommendation.dominant_differentiator or ""
    parts = [
        f"Best current recommendation: {recommendation.title}.",
        f"{method_conditions}.",
        tail,
    ]
    return " ".join(part.strip() for part in parts if part and part.strip())


async def answer_follow_up_question(payload: FollowUpChatRequest) -> FollowUpChatResponse:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if api_key:
        try:
            answer = await _answer_with_openai(payload, api_key)
            return FollowUpChatResponse(answer=answer, source="openai")
        except Exception as exc:  # pragma: no cover - exercised indirectly in tests via fallback
            logger.warning("OpenAI follow-up answer failed; falling back to grounded summary: %s", exc)
    else:
        logger.info("OPENAI_API_KEY is not set; using grounded follow-up fallback.")

    return FollowUpChatResponse(
        answer=_build_fallback_answer(payload),
        source="grounded_fallback",
    )

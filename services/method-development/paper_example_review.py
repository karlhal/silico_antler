from __future__ import annotations

import json
from pathlib import Path
import re

from paper_example_evaluation import load_gold_fixtures


SERVICE_ROOT = Path(__file__).resolve().parent
OUTPUT_REPORT = (
    SERVICE_ROOT.parent
    / "output"
    / "method-development"
    / "paper-example-evaluation.json"
)
PROMPT_FIXTURE = (
    SERVICE_ROOT / "tests" / "paper_example" / "expected" / "evaluation_prompts.json"
)


def load_evaluation_report() -> dict:
    return json.loads(OUTPUT_REPORT.read_text())


def load_prompt_examples() -> dict:
    return json.loads(PROMPT_FIXTURE.read_text())


def collect_problem_checks(report: dict) -> list[dict]:
    items: list[dict] = []
    for paper_report in report.get("reports", []):
        for check in paper_report.get("checks", []):
            if check.get("status") not in {"mismatched", "missing"}:
                continue
            items.append(
                {
                    "paper_id": paper_report["paper_id"],
                    "source_kind": paper_report["source_kind"],
                    "field_path": check["field_path"],
                    "status": check["status"],
                    "expected": check.get("expected"),
                    "actual": check.get("actual"),
                    "note": check.get("note"),
                }
            )
    return items


def build_prompt_candidates(prompt: str) -> dict:
    prompt_tokens = _tokenize(prompt)
    fixtures = load_gold_fixtures()
    candidates = []
    for fixture in fixtures:
        descriptor = _fixture_descriptor_text(fixture)
        fixture_tokens = _tokenize(descriptor)
        overlap = sorted(prompt_tokens & fixture_tokens)
        score = round(
            len(overlap) / max(1, min(len(prompt_tokens), len(fixture_tokens))), 3
        )
        candidates.append(
            {
                "paper_id": fixture["paper_id"],
                "title": fixture["title"],
                "score": score,
                "overlap_tokens": overlap,
            }
        )

    candidates.sort(
        key=lambda item: (item["score"], len(item["overlap_tokens"])), reverse=True
    )
    should_find = bool(candidates and candidates[0]["score"] >= 0.08)
    return {
        "prompt": prompt,
        "should_find": should_find,
        "top_candidates": candidates[:3],
    }


def _fixture_descriptor_text(fixture: dict) -> str:
    expected = fixture.get("expected", {})
    chunks = [fixture.get("title", "")]
    for section in ("chromatography_system", "method_parameters"):
        section_payload = expected.get(section, {})
        if isinstance(section_payload, dict):
            chunks.extend(str(value) for value in section_payload.values())
    for entity in expected.get("retention_entities", []):
        chunks.append(str(entity.get("name", "")))
    return " ".join(chunks)


def _tokenize(text: str) -> set[str]:
    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "was",
        "were",
        "using",
        "used",
        "method",
        "final",
        "including",
        "extract",
        "find",
        "analysis",
        "these",
        "paper",
        "papers",
    }
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in stopwords
    }

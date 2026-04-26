from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from paper_example_evaluation import run_paper_example_evaluation
from paper_example_review import (
    build_prompt_candidates,
    collect_problem_checks,
    load_prompt_examples,
)


def test_prompt_examples_load() -> None:
    prompts = load_prompt_examples()

    assert "positive" in prompts
    assert "negative" in prompts
    assert prompts["positive"]
    assert prompts["negative"]


def test_collect_problem_checks_returns_mismatches_or_missing_only() -> None:
    report = run_paper_example_evaluation()
    problem_checks = collect_problem_checks(report)

    assert problem_checks
    assert {item["status"] for item in problem_checks} <= {"mismatched", "missing"}


def test_build_prompt_candidates_prefers_relevant_fixture() -> None:
    result = build_prompt_candidates(
        "Extract the final LC-MS/MS method for carotenoids and vitamins in plasma"
    )

    assert result["should_find"] is True
    assert result["top_candidates"][0]["paper_id"] == "mdpi_carotenoid_method"


def test_build_prompt_candidates_can_flag_unrelated_prompt() -> None:
    result = build_prompt_candidates("Find a GC-MS cannabinoid method")

    assert result["should_find"] is False


def test_build_prompt_candidates_supports_final_over_optimization_prompt() -> None:
    result = build_prompt_candidates(
        "Find the selected final glucose HPLC method for Shewanella media and ignore optimization-only trial conditions."
    )

    assert result["should_find"] is True
    assert result["top_candidates"][0]["paper_id"] == "plos_glucose_method"

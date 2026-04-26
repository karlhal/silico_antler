from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from paper_example_evaluation import load_gold_fixtures, run_paper_example_evaluation


def test_gold_fixtures_load_for_both_example_papers() -> None:
    fixtures = load_gold_fixtures()

    assert len(fixtures) == 2
    assert {fixture["paper_id"] for fixture in fixtures} == {
        "mdpi_carotenoid_method",
        "plos_glucose_method",
    }


def test_paper_example_evaluation_runs_for_pdf_and_html_sources() -> None:
    report = run_paper_example_evaluation()

    assert report["fixtures_evaluated"] == 2
    assert len(report["reports"]) == 4
    assert report["aggregate"]["supported_total"] > 0
    assert {item["source_kind"] for item in report["reports"]} == {"pdf", "html"}
    assert all("summary" in item for item in report["reports"])

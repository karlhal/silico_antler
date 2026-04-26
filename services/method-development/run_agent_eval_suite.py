import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.ai_runtime_settings import AiRuntimeSettings
from app.gemini_orchestration_client import GeminiObserverInsight
from app.sqlite_review_record_store import SqliteReviewRecordStore
from app.retrieval_store import SeededRetrievalStore
from app.source_document_registry import InMemorySourceDocumentRegistry
from app.open_access_client import OpenAccessPaperClient
from app.recommendation_schemas import OpenAccessPaperCandidate, FetchedSourceArtifact

# Setup mock clients and state
class _FakeOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self, case_id: str = ""):
        self.case_id = case_id

    def search_papers(self, query: str, *, max_papers: int = 5) -> List[OpenAccessPaperCandidate]:
        if self.case_id == "recommendation.open_access_screening_skip":
            return [
                OpenAccessPaperCandidate(
                    paper_id="paper-mdpi",
                    title="Development of an Advanced HPLC-MS/MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma",
                    doi="10.3390/ijms17101719",
                    url="https://example.test/mdpi",
                    published_year=2016,
                    source_name="International Journal of Molecular Sciences",
                    abstract="Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS.",
                    open_access=True,
                ),
                OpenAccessPaperCandidate(
                    paper_id="skipped-paper",
                    title="Something completely irrelevant about astronomy",
                    doi="10.1000/astronomy",
                    url="https://example.test/astronomy",
                    published_year=2020,
                    source_name="Astronomy Today",
                    abstract="Stars are bright.",
                    open_access=True,
                )
            ]
        
        if self.case_id == "recommendation.open_access_fetch_degraded":
            return [
                OpenAccessPaperCandidate(
                    paper_id="paper-mdpi",
                    title="Development of an Advanced HPLC-MS/MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma",
                    doi="10.3390/ijms17101719",
                    url="https://example.test/success",
                    published_year=2016,
                    source_name="International Journal of Molecular Sciences",
                    abstract="Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS.",
                    open_access=True,
                ),
                OpenAccessPaperCandidate(
                    paper_id="failed-paper",
                    title="LC-MS/MS method for carotenoids in human plasma",
                    doi="10.3390/fail",
                    url="https://example.test/fail",
                    published_year=2016,
                    source_name="Fail Journal",
                    abstract="LC-MS/MS determination of carotenoids in plasma.",
                    open_access=True,
                )
            ]

        if self.case_id == "recommendation.no_trustworthy_candidates":
            return [
                OpenAccessPaperCandidate(
                    paper_id="untrustworthy-paper",
                    title="Untrustworthy Paper",
                    doi="10.3390/untrustworthy",
                    url="https://example.test/untrustworthy",
                    published_year=2016,
                    source_name="Untrustworthy Journal",
                    abstract="Abstract here.",
                    open_access=True,
                )
            ]

        return [OpenAccessPaperCandidate(
            paper_id="paper-mdpi",
            title="Development of an Advanced HPLC-MS/MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma",
            doi="10.3390/ijms17101719",
            url="https://example.test/mdpi",
            published_year=2016,
            source_name="International Journal of Molecular Sciences",
            abstract="Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS.",
            open_access=True,
        )]

    def fetch_source_artifact(self, candidate: OpenAccessPaperCandidate) -> FetchedSourceArtifact:
        if self.case_id == "recommendation.open_access_fetch_degraded" and candidate.paper_id == "failed-paper":
             raise Exception("Simulated fetch failure")
             
        if self.case_id == "recommendation.no_trustworthy_candidates":
             return FetchedSourceArtifact(
                paper_id=candidate.paper_id,
                kind="html",
                title=candidate.title,
                doi=candidate.doi,
                url=candidate.url,
                published_year=candidate.published_year,
                file_name="bad.html",
                html_content="<html><body>Very little info here.</body></html>",
            )

        paper_path = PROJECT_ROOT / "tests/paper_example/Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="html",
            title=candidate.title,
            doi=candidate.doi,
            url=candidate.url,
            published_year=candidate.published_year,
            file_name="mdpi.html",
            html_content=paper_path.read_text(),
        )

class _FakeGeminiClient:
    def summarize_c12_outcome(self, **_: Any) -> GeminiObserverInsight:
        return GeminiObserverInsight(
            model="gemini-2.5-pro",
            summary="Review record is approved and demo-ready.",
            recommended_next_action="proceed_to_demo",
            concerns=[],
        )

def setup_app_state(case_id: str = "", enable_ai: bool = False):
    app.state.limiter.enabled = False
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
    app.state.review_record_store = SqliteReviewRecordStore()
    
    if case_id == "recommendation.local_corpus_impurity_ranking":
        from app.retrieval_schemas import RetrievalMethodRecord, SourceDocumentMetadata, HplcMolecularEntity, ChromatographySystem, MethodParameters, MobilePhase, RetrievalProvenance
        def _build_record(record_id: str, entities: list):
            return RetrievalMethodRecord(
                record_id=record_id,
                source_document=SourceDocumentMetadata(source_document_id=f"seed:{record_id}", source_type="seeded", title=f"Method for {record_id}"),
                molecular_entities=[HplcMolecularEntity(local_identifier=name, display_name=name, smiles_string=smiles) for name, smiles in entities],
                chromatography_system=ChromatographySystem(mode="rp_lc", column_manufacturer="Waters", column_name="Acquity BEH C18", stationary_phase_chemistry="C18", column_length_mm=100.0, column_inner_diameter_mm=2.1, particle_size_um=1.7),
                method_parameters=MethodParameters(mobile_phase_a=MobilePhase(solvent="water"), mobile_phase_b=MobilePhase(solvent="acetonitrile"), flow_rate_ml_min=0.35, run_time_min=12.0),
                provenance=RetrievalProvenance(extraction_mode="seeded", extraction_confidence=1.0, evidence_snippets=[{"section_label": "Seeded", "text": "Seeded record"}])
            )
        app.state.retrieval_store = SeededRetrievalStore(records=[
            _build_record("record-target-only", [("ethanol", "CCO")]),
            _build_record("record-multi-analyte", [("ethanol", "CCO"), ("acetone", "CC(=O)C")]),
        ])
    else:
        app.state.retrieval_store = SeededRetrievalStore.from_seed_file()

    app.state.ai_runtime_settings = AiRuntimeSettings(
        google_api_key="demo-key" if enable_ai else None,
        enable_llm_orchestration=enable_ai,
        planner_model="gemini-2.5-pro",
        worker_model="gemini-2.5-flash",
        llm_timeout_sec=20,
        llm_max_calls_per_run=6,
        max_step_attempts_per_run=1,
        max_total_steps_per_run=5,
    )
    app.state.open_access_client = _FakeOpenAccessPaperClient(case_id)
    app.state.gemini_client = _FakeGeminiClient()

client = TestClient(app)

def run_recommendation(case_id: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
    setup_app_state(case_id)
    response = client.post("/recommendation/run", json=request_payload)
    # We don't return early on 422 if we expect it
    return response.json() if response.status_code == 200 or response.status_code == 422 else {"error": response.json()}

def run_orchestration(case_id: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
    enable_ai = request_payload.get("enable_ai_observer", False)
    payload = {k: v for k, v in request_payload.items() if k != "enable_ai_observer"}
    setup_app_state(case_id, enable_ai=enable_ai)
    # If it's a reuse test, we need to run it once first
    if payload.get("retry_existing") and "eval-orch-001" in payload["source_document"]["source_document_id"]:
         client.post("/c12/review-records/orchestrate", json=payload)
    
    response = client.post("/c12/review-records/orchestrate", json=payload)
    if response.status_code != 200:
        return {"error": response.json()}
    return response.json()

def get_trace_value(payload: Dict[str, Any], path: str) -> Any:
    # 422 errors wrap the detail in a dict
    if "detail" in payload and isinstance(payload["detail"], dict) and path in payload["detail"]:
         return payload["detail"].get(path)

    parts = path.split(".")
    val = payload
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.json import JSON

def grade_case(case: Dict[str, Any], console: Console) -> Dict[str, Any]:
    if not console:
        # Fallback if needed, though we pass it now
        console = Console()
        
    console.print(f"Running case: [bold cyan]{case['case_id']}[/bold cyan]...")
    if case["runner"] == "recommendation":
        actual = run_recommendation(case["case_id"], case["request"])
    elif case["runner"] == "orchestration":
        actual = run_orchestration(case["case_id"], case["request"])
    else:
        return {"case_id": case["case_id"], "status": "failed", "error": f"Unknown runner: {case['runner']}"}

    if "error" in actual:
        return {"case_id": case["case_id"], "status": "failed", "error": actual["error"]}

    mismatches = []
    
    # Trace grading
    for path, expected_val in case.get("expected_trace", {}).items():
        actual_val = get_trace_value(actual, path)
        if actual_val != expected_val:
            mismatches.append(f"Trace mismatch at {path}: expected {expected_val}, got {actual_val}")

    # Outcome grading (shortcut for common fields)
    expected_outcome = case.get("expected_outcome", {})
    if "status" in expected_outcome:
        actual_status = actual.get("runtime", {}).get("status") if case["runner"] == "recommendation" else None
        if actual_status and actual_status != expected_outcome["status"]:
             mismatches.append(f"Outcome mismatch: status expected {expected_outcome['status']}, got {actual_status}")
    
    if "recommended_paper_id" in expected_outcome:
        actual_paper_id = actual.get("recommended_candidate", {}).get("paper_id")
        if actual_paper_id != expected_outcome["recommended_paper_id"]:
             mismatches.append(f"Outcome mismatch: recommended_paper_id expected {expected_outcome['recommended_paper_id']}, got {actual_paper_id}")

    if "registration_status" in expected_outcome:
        actual_reg = actual.get("steps", {}).get("registration", {}).get("status")
        if actual_reg != expected_outcome["registration_status"]:
            mismatches.append(f"Outcome mismatch: registration_status expected {expected_outcome['registration_status']}, got {actual_reg}")

    if "extraction_status" in expected_outcome:
        actual_ext = actual.get("steps", {}).get("extraction", {}).get("status")
        if actual_ext != expected_outcome["extraction_status"]:
            mismatches.append(f"Outcome mismatch: extraction_status expected {expected_outcome['extraction_status']}, got {actual_ext}")

    if "approval_status" in expected_outcome:
        actual_app = actual.get("steps", {}).get("approval", {}).get("status")
        if actual_app != expected_outcome["approval_status"]:
            mismatches.append(f"Outcome mismatch: approval_status expected {expected_outcome['approval_status']}, got {actual_app}")

    if "record_status" in expected_outcome:
        actual_rec = actual.get("review_record", {}).get("status")
        if actual_rec != expected_outcome["record_status"]:
            mismatches.append(f"Outcome mismatch: record_status expected {expected_outcome['record_status']}, got {actual_rec}")

    if "cutoff_reached" in expected_outcome:
        actual_cutoff = actual.get("budget", {}).get("cutoff_reached")
        if actual_cutoff != expected_outcome["cutoff_reached"]:
            mismatches.append(f"Outcome mismatch: cutoff_reached expected {expected_outcome['cutoff_reached']}, got {actual_cutoff}")

    if "ai_observer_status" in expected_outcome:
        actual_obs = actual.get("steps", {}).get("ai_observer", {}).get("status")
        if actual_obs != expected_outcome["ai_observer_status"]:
            mismatches.append(f"Outcome mismatch: ai_observer_status expected {expected_outcome['ai_observer_status']}, got {actual_obs}")

    status = "passed" if not mismatches else "failed"
    return {
        "case_id": case["case_id"],
        "status": status,
        "mismatches": mismatches,
        "behavior": case["behavior"]
    }

def main():
    parser = argparse.ArgumentParser(description="Run Agent Eval Suite")
    parser.add_argument("--suite", choices=["smoke", "core", "extended"], default="smoke")
    parser.add_argument("--case", help="Run a specific case by ID")
    parser.add_argument("--json-output", help="Path to write JSON scorecard")
    args = parser.parse_args()

    console = Console()
    dataset_path = PROJECT_ROOT / "tests/fixtures/agent_eval_dataset.json"
    with open(dataset_path) as f:
        dataset = json.load(f)

    cases_to_run = [
        c for c in dataset["cases"]
        if (args.case and c["case_id"] == args.case) or (not args.case and (args.suite == "extended" or c["suite"] == args.suite or (args.suite == "core" and c["suite"] == "smoke")))
    ]

    results = []
    passed = 0
    for case in cases_to_run:
        res = grade_case(case, console)
        results.append(res)
        if res["status"] == "passed":
            passed += 1

    scorecard = {
        "suite": args.suite,
        "total": len(cases_to_run),
        "passed": passed,
        "failed": len(cases_to_run) - passed,
        "results": results
    }

    summary_table = Table(title=f"Agent Eval Scorecard: {args.suite}")
    summary_table.add_column("Case ID")
    summary_table.add_column("Status")
    summary_table.add_column("Behavior")
    for res in results:
        status_str = f"[bold green]PASSED[/bold green]" if res["status"] == "passed" else f"[bold red]FAILED[/bold red]"
        summary_table.add_row(res["case_id"], status_str, res["behavior"])
    
    console.print(summary_table)

    console.print(Panel(f"Total: {len(cases_to_run)} | Passed: [bold green]{passed}[/bold green] | Failed: [bold red]{len(cases_to_run) - passed}[/bold red]", title="Summary"))

    if args.json_output:
        out_path = Path(args.json_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(scorecard, f, indent=2)
        console.print(f"\nScorecard saved to {args.json_output}")

    if passed < len(cases_to_run):
        for res in results:
            if res["status"] == "failed":
                console.print(f"\n[bold red]FAILED:[/bold red] {res['case_id']}")
                for m in res.get("mismatches", []):
                    console.print(f"  - {m}")
                if "error" in res:
                    console.print(Panel(JSON.from_data(res["error"]), title="Error Details", border_style="red"))
        sys.exit(1)

if __name__ == "__main__":
    main()

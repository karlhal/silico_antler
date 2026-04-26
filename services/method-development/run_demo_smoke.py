from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.json import JSON


SERVICE_ROOT = Path(__file__).resolve().parent
DEFAULT_FIXTURE_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "sample_hplc_detail_and_anchoring_article.html"
)


def _load_local_env_file() -> None:
    env_path = SERVICE_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Method development service smoke test")
    parser.add_argument("--fixture", help="Path to source document fixture (HTML or PDF)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed runtime data")
    parser.add_argument("--debug", action="store_true", help="Print full raw responses")
    parser.add_argument("--json", action="store_true", help="Machine-readable output only")
    args = parser.parse_args()

    _load_local_env_file()

    project_root = SERVICE_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from fastapi.testclient import TestClient

    from app.ai_runtime_settings import load_ai_runtime_settings
    from app.gemini_orchestration_client import OrchestrationClientError
    from app.main import app

    console = Console(stderr=True) if args.json else Console()
    
    settings = load_ai_runtime_settings()
    provider_credentials_present = bool(
        settings.google_api_key
        or settings.groq_api_key
        or settings.zai_api_key
        or settings.openrouter_api_key
        or settings.llm_base_url
    )
    if settings.enable_llm_orchestration and not provider_credentials_present:
        if not args.json:
            console.print(
                "[bold red]ERROR[/bold red]: LLM orchestration is enabled but no provider credentials are configured."
            )
        return 2

    client = TestClient(app)

    results: dict[str, Any] = {
        "settings": {
            "llm_provider": settings.llm_provider,
            "llm_orchestration_enabled": settings.enable_llm_orchestration,
            "provider_credentials_present": provider_credentials_present,
            "planner_model": settings.planner_model,
            "worker_model": settings.worker_model,
            "llm_timeout_sec": settings.llm_timeout_sec,
            "llm_max_calls_per_run": settings.llm_max_calls_per_run,
            "max_step_attempts_per_run": settings.max_step_attempts_per_run,
            "max_total_steps_per_run": settings.max_total_steps_per_run,
        }
    }

    if not args.json:
        console.print(Panel(JSON.from_data(results["settings"]), title="AI Runtime Settings"))

    if settings.enable_llm_orchestration:
        llm_client = getattr(app.state, "gemini_client", None)
        if llm_client is None:
            if not args.json:
                console.print(
                    "[bold red]ERROR[/bold red]: LLM orchestration is enabled but the LLM client was not initialized."
                )
            return 2
        try:
            probe = llm_client.probe_connection()
        except OrchestrationClientError as exc:
            if not args.json:
                console.print(
                    f"[bold red]ERROR[/bold red]: LLM connectivity probe failed: {exc}"
                )
            return 2
        
        results["llm_probe"] = {
            "ok": probe.ok,
            "model": probe.model,
            "response_text": probe.response_text,
        }
        
        if not args.json:
            console.print(Panel(JSON.from_data(results["llm_probe"]), title="LLM Connectivity Probe"))
            
        if not probe.ok:
            if not args.json:
                console.print("[bold red]ERROR[/bold red]: LLM probe did not return OK.")
            return 2

    health_response = client.get("/health")
    if health_response.status_code != 200:
        if not args.json:
            console.print(f"[bold red]ERROR[/bold red]: health check failed ({health_response.status_code}): {health_response.text}")
        return 1
    results["health"] = {"status": "ok", "status_code": 200}

    fixture_path = Path(args.fixture) if args.fixture else DEFAULT_FIXTURE_PATH
    if not fixture_path.exists():
        if not args.json:
            console.print(f"[bold red]ERROR[/bold red]: Fixture not found at {fixture_path}")
        return 1

    orchestration_payload = {
        "source_document": {
            "source_document_id": f"smoke-{fixture_path.stem}",
            "source_type": "html" if fixture_path.suffix.lower() != ".pdf" else "pdf",
            "url": f"https://example.test/smoke/{fixture_path.name}",
        },
        "html_content": fixture_path.read_text() if fixture_path.suffix.lower() != ".pdf" else None,
        "approve_if_ready": True,
        "max_total_steps": 5,
        "entity_resolutions": [
            {
                "local_identifier": "intermediate 2",
                "smiles_string": "c1ccccc1",
                "display_name": "Intermediate 2",
            }
        ],
    }
    
    # PDF handling if needed, though smoke currently uses HTML fixture
    if fixture_path.suffix.lower() == ".pdf":
        import base64
        orchestration_payload["pdf_content_base64"] = base64.b64encode(fixture_path.read_bytes()).decode("utf-8")

    orchestration_response = client.post(
        "/c12/review-records/orchestrate",
        json=orchestration_payload,
    )
    
    if args.debug and not args.json:
        console.print(Panel(JSON.from_data(orchestration_response.json()), title="Raw Orchestration Response"))

    if orchestration_response.status_code != 200:
        if not args.json:
            console.print(f"[bold red]ERROR[/bold red]: orchestration request failed ({orchestration_response.status_code}): {orchestration_response.text}")
        return 1

    orch_data = orchestration_response.json()
    results["orchestration"] = {
        "source_document_id": orch_data["source_document_id"],
        "budget": orch_data["budget"],
        "steps": orch_data["steps"],
        "review_record_status": orch_data["review_record"]["status"],
        "retrieval_ready": orch_data["review_record"]["validation"]["retrieval_ready"],
    }

    if not args.json:
        console.print(Panel(JSON.from_data(results["orchestration"]), title="C12 Orchestration Summary"))

    retrieval_response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "c1ccccc1",
            "limit": 1,
            "min_score": 0.99,
        },
    )
    
    if args.debug and not args.json:
        console.print(Panel(JSON.from_data(retrieval_response.json()), title="Raw Retrieval Response"))

    if retrieval_response.status_code != 200:
        if not args.json:
            console.print(f"[bold red]ERROR[/bold red]: retrieval query failed ({retrieval_response.status_code}): {retrieval_response.text}")
        return 1

    retr_data = retrieval_response.json()
    results["retrieval"] = {"results_count": len(retr_data["results"])}
    if retr_data["results"]:
        top_result = retr_data["results"][0]
        results["retrieval"]["top_result"] = {
            "record_id": top_result["record"]["record_id"],
            "record_state": top_result["review_summary"]["record_state"],
            "score": top_result["score"],
            "match_summary": top_result["match_rationale"]["summary"],
        }
    
    if not args.json:
        console.print(Panel(JSON.from_data(results["retrieval"]), title="Retrieval Summary"))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        console.print("\n[bold green]Smoke test passed.[/bold green]")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

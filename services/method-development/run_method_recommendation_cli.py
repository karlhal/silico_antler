from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal, cast

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table
import questionary

from app.recommendation_engine import best_evidence_snippets, recommend_methods
from app.recommendation_schemas import (
    MethodRecommendationRequest,
    SourceMode,
    SystemSpecs,
)

PreferredMode = Literal["rp_lc", "hilic"]


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI-first HPLC method recommendation")
    subparsers = parser.add_subparsers(dest="command")

    recommend_parser = subparsers.add_parser("recommend")
    _add_recommend_arguments(recommend_parser)

    interactive_parser = subparsers.add_parser("interactive")
    interactive_parser.add_argument("--json", action="store_true")
    interactive_parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    if args.command in {None, "interactive"}:
        return _run_interactive(args)
    if args.command == "recommend":
        return _run_recommend(args)
    return 0


def _add_recommend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request", required=True)
    parser.add_argument("--analyte-name")
    parser.add_argument("--target-smiles")
    parser.add_argument("--matrix")
    parser.add_argument("--preferred-mode", choices=["rp_lc", "hilic"])
    parser.add_argument("--max-run-time", type=float)
    parser.add_argument("--require-ms", action="store_true")

    # System specs arguments
    parser.add_argument("--col-manuf")
    parser.add_argument("--col-name")
    parser.add_argument("--col-chem")
    parser.add_argument("--col-len", type=float)
    parser.add_argument("--col-id", type=float)
    parser.add_argument("--col-psize", type=float)

    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument("--paper-dir")
    parser.add_argument("--open-access-search", action="store_true")
    parser.add_argument("--search-query")
    parser.add_argument("--max-papers", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug", action="store_true")


def _run_recommend(args: argparse.Namespace) -> int:
    request = _request_from_args(args)
    report = recommend_methods(request)
    return _render_report(report, json_output=args.json, debug=args.debug)


def _run_interactive(args: argparse.Namespace) -> int:
    request = _prompt_for_request()
    report = recommend_methods(request)
    return _render_report(
        report,
        json_output=getattr(args, "json", False),
        debug=getattr(args, "debug", False),
    )


def _request_from_args(args: argparse.Namespace) -> MethodRecommendationRequest:
    local_paths = list(getattr(args, "paper", []) or [])
    paper_dir = getattr(args, "paper_dir", None)
    if paper_dir:
        local_paths.extend(_expand_paper_dir(Path(paper_dir)))

    source_mode = cast(
        SourceMode,
        "open_access" if getattr(args, "open_access_search", False) else "local",
    )

    system_specs = SystemSpecs(
        column_manufacturer=getattr(args, "col_manuf", None),
        column_name=getattr(args, "col_name", None),
        column_chemistry=getattr(args, "col_chem", None),
        column_length_mm=getattr(args, "col_len", None),
        column_inner_diameter_mm=getattr(args, "col_id", None),
        particle_size_um=getattr(args, "col_psize", None),
    )

    return MethodRecommendationRequest(
        request_text=args.request,
        analyte_name=getattr(args, "analyte_name", None),
        target_smiles=getattr(args, "target_smiles", None),
        matrix_hint=getattr(args, "matrix", None),
        system_specs=system_specs,
        preferred_mode=cast(
            PreferredMode | None, getattr(args, "preferred_mode", None)
        ),
        max_run_time_min=getattr(args, "max_run_time", None),
        require_mass_spectrometry=getattr(args, "require_ms", False),
        source_mode=source_mode,
        local_paths=local_paths,
        search_query=getattr(args, "search_query", None),
        max_papers=getattr(args, "max_papers", 5),
    )


def _prompt_for_request() -> MethodRecommendationRequest:
    console = Console()
    console.print(Panel.fit("Interactive Method Recommendation", title="Silico CLI"))

    # 1. Their System
    console.print("[bold cyan]Step 1: Your HPLC System[/bold cyan]")
    
    # Selection for common manufacturers
    column_manufacturer = questionary.select(
        "Column manufacturer",
        choices=["Agilent", "Waters", "Phenomenex", "Thermo Scientific", "Shimadzu", "Other"],
        default="Agilent",
    ).ask()
    if column_manufacturer == "Other":
        column_manufacturer = _optional_prompt("Enter custom manufacturer")

    column_name = _optional_prompt("Column name")
    
    # Selection for common chemistries
    column_chemistry = questionary.select(
        "Stationary phase chemistry",
        choices=["C18", "C8", "HILIC", "Phenyl", "Amide", "Other"],
        default="C18",
    ).ask()
    if column_chemistry == "Other":
        column_chemistry = _optional_prompt("Enter custom chemistry")

    column_length = _optional_float_prompt("Column length (mm)")
    column_id = _optional_float_prompt("Column inner diameter (mm)")
    particle_size = _optional_float_prompt("Particle size (um)")

    # Multi-select for available solvents
    available_solvents = questionary.checkbox(
        "Available solvents in your lab (Space to toggle)",
        choices=[
            "Acetonitrile",
            "Methanol",
            "Water (HPLC Grade)",
            "Isopropanol",
            "Tetrahydrofuran (THF)",
        ],
    ).ask()

    # Selection for detector types
    detector_type = questionary.select(
        "Detector type",
        choices=["UV-Vis", "PDA/DAD", "MS/MS", "RID", "ELSD", "Other"],
        default="UV-Vis",
    ).ask()
    if detector_type == "Other":
        detector_type = _optional_prompt("Enter custom detector")

    system_specs = SystemSpecs(
        column_manufacturer=column_manufacturer,
        column_name=column_name,
        column_chemistry=column_chemistry,
        column_length_mm=column_length,
        column_inner_diameter_mm=column_id,
        particle_size_um=particle_size,
        available_solvents=available_solvents or [],
        detector_types=[detector_type] if detector_type else [],
    )

    # 2. What they want to separate
    console.print("\n[bold cyan]Step 2: Separation Target[/bold cyan]")
    request_text = Prompt.ask(
        "What are you trying to separate?",
        default="Recommend an HPLC method",
    )
    analyte_name = _optional_prompt("Target analyte name")
    target_smiles = _optional_prompt("Target SMILES")
    
    # Selection for common matrices
    matrix_hint = questionary.select(
        "Matrix / Sample Source (where is the analyte?)",
        choices=["Human Plasma", "Water (Environmental)", "Urine", "Serum", "Organic Solvent", "Other"],
        default="Human Plasma",
    ).ask()
    if matrix_hint == "Other":
        matrix_hint = _optional_prompt("Enter custom matrix")

    require_ms = Confirm.ask(
        "Require mass spectrometry?",
        default=_infer_require_ms_default(request_text),
    )
    preferred_mode = Prompt.ask(
        "Preferred mode",
        choices=["rp_lc", "hilic", "none"],
        default="none",
    )
    max_run_time = _optional_float_prompt("Max run time (minutes)")

    # 3. Discovery Source
    console.print("\n[bold cyan]Step 3: Discovery Source[/bold cyan]")
    source_mode_choice = cast(
        SourceMode,
        questionary.select(
            "Source mode",
            choices=["local", "open_access"],
            default="local",
        ).ask(),
    )

    local_paths: list[str] = []
    search_query: str | None = None
    max_papers = 5
    if source_mode_choice == "local":
        default_paper_dir = _default_demo_paper_dir()
        paper_dir = (
            Prompt.ask(
                "Directory of papers (.pdf/.html)",
                default=default_paper_dir or "",
            ).strip()
            or None
        )
        if paper_dir:
            local_paths.extend(_expand_paper_dir(Path(paper_dir)))
        while True:
            paper_path = _optional_prompt(
                "Add a single paper path (leave blank to stop)"
            )
            if not paper_path:
                break
            local_paths.append(paper_path)
        if not local_paths:
            if default_paper_dir:
                local_paths.extend(_expand_paper_dir(Path(default_paper_dir)))
                console.print(
                    Panel.fit(
                        f"No local paths supplied, so the bundled demo corpus was used: {default_paper_dir}",
                        title="Using Demo Papers",
                    )
                )
            else:
                raise SystemExit(
                    "Local mode requires at least one paper path or a paper directory."
                )
    else:
        search_query = _optional_prompt("Open-access search query") or request_text
        max_papers = IntPrompt.ask("Max papers to inspect", default=5)

    return MethodRecommendationRequest(
        request_text=request_text,
        analyte_name=analyte_name,
        target_smiles=target_smiles,
        matrix_hint=matrix_hint,
        system_specs=system_specs,
        preferred_mode=cast(
            PreferredMode | None, None if preferred_mode == "none" else preferred_mode
        ),
        max_run_time_min=max_run_time,
        require_mass_spectrometry=require_ms,
        source_mode=source_mode_choice,
        local_paths=local_paths,
        search_query=search_query,
        max_papers=max_papers,
    )


def _render_report(report, *, json_output: bool, debug: bool = False) -> int:
    if json_output:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        return 0

    console = Console()
    request = report.request
    
    # Vocabulary alignment: explicit status and mode
    status = report.runtime.status if report.runtime else "unknown"
    mode = report.source_mode
    console.print(
        Panel.fit(
            f"Request: {request.request_text}\nStatus: [bold]{status}[/bold] | Mode: [bold]{mode}[/bold]",
            title="Recommendation Run",
        )
    )

    if debug and report.runtime:
        console.print(Panel(JSON.from_data(report.runtime.model_dump(mode="json")), title="Runtime Diagnostics (DEBUG)"))

    if report.discovered_papers:
        discovered = Table(title="Discovered Open-Access Papers")
        discovered.add_column("Title")
        discovered.add_column("Year")
        discovered.add_column("DOI/URL")
        for item in report.discovered_papers:
            discovered.add_row(
                item.title,
                str(item.published_year or ""),
                item.doi or item.url or "",
            )
        console.print(discovered)

    ranking = Table(title="Recommendation Candidates")
    ranking.add_column("Rank")
    ranking.add_column("Title")
    ranking.add_column("Score")
    ranking.add_column("Mode")
    ranking.add_column("Run Time")
    for index, candidate in enumerate(report.considered_candidates, start=1):
        mode = (
            candidate.extraction.chromatography_system.mode
            if candidate.extraction.chromatography_system
            else "unknown"
        )
        runtime = (
            f"{candidate.extraction.method_parameters.run_time_min:.1f} min"
            if candidate.extraction.method_parameters
            and candidate.extraction.method_parameters.run_time_min is not None
            else "n/a"
        )
        ranking.add_row(
            str(index),
            candidate.title,
            f"{candidate.score.total_score:.3f}",
            mode,
            runtime,
        )
    console.print(ranking)

    if report.recommended_candidate is None:
        console.print(
            Panel.fit("No candidate methods were extracted.", title="Recommendation")
        )
        return 1

    best = report.recommended_candidate
    console.print(
        Panel.fit(
            f"{best.title}\n{best.citation}\n\n{best.rationale}",
            title="Recommended Method",
        )
    )

    if best.extraction.chromatography_system is not None:
        console.print(
            Panel.fit(
                JSON.from_data(
                    best.extraction.chromatography_system.model_dump(mode="json")
                ),
                title="Chromatography System",
            )
        )
    if best.extraction.method_parameters is not None:
        console.print(
            Panel.fit(
                JSON.from_data(
                    best.extraction.method_parameters.model_dump(mode="json")
                ),
                title="Original Method Parameters (from Literature)",
            )
        )

    if best.recommended_method and best.recommended_method.is_scaled:
        scaled = best.recommended_method
        scaled_data = {
            "flow_rate_ml_min": scaled.flow_rate_ml_min,
            "injection_volume_ul": scaled.injection_volume_ul,
            "run_time_min": scaled.run_time_min,
            "gradient_profile": [p.model_dump() for p in scaled.gradient_profile],
            "scaling_notes": scaled.scaling_notes,
        }
        console.print(
            Panel.fit(
                JSON.from_data(scaled_data),
                title="Optimized for Your System (Physics-Based Scaling)",
                border_style="bold green",
            )
        )

    console.print(
        Panel.fit(
            JSON.from_data(
                [
                    snippet.model_dump(mode="json")
                    for snippet in best_evidence_snippets(best)
                ]
            ),
            title="Evidence Snippets",
        )
    )
    return 0


def _optional_prompt(label: str) -> str | None:
    value = Prompt.ask(label, default="")
    cleaned = value.strip()
    return cleaned or None


def _optional_float_prompt(label: str) -> float | None:
    raw = Prompt.ask(label, default="")
    cleaned = raw.strip()
    if not cleaned:
        return None
    return float(cleaned)


def _expand_paper_dir(path: Path) -> list[str]:
    patterns = ("*.pdf", "*.html", "*.htm")
    paths: list[str] = []
    for pattern in patterns:
        for candidate in sorted(path.glob(pattern)):
            paths.append(str(candidate))
    return paths


def _default_demo_paper_dir() -> str | None:
    candidate = Path(__file__).resolve().parent / "tests" / "paper_example"
    if candidate.exists():
        return str(candidate)
    return None


def _infer_require_ms_default(request_text: str) -> bool:
    normalized = request_text.lower()
    return any(
        token in normalized
        for token in (
            "lc-ms",
            "lc ms",
            "ms/ms",
            "msms",
            "mass spectrometry",
            "triple quadrupole",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

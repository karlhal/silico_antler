from __future__ import annotations

import json

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from paper_example_review import (
    collect_problem_checks,
    load_evaluation_report,
    load_prompt_examples,
)


def main() -> int:
    console = Console()
    report = load_evaluation_report()
    prompts = load_prompt_examples()
    problem_checks = collect_problem_checks(report)

    summary_table = Table(title="Paper Example Benchmark Summary")
    summary_table.add_column("Paper")
    summary_table.add_column("Source")
    summary_table.add_column("Matched", justify="right")
    summary_table.add_column("Total", justify="right")
    summary_table.add_column("Ratio", justify="right")
    for item in report["reports"]:
        summary_table.add_row(
            item["paper_id"],
            item["source_kind"],
            str(item["summary"]["matched"]),
            str(item["summary"]["supported_total"]),
            str(item["summary"]["match_ratio"]),
        )
    console.print(summary_table)
    console.print(
        Panel.fit(
            JSON.from_data(report["aggregate"]),
            title="Aggregate",
        )
    )

    prompt_table = Table(title="Prompt Examples")
    prompt_table.add_column("Type")
    prompt_table.add_column("ID")
    prompt_table.add_column("Prompt")
    prompt_table.add_column("Expected")
    for group_name, entries in prompts.items():
        for entry in entries:
            prompt_table.add_row(
                group_name,
                entry["id"],
                entry["prompt"],
                entry["expected_outcome"],
            )
    console.print(prompt_table)

    if not problem_checks:
        console.print(Panel.fit("No mismatches or missing fields.", title="Problems"))
        return 0

    for item in problem_checks:
        comparison = Table.grid(expand=True)
        comparison.add_column(ratio=1)
        comparison.add_column(ratio=1)
        comparison.add_row(
            Panel(
                JSON.from_data(item["expected"]), title="Expected", border_style="green"
            ),
            Panel(JSON.from_data(item["actual"]), title="Actual", border_style="red"),
        )
        console.print(
            Panel(
                comparison,
                title=(
                    f"{item['paper_id']} [{item['source_kind']}] - "
                    f"{item['field_path']} ({item['status']})"
                ),
                subtitle=item["note"] or "",
            )
        )

    console.print(
        Panel.fit(
            f"Total problem checks: {len(problem_checks)}",
            title="Review Count",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

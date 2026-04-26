from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from paper_example_review import build_prompt_candidates, load_prompt_examples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", help="Prompt to evaluate against example papers")
    args = parser.parse_args()

    console = Console()
    prompt = args.prompt or Prompt.ask("Enter a benchmark prompt")
    result = build_prompt_candidates(prompt)
    prompt_examples = load_prompt_examples()

    console.print(
        Panel.fit(
            f"Prompt: {result['prompt']}\nExpected outcome: {'should_extract' if result['should_find'] else 'should_not_find'}",
            title="Prompt Check",
        )
    )

    table = Table(title="Top Candidate Papers")
    table.add_column("Paper")
    table.add_column("Score", justify="right")
    table.add_column("Overlap Tokens")
    for item in result["top_candidates"]:
        table.add_row(
            item["paper_id"],
            str(item["score"]),
            ", ".join(item["overlap_tokens"][:12]),
        )
    console.print(table)

    examples = Table(title="Stored Prompt Examples")
    examples.add_column("Type")
    examples.add_column("ID")
    examples.add_column("Expected")
    for group_name, entries in prompt_examples.items():
        for entry in entries:
            examples.add_row(group_name, entry["id"], entry["expected_outcome"])
    console.print(examples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

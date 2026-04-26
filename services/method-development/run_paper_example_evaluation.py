from __future__ import annotations

import json
from pathlib import Path

from paper_example_evaluation import run_paper_example_evaluation


def main() -> int:
    report = run_paper_example_evaluation()
    output_path = (
        Path(__file__).resolve().parents[1]
        / "output"
        / "method-development"
        / "paper-example-evaluation.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    print("Paper example evaluation")
    print(json.dumps(report["aggregate"], indent=2))
    for item in report["reports"]:
        print(
            f"- {item['paper_id']} [{item['source_kind']}]: "
            f"{item['summary']['matched']}/{item['summary']['supported_total']} matched"
        )
    print(f"Saved detailed report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

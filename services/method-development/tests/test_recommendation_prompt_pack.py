from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.recommendation_prompt_pack import (
    build_candidate_reranker_prompt,
    parse_candidate_reranker_response,
    parse_field_extraction_response,
    parse_method_evidence_sniff_response,
    parse_query_planner_response,
)


def test_query_planner_parser_rejects_malformed_json() -> None:
    assert parse_query_planner_response("{not-json") is None


def test_candidate_reranker_parser_rejects_duplicate_paper_ids() -> None:
    assert (
        parse_candidate_reranker_response(
            """
            {
              "ranked_candidates": [
                {
                  "paper_id": "paper-1",
                  "shortlist_score": 0.9,
                  "final_method_confidence": 0.9,
                  "matrix_match_confidence": 0.9,
                  "keep": true,
                  "reason": "good"
                },
                {
                  "paper_id": "paper-1",
                  "shortlist_score": 0.2,
                  "final_method_confidence": 0.3,
                  "matrix_match_confidence": 0.1,
                  "keep": false,
                  "reason": "duplicate"
                }
              ]
            }
            """
        )
        is None
    )


def test_method_evidence_sniff_parser_forces_false_below_threshold() -> None:
    parsed = parse_method_evidence_sniff_response(
        """
        {
          "contains_extractable_final_method": true,
          "confidence": 0.21,
          "best_evidence_unit_ids": ["evu-1"],
          "reason": "Weak signal only."
        }
        """
    )

    assert parsed is not None
    assert parsed.contains_extractable_final_method is False


def test_field_extraction_parser_accepts_combined_mobile_phase_gradient_payload() -> None:
    parsed = parse_field_extraction_response(
        "mobile_phase_gradient",
        """
        {
          "mobile_phase_a": {
            "solvent": "water",
            "additive": "0.1% formic acid",
            "ph_estimate": 3.0
          },
          "mobile_phase_b": {
            "solvent": "acetonitrile",
            "additive": "0.1% formic acid",
            "ph_estimate": null
          },
          "flow_rate_ml_min": 0.35,
          "run_time_min": 9.0,
          "column_temperature_c": 30.0,
          "gradient_profile": [
            {"time_min": 0.0, "percent_b": 5.0},
            {"time_min": 9.0, "percent_b": 95.0}
          ],
          "isocratic_percent_b": null,
          "confidence": 0.92,
          "evidence_unit_ids": ["evu-1", "evu-2"],
          "warnings": []
        }
        """,
    )

    assert parsed is not None
    assert parsed.model_dump(mode="json")["flow_rate_ml_min"] == 0.35


def test_candidate_reranker_prompt_includes_candidate_json_payload() -> None:
    prompt = build_candidate_reranker_prompt(
        request_text="Find a final LC-MS/MS method for carotenoids in plasma",
        analyte_name="carotenoids",
        matrix_hint="human plasma",
        preferred_mode="rp_lc",
        require_mass_spectrometry=True,
        candidates=[
            {
                "paper_id": "paper-1",
                "title": "Validated LC-MS/MS method",
                "abstract": "Validated LC-MS/MS determination in plasma.",
                "published_year": 2020,
                "source_name": "Example Journal",
                "query_provenance": [{"variant_id": "strict_method"}],
            }
        ],
    )

    assert "Screen and rerank these paper candidates for method discovery." in prompt.user_prompt
    assert '"paper_id": "paper-1"' in prompt.user_prompt

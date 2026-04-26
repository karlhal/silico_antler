from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.hplc_extraction_schemas import ExtractedMobilePhaseDetailCandidate
from app.hplc_text_extraction import extract_minimal_hplc
from app.recommendation_runtime import RecommendationRuntimeTracker
from app.recommendation_schemas import MethodRecommendationRequest
from app.retrieval_schemas import EvidenceSnippet, SourceDocumentMetadata
from app.source_document_ingestion import ingest_html_document, ingest_pdf_document
from app.source_document_schemas import SourceDocumentPage, SourceDocumentSection

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_extract_minimal_hplc_returns_structured_method_components() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-001",
            source_type="html",
            url="https://example.test/extract-001",
        ),
        (FIXTURES_DIR / "sample_hplc_extraction_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.source_document.title == "Minimal HPLC Extraction Example"
    assert extraction.chromatography_system is not None
    assert extraction.chromatography_system.mode == "rp_lc"
    assert extraction.chromatography_system.stationary_phase_chemistry == "C18"
    assert extraction.chromatography_system.column_length_mm == 150.0
    assert extraction.chromatography_system.column_inner_diameter_mm == 4.6
    assert extraction.chromatography_system.particle_size_um == 3.0
    assert extraction.method_parameters is not None
    assert "phosphate" in extraction.method_parameters.mobile_phase_a.solvent.lower()
    assert extraction.method_parameters.mobile_phase_a.ph_estimate == 7.2
    assert extraction.method_parameters.mobile_phase_b.solvent == "acetonitrile"
    assert extraction.method_parameters.flow_rate_ml_min == 1.0
    assert extraction.method_parameters.column_temperature_c == 29.5
    assert extraction.method_parameters.run_time_min == 35.0
    assert extraction.method_parameters.gradient_profile[0].percent_b == 10.0
    assert extraction.method_parameters.gradient_profile[-1].percent_b == 10.0
    assert extraction.retention_time_observations[0].local_identifier == "PMP-glucose"
    assert extraction.retention_time_observations[0].observed_retention_time_min == 16.7
    assert extraction.provenance.extraction_mode == "parsed_text"
    assert extraction.provenance.extraction_confidence is not None
    assert extraction.field_evidence
    assert extraction.retrieval_record_ready is False


def test_extract_minimal_hplc_warns_when_required_method_fields_are_missing() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-002",
            source_type="html",
            url="https://example.test/extract-002",
        ),
        (FIXTURES_DIR / "sample_hplc_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.chromatography_system is None
    assert extraction.method_parameters is not None
    assert any("Column geometry" in warning for warning in extraction.warnings)


def test_extract_minimal_hplc_does_not_crash_on_standalone_mobile_phase_detail_candidates(
    monkeypatch,
) -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-002c",
            source_type="html",
            url="https://example.test/extract-002c",
        ),
        (FIXTURES_DIR / "sample_hplc_article.html").read_text(),
    )

    monkeypatch.setattr(
        "app.hplc_text_extraction._extract_mobile_phase_candidates",
        lambda _sources: [],
    )
    monkeypatch.setattr(
        "app.hplc_text_extraction._extract_mobile_phase_detail_candidates",
        lambda _sources: [
            ExtractedMobilePhaseDetailCandidate(
                candidate_kind="phase_detail_statement",
                candidate_role="final",
                target_phase="mobile_phase_a",
                statement_text="Mobile phase A contained 0.1% formic acid.",
                confidence=0.88,
                additive="0.1% formic acid",
                evidence_snippets=[
                    EvidenceSnippet(
                        text="Mobile phase A contained 0.1% formic acid.",
                        page_number=1,
                        section_label="Methods",
                    )
                ],
            )
        ],
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is None
    assert any(
        "Standalone mobile-phase detail statements were detected"
        in warning
        for warning in extraction.warnings
    )


def test_extract_minimal_hplc_uses_targeted_llm_fallback_and_extraction_cache() -> None:
    class _FakeTargetedGeminiClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, bool]] = []

        def extract_targeted_hplc_bundle(
            self,
            *,
            field_group: str,
            request_text: str | None = None,
            context_text: str,
            broadened_context: bool = False,
        ) -> tuple[dict | None, dict, str]:
            assert context_text
            assert request_text
            self.calls.append((field_group, broadened_context))
            payloads = {
                "mobile_phase_gradient": {
                    "mobile_phase_a": {"solvent": "water", "additive": "0.1% formic acid"},
                    "mobile_phase_b": {"solvent": "acetonitrile", "additive": "0.1% formic acid"},
                    "flow_rate_ml_min": 0.35,
                    "run_time_min": 9.0,
                    "gradient_profile": [
                        {"time_min": 0.0, "percent_b": 5.0},
                        {"time_min": 9.0, "percent_b": 95.0},
                    ],
                    "confidence": 0.92,
                    "evidence_unit_ids": ["evu-1", "evu-2"],
                    "warnings": [],
                },
            }
            return (
                payloads.get(field_group),
                {"usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}},
                "openai/gpt-oss-20b",
            )

        def vet_evidence_snippets(self, snippets: list[str]) -> str | None:
            assert snippets
            return "Final evidence quote for the recovered method."

    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-llm-cache-001",
            source_type="html",
            url="https://example.test/extract-llm-cache-001",
            title="LLM recovery example",
        ),
        """
        <html>
          <body>
            <h2>Methods</h2>
            <p>The final chromatographic separation used a Waters XBridge C18 (100 x 2.1 mm, 3.5 um) column.</p>
            <p>The exact mobile-phase composition and runtime were summarized in the validated final method notes.</p>
          </body>
        </html>
        """,
    )
    fake_client = _FakeTargetedGeminiClient()
    tracker = RecommendationRuntimeTracker(
        MethodRecommendationRequest(
            request_text="Recover the final LC-MS/MS method",
            source_mode="local_files",
            local_paths=[],
        ),
        open_access_timeout_sec=20,
        llm_observer_enabled=True,
        rate_limit_policy="5/hour",
        enable_debug_metadata=False,
    )
    tracker.log_start()
    tracker.log_stage("extract_methods", message="Extracting", items_completed=0, items_total=1)

    extraction = extract_minimal_hplc(
        document,
        gemini_client=fake_client,
        runtime_tracker=tracker,
    )

    assert extraction.provenance.extraction_mode == "llm_assisted"
    assert extraction.method_parameters is not None
    assert extraction.method_parameters.mobile_phase_a.solvent == "water"
    assert extraction.method_parameters.flow_rate_ml_min == 0.35
    assert extraction.method_parameters.run_time_min == 9.0
    assert [field_group for field_group, _ in fake_client.calls] == [
        "mobile_phase_gradient",
    ]
    runtime = tracker.success_runtime(
        discovered_count=1,
        candidate_count=1,
        recommended_candidate_id="paper-1",
    )
    assert runtime.telemetry is not None
    assert runtime.telemetry.evidence_unit_count > 0
    assert runtime.telemetry.llm_prompt_tokens > 0
    assert runtime.telemetry.cache.extraction_misses == 1

    second_tracker = RecommendationRuntimeTracker(
        MethodRecommendationRequest(
            request_text="Recover the final LC-MS/MS method",
            source_mode="local_files",
            local_paths=[],
        ),
        open_access_timeout_sec=20,
        llm_observer_enabled=True,
        rate_limit_policy="5/hour",
        enable_debug_metadata=False,
    )
    second_tracker.log_start()
    second_tracker.log_stage(
        "extract_methods",
        message="Extracting",
        items_completed=0,
        items_total=1,
    )
    cached_extraction = extract_minimal_hplc(
        document,
        gemini_client=fake_client,
        runtime_tracker=second_tracker,
    )

    assert cached_extraction.method_parameters is not None
    assert len(fake_client.calls) == 1
    second_runtime = second_tracker.success_runtime(
        discovered_count=1,
        candidate_count=1,
        recommended_candidate_id="paper-1",
    )
    assert second_runtime.telemetry is not None
    assert second_runtime.telemetry.cache.extraction_hits == 1


def test_extract_minimal_hplc_ignores_malformed_single_point_llm_gradients() -> None:
    class _FakeTargetedGeminiClient:
        def extract_targeted_hplc_bundle(
            self,
            *,
            field_group: str,
            request_text: str | None = None,
            context_text: str,
            broadened_context: bool = False,
        ) -> tuple[dict | None, dict, str]:
            del request_text, context_text, broadened_context
            payloads = {
                "mobile_phase_gradient": {
                    "mobile_phase_a": {"solvent": "water", "additive": "0.1% formic acid"},
                    "mobile_phase_b": {"solvent": "acetonitrile"},
                    "flow_rate_ml_min": 0.25,
                    "run_time_min": 6.0,
                    "gradient_profile": [
                        {"time_min": 0.0, "percent_b": 90.0},
                    ],
                    "confidence": 0.82,
                    "evidence_unit_ids": ["evu-1"],
                    "warnings": [],
                },
            }
            return (
                payloads.get(field_group),
                {"usage": {"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110}},
                "openai/gpt-oss-20b",
            )

        def vet_evidence_snippets(self, snippets: list[str]) -> str | None:
            assert snippets
            return snippets[0]

    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-llm-single-gradient-001",
            source_type="html",
            url="https://example.test/extract-llm-single-gradient-001",
            title="Single point gradient recovery example",
        ),
        """
        <html>
          <body>
            <h2>Methods</h2>
            <p>The final chromatographic separation used a Waters XBridge C18 (100 x 2.1 mm, 3.5 um) column.</p>
            <p>Final method details were confirmed in the validated assay summary.</p>
          </body>
        </html>
        """,
    )

    extraction = extract_minimal_hplc(
        document,
        gemini_client=_FakeTargetedGeminiClient(),
    )

    assert extraction.provenance.extraction_mode == "llm_assisted"
    assert extraction.method_parameters is not None
    assert extraction.method_parameters.flow_rate_ml_min == 0.25
    assert extraction.method_parameters.run_time_min == 6.0
    assert extraction.method_parameters.gradient_profile == []
    assert extraction.method_parameters.isocratic_percent_b == 90.0


def test_extract_minimal_hplc_only_uses_full_document_llm_fallback_for_pdfs() -> None:
    class _FakeGeminiClient:
        def __init__(self) -> None:
            self.full_document_calls = 0

        def extract_targeted_hplc_bundle(
            self,
            *,
            field_group: str,
            request_text: str | None = None,
            context_text: str,
            broadened_context: bool = False,
        ) -> tuple[dict | None, dict, str]:
            del field_group, request_text, context_text, broadened_context
            return None, {}, "google/gemma-4-31b-it:free"

        def extract_hplc_parameters(self, text: str) -> dict | None:
            del text
            self.full_document_calls += 1
            return {
                "column_name": "Waters XBridge C18",
                "column_length_mm": 100.0,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
                "mobile_phase_a": {"solvent": "water", "additive": "0.1% formic acid"},
                "mobile_phase_b": {"solvent": "acetonitrile", "additive": None},
                "flow_rate_ml_min": 0.35,
                "run_time_min": 8.0,
                "gradient_profile": [
                    {"time_min": 0.0, "percent_b": 5.0},
                    {"time_min": 8.0, "percent_b": 95.0},
                ],
            }

        def vet_evidence_snippets(self, snippets: list[str]) -> str | None:
            del snippets
            return None

    html_document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-full-doc-gate-001",
            source_type="html",
            url="https://example.test/extract-full-doc-gate-001",
            title="Sparse HTML",
        ),
        """
        <html>
          <body>
            <h2>Results</h2>
            <p>The assay was validated after optimization.</p>
          </body>
        </html>
        """,
    )
    fake_client = _FakeGeminiClient()

    extraction = extract_minimal_hplc(html_document, gemini_client=fake_client)

    assert extraction.provenance.extraction_mode == "parsed_text"
    assert fake_client.full_document_calls == 0

    pdf_document = html_document.model_copy(
        update={
            "source_document": html_document.source_document.model_copy(
                update={"source_type": "pdf"}
            )
        }
    )
    pdf_extraction = extract_minimal_hplc(
        pdf_document,
        gemini_client=fake_client,
        allow_full_document_llm_fallback=True,
    )

    assert fake_client.full_document_calls == 1
    assert pdf_extraction.provenance.extraction_mode == "llm_assisted"


def test_extract_minimal_hplc_prefers_provider_pdf_reader_before_text_fallback() -> None:
    class _FakePdfReaderClient:
        def __init__(self) -> None:
            self.pdf_calls = 0
            self.text_calls = 0

        def extract_hplc_parameters_from_pdf(
            self,
            *,
            pdf_bytes: bytes,
            filename: str,
            pdf_url: str | None = None,
            request_text: str | None = None,
            title: str | None = None,
        ) -> dict | None:
            assert pdf_bytes == b"%PDF-1.7\n%%EOF"
            assert filename == "provider-reader.pdf"
            assert pdf_url == "https://example.test/provider-reader.pdf"
            assert request_text
            assert title == "Provider PDF Reader"
            self.pdf_calls += 1
            return {
                "chromatography_mode": "rp_lc",
                "column_name": "Waters XBridge C18",
                "column_length_mm": 100.0,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
                "mobile_phase_a": {
                    "solvent": "water",
                    "additive": "0.1% formic acid",
                },
                "mobile_phase_b": {
                    "solvent": "acetonitrile",
                    "additive": "0.1% formic acid",
                },
                "flow_rate_ml_min": 0.35,
                "run_time_min": 9.0,
                "gradient_profile": [
                    {"time_min": 0.0, "percent_b": 5.0},
                    {"time_min": 9.0, "percent_b": 95.0},
                ],
                "evidence_quote": "Final chromatographic conditions used XBridge C18 with 0.35 mL/min flow.",
            }

        def extract_hplc_parameters(self, text: str) -> dict | None:
            del text
            self.text_calls += 1
            return None

    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-provider-pdf-reader-001",
            source_type="html",
            title="Provider PDF Reader",
            file_name="provider-reader.pdf",
            url="https://example.test/provider-reader.pdf",
        ),
        """
        <html><body><h2>Results</h2><p>The assay was validated.</p></body></html>
        """,
    ).model_copy(
        update={
            "source_document": SourceDocumentMetadata(
                source_document_id="extract-provider-pdf-reader-001",
                source_type="pdf",
                title="Provider PDF Reader",
                file_name="provider-reader.pdf",
                url="https://example.test/provider-reader.pdf",
            )
        }
    )
    fake_client = _FakePdfReaderClient()

    extraction = extract_minimal_hplc(
        document,
        request_text="Extract the final LC-MS/MS method.",
        gemini_client=fake_client,
        allow_full_document_llm_fallback=True,
        source_pdf_bytes=b"%PDF-1.7\n%%EOF",
        source_pdf_url="https://example.test/provider-reader.pdf",
    )

    assert fake_client.pdf_calls == 1
    assert fake_client.text_calls == 0
    assert extraction.provenance.extraction_mode == "llm_assisted"
    assert extraction.method_parameters is not None
    assert extraction.method_parameters.flow_rate_ml_min == 0.35
    assert any("OpenRouter PDF parser" in warning for warning in extraction.warnings)


def test_extract_minimal_hplc_uses_local_markdown_reader_when_pdf_parser_has_no_gain(
    monkeypatch,
) -> None:
    class _FakeMarkdownClient:
        def __init__(self) -> None:
            self.pdf_calls = 0
            self.markdown_calls = 0
            self.text_calls = 0

        def extract_hplc_parameters_from_pdf(self, **_: object) -> dict | None:
            self.pdf_calls += 1
            return None

        def extract_hplc_parameters_from_markdown(
            self,
            markdown_text: str,
            *,
            request_text: str | None = None,
            title: str | None = None,
        ) -> dict | None:
            assert "Waters XBridge C18" in markdown_text
            assert request_text
            assert title == "Local Markdown Reader"
            self.markdown_calls += 1
            return {
                "chromatography_mode": "rp_lc",
                "column_name": "Waters XBridge C18",
                "column_length_mm": 100.0,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
                "mobile_phase_a": {"solvent": "water", "additive": "0.1% formic acid"},
                "mobile_phase_b": {"solvent": "acetonitrile", "additive": None},
                "flow_rate_ml_min": 0.35,
                "run_time_min": 9.0,
                "gradient_profile": [
                    {"time_min": 0.0, "percent_b": 5.0},
                    {"time_min": 9.0, "percent_b": 95.0},
                ],
            }

        def extract_hplc_parameters(self, text: str) -> dict | None:
            del text
            self.text_calls += 1
            return None

    pdf_bytes = _build_simple_pdf(
        [
            "Final chromatography used a Waters XBridge C18 column.",
            "Mobile phase A was water with 0.1% formic acid.",
            "Mobile phase B was acetonitrile.",
            "The flow rate was 0.35 mL/min.",
        ]
    )
    document = ingest_pdf_document(
        SourceDocumentMetadata(
            source_document_id="extract-local-markdown-reader-001",
            source_type="pdf",
            title="Local Markdown Reader",
            file_name="local-markdown-reader.pdf",
        ),
        pdf_bytes,
    ).model_copy(
        update={
            "raw_text": "Validated sparse method note.",
            "pages": [
                SourceDocumentPage(page_number=1, text="Validated sparse method note.")
            ],
            "sections": [
                SourceDocumentSection(
                    section_id="sparse-1",
                    label="Results",
                    normalized_label="results",
                    start_page_number=1,
                    end_page_number=1,
                    text="Validated sparse method note.",
                )
            ],
        }
    )
    fake_client = _FakeMarkdownClient()

    extraction = extract_minimal_hplc(
        document,
        request_text="Extract the final LC-MS/MS method.",
        gemini_client=fake_client,
        allow_full_document_llm_fallback=True,
        source_pdf_bytes=pdf_bytes,
    )

    assert fake_client.pdf_calls == 1
    assert fake_client.markdown_calls == 1
    assert fake_client.text_calls == 0
    assert extraction.method_parameters is not None
    assert extraction.method_parameters.flow_rate_ml_min == 0.35
    assert any("PyMuPDF4LLM" in warning for warning in extraction.warnings)


def test_extract_minimal_hplc_truncates_overlong_mobile_phase_statement_text() -> None:
    long_tail = " detailed optimization note" * 140
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-002b",
            source_type="html",
            url="https://example.test/extract-002b",
        ),
        f"""
        <html>
          <head><title>Long Mobile Phase Statement</title></head>
          <body>
            <h2>Methods</h2>
            <p>Waters XBridge C18 (150 x 4.6 mm, 3 um)</p>
            <p>Mobile phase A: water{long_tail} Mobile phase B: acetonitrile.</p>
            <p>The flow rate was 1.0 mL/min.</p>
            <p>Runtime was 12 min.</p>
          </body>
        </html>
        """,
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.mobile_phase_candidates
    assert all(len(candidate.statement_text) <= 2000 for candidate in extraction.mobile_phase_candidates)


def test_extract_minimal_hplc_keeps_alternative_solvent_notes_out_of_final_method() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-003",
            source_type="html",
            url="https://example.test/extract-003",
        ),
        (FIXTURES_DIR / "sample_hplc_alternative_solvents_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    assert extraction.method_parameters.mobile_phase_a.solvent == "water"
    assert extraction.method_parameters.mobile_phase_b.solvent == "methanol"
    selected_candidates = [
        candidate
        for candidate in extraction.mobile_phase_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0].candidate_kind == "full_system"
    assert selected_candidates[0].candidate_role == "final"
    replacement_candidates = [
        candidate
        for candidate in extraction.mobile_phase_candidates
        if candidate.candidate_kind == "replacement_note"
    ]
    assert len(replacement_candidates) == 1
    assert replacement_candidates[0].candidate_role == "trial"
    assert replacement_candidates[0].comparison_from_text == "acetonitrile"
    assert replacement_candidates[0].comparison_to_text == "phosphate buffer"


def test_extract_minimal_hplc_prefers_final_text_gradient_over_optimization_table() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-004",
            source_type="html",
            url="https://example.test/extract-004",
        ),
        (FIXTURES_DIR / "sample_hplc_gradient_candidates_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    assert len(extraction.method_parameters.gradient_profile) == 4
    assert extraction.method_parameters.gradient_profile[0].percent_b == 10.0
    assert extraction.method_parameters.gradient_profile[-1].percent_b == 10.0
    selected_candidates = [
        candidate
        for candidate in extraction.gradient_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0].candidate_kind == "text_statement"
    assert selected_candidates[0].candidate_role == "final"
    table_candidates = [
        candidate
        for candidate in extraction.gradient_candidates
        if candidate.candidate_kind == "table_derived"
    ]
    assert len(table_candidates) == 1
    assert table_candidates[0].candidate_role == "trial"


def test_extract_minimal_hplc_can_use_table_derived_gradient_when_text_is_absent() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-005",
            source_type="html",
            url="https://example.test/extract-005",
        ),
        (FIXTURES_DIR / "sample_hplc_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    assert extraction.method_parameters.gradient_profile[0].time_min == 0.0
    assert extraction.method_parameters.gradient_profile[0].percent_b == 5.0
    assert extraction.method_parameters.gradient_profile[1].time_min == 10.0
    assert extraction.method_parameters.gradient_profile[1].percent_b == 95.0
    selected_candidates = [
        candidate
        for candidate in extraction.gradient_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0].candidate_kind == "table_derived"


def test_extract_minimal_hplc_selects_final_column_and_retention_candidates() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-006",
            source_type="html",
            url="https://example.test/extract-006",
        ),
        (FIXTURES_DIR / "sample_hplc_candidate_selection_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.chromatography_system is not None
    assert extraction.chromatography_system.column_name == "YMC-Pack ODS-AQ"
    system_candidates = extraction.chromatography_system_candidates
    assert len(system_candidates) == 2
    assert len([c for c in system_candidates if c.selected_for_output]) == 1
    assert system_candidates[0].candidate_role == "final"
    assert any(candidate.candidate_role == "trial" for candidate in system_candidates)
    assert len(extraction.retention_time_observations) == 2
    selected_observations = [
        observation
        for observation in extraction.retention_time_observations
        if observation.selected_for_record_draft
    ]
    assert len(selected_observations) == 1
    assert selected_observations[0].local_identifier == "PMP-glucose"
    assert selected_observations[0].observed_retention_time_min == 16.7
    assert extraction.record_draft is not None
    assert extraction.record_draft.record_id == "draft-extract-006"
    assert (
        extraction.record_draft.selected_retention_time_observations[0].local_identifier
        == "PMP-glucose"
    )
    assert extraction.record_draft.ready_for_record_assembly is False
    assert any(
        "molecular entity anchoring" in item
        for item in extraction.record_draft.unresolved_requirements
    )


def test_extract_minimal_hplc_enriches_mobile_phase_details_and_timing_candidates() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-007",
            source_type="html",
            url="https://example.test/extract-007",
        ),
        (FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    assert extraction.method_parameters.mobile_phase_a.solvent == "water"
    assert extraction.method_parameters.mobile_phase_a.additive == "0.1% formic acid"
    assert extraction.method_parameters.mobile_phase_a.ph_estimate == 3.2
    assert extraction.method_parameters.run_time_min == 12.0
    selected_detail_candidates = [
        candidate
        for candidate in extraction.mobile_phase_detail_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_detail_candidates) == 1
    assert selected_detail_candidates[0].candidate_role == "final"
    assert selected_detail_candidates[0].target_phase == "mobile_phase_a"
    selected_timing_candidates = [
        candidate
        for candidate in extraction.timing_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_timing_candidates) == 1
    assert selected_timing_candidates[0].candidate_kind == "run_time_statement"
    assert selected_timing_candidates[0].run_time_min == 12.0
    assert any(
        candidate.candidate_kind == "gradient_derived"
        and candidate.reequilibration_time_min == 2.0
        for candidate in extraction.timing_candidates
    )


def test_extract_minimal_hplc_builds_anchored_entity_candidates_for_local_identifiers() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-008",
            source_type="html",
            url="https://example.test/extract-008",
        ),
        (FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert len(extraction.anchored_entity_candidates) == 2
    selected_entities = [
        candidate
        for candidate in extraction.anchored_entity_candidates
        if candidate.selected_for_record_draft
    ]
    assert len(selected_entities) == 1
    assert selected_entities[0].local_identifier == "intermediate 2"
    assert selected_entities[0].observed_retention_time_min == 7.4
    assert extraction.record_draft is not None
    assert (
        extraction.record_draft.anchored_entities[0].local_identifier
        == "intermediate 2"
    )


def test_extract_minimal_hplc_collapses_aliases_into_molecular_entity_drafts() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-009",
            source_type="html",
            url="https://example.test/extract-009",
        ),
        (FIXTURES_DIR / "sample_hplc_alias_resolution_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.record_draft is not None
    drafts = extraction.record_draft.molecular_entity_drafts
    assert len(drafts) == 2
    compound_draft = next(draft for draft in drafts if draft.local_identifier == "4a")
    assert set(alias.lower() for alias in compound_draft.aliases) >= {
        "compound 4a",
        "4a",
        "target compound",
        "desired isomer",
        "main peak",
    }
    assert compound_draft.placeholder_smiles_string == "UNRESOLVED::4a"
    assert compound_draft.smiles_linkage_status == "unresolved_local_identifier"
    assert set(compound_draft.linkage_lookup_keys) >= {"4a", "compound 4a"}
    assert any(
        "generic co-reference aliases" in note for note in compound_draft.linkage_notes
    )
    named_draft = next(
        draft
        for draft in drafts
        if draft.local_identifier in {"PMP glucose", "PMP-glucose"}
    )
    assert set(alias.lower() for alias in named_draft.aliases) >= {
        "pmp glucose",
        "pmp-glucose",
    }
    assert named_draft.smiles_linkage_status == "unresolved_named_entity"
    assert set(named_draft.linkage_lookup_keys) >= {"pmp glucose", "pmp-glucose"}


def test_extract_minimal_hplc_attaches_validation_to_reasonable_draft() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-010",
            source_type="html",
            url="https://example.test/extract-010",
        ),
        (FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.record_draft is not None
    assert extraction.record_draft.validation.status == "needs_review"
    assert extraction.record_draft.validation.retrieval_ready is False
    assert not any(
        issue.severity == "error" for issue in extraction.record_draft.validation.issues
    )
    assert any(
        issue.code == "molecular_entity_unresolved"
        for issue in extraction.record_draft.validation.issues
    )


def test_extract_minimal_hplc_invalidates_implausible_record_geometry_and_ph() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-011",
            source_type="html",
            url="https://example.test/extract-011",
        ),
        (FIXTURES_DIR / "sample_hplc_invalid_validation_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.record_draft is not None
    assert extraction.record_draft.validation.status == "invalid"
    issue_codes = {issue.code for issue in extraction.record_draft.validation.issues}
    assert "flow_rate_high_for_narrow_column" in issue_codes
    assert "ph_outside_stationary_phase_range" in issue_codes


def test_extract_minimal_hplc_keeps_generic_alias_as_unresolved_placeholder() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-012",
            source_type="html",
            url="https://example.test/extract-012",
        ),
        (FIXTURES_DIR / "sample_hplc_generic_alias_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.record_draft is not None
    drafts = extraction.record_draft.molecular_entity_drafts
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.local_identifier == "main peak"
    assert draft.smiles_linkage_status == "placeholder_generated"
    assert draft.placeholder_smiles_string == "UNRESOLVED::main-peak"
    issue_codes = {issue.code for issue in extraction.record_draft.validation.issues}
    assert "generic_anchor_unresolved" in issue_codes


def test_extract_minimal_hplc_can_parse_retention_observations_from_table_text() -> (
    None
):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-013",
            source_type="html",
            url="https://example.test/extract-013",
        ),
        (FIXTURES_DIR / "sample_hplc_retention_table_article.html").read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.record_draft is not None
    observed_pairs = {
        (item.local_identifier, item.observed_retention_time_min)
        for item in extraction.retention_time_observations
    }
    assert ("Intermediate 2", 7.4) in observed_pairs
    assert ("Impurity A", 3.1) in observed_pairs
    assert any(
        item.selected_for_record_draft and item.local_identifier == "Intermediate 2"
        for item in extraction.retention_time_observations
    )
    assert any(
        candidate.local_identifier == "Intermediate 2"
        for candidate in extraction.anchored_entity_candidates
    )
    assert any(
        evidence.snippet.section_label == "Results and Discussion"
        and "Table 2. Retention time summary." in evidence.snippet.text
        for evidence in extraction.field_evidence
        if evidence.field_path == "retention_time_observations"
    )


def test_extract_minimal_hplc_can_parse_multicolumn_gradient_table() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-014",
            source_type="html",
            url="https://example.test/extract-014",
        ),
        (
            FIXTURES_DIR / "sample_hplc_multicolumn_gradient_table_article.html"
        ).read_text(),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    assert [
        (point.time_min, point.percent_b)
        for point in extraction.method_parameters.gradient_profile
    ] == [(0.0, 5.0), (8.0, 40.0), (12.0, 95.0)]
    selected_candidates = [
        candidate
        for candidate in extraction.gradient_candidates
        if candidate.selected_for_method_parameters
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0].candidate_kind == "table_derived"
    assert selected_candidates[0].candidate_role == "final"
    assert extraction.method_parameters.run_time_min == 12.0


def test_extract_minimal_hplc_can_parse_generic_mobile_phase_pair_sentence() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-015",
            source_type="html",
            url="https://example.test/extract-015",
        ),
        """
        <html>
          <body>
            <section>
              <h2>Materials and Methods</h2>
              <p>The column used was a YMC-Pack ODS-AQ (150 x 4.6 mm, 3 um).</p>
              <p>The selected method used a mobile phase consisting of 15 mM potassium phosphate dibasic pH 7.2 and ACN.</p>
              <p>The flow rate was 1.0 mL/min.</p>
              <p>Column temperature was 29.5 C.</p>
              <p>Run time was 35 min.</p>
            </section>
          </body>
        </html>
        """,
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.chromatography_system is not None
    assert extraction.method_parameters is not None
    assert "phosphate" in extraction.method_parameters.mobile_phase_a.solvent.lower()
    assert extraction.method_parameters.mobile_phase_a.ph_estimate == 7.2
    assert extraction.method_parameters.mobile_phase_b.solvent == "acetonitrile"


def test_extract_minimal_hplc_can_parse_retention_table_with_extra_columns() -> None:
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-016",
            source_type="html",
            url="https://example.test/extract-016",
        ),
        """
        <html>
          <body>
            <section>
              <h2>Chromatographic Conditions</h2>
              <p>The column used was a YMC Carotenoid S-5 um, 250 x 4.6 mm.</p>
              <p>Mobile phase A consisted of methanol with 0.7 g/L ammonium acetate and 0.1% acetic acid.</p>
              <p>Mobile phase B contained MTBE and methanol (80:20, v/v) with 0.7 g/L ammonium acetate and 0.1% acetic acid.</p>
              <p>The mobile phase flow rate was 600 uL/min.</p>
              <p>The total run time of analysis was 50 min.</p>
              <table>
                <caption>Table 2. Retention time summary.</caption>
                <tr><th>Analyte</th><th>Rt (min)</th><th>DP (V)</th><th>Transition</th></tr>
                <tr><td>retinol</td><td>5.00</td><td>35</td><td>269 -> 181</td></tr>
                <tr><td>retinol acetate</td><td>7.34</td><td>41</td><td>329 -> 269</td></tr>
                <tr><td>beta-carotene</td><td>27.42</td><td>85</td><td>537 -> 413</td></tr>
              </table>
            </section>
          </body>
        </html>
        """,
    )

    extraction = extract_minimal_hplc(document)

    observed_pairs = {
        (item.local_identifier, item.observed_retention_time_min)
        for item in extraction.retention_time_observations
    }
    assert ("retinol", 5.0) in observed_pairs
    assert ("retinol acetate", 7.34) in observed_pairs
    assert ("beta-carotene", 27.42) in observed_pairs


def test_extract_minimal_hplc_uses_plos_style_pdf_sections_for_evidence_and_page_traceability() -> (
    None
):
    document = ingest_pdf_document(
        SourceDocumentMetadata(
            source_document_id="extract-pdf-001",
            source_type="pdf",
            file_name="plos-style-extraction.pdf",
        ),
        _build_simple_pdf(
            [
                "PLOS ONE",
                "RESEARCHARTICLE",
                "Development of a RP-HPLC method for determination of glucose",
                "a1111111111 Abstract A compact abstract example.",
                "Materialsandmethods Waters XBridge C18 (150 x 4.6 mm, 3 um)",
                "Mobile phase A: phosphate buffer (pH 7.2)",
                "Mobile phase B: acetonitrile",
                "The flow rate was 1.0 mL/min.",
                "Column temperature was 29.5 C.",
                "Runtime was 35 min.",
                "Resultsanddiscussion The PMP-glucose peak had a retention time of 16.7 min.",
                "Gradient 10 to 64% B over 30 min, hold 5 min, return to initial over 1 min.",
            ]
        ),
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.chromatography_system is not None
    assert extraction.chromatography_system.column_name == "Waters XBridge C18"
    assert extraction.method_parameters is not None
    assert extraction.method_parameters.mobile_phase_a.solvent == "phosphate buffer"
    assert extraction.method_parameters.mobile_phase_b.solvent == "acetonitrile"
    assert extraction.method_parameters.flow_rate_ml_min == 1.0
    assert extraction.method_parameters.run_time_min == 35.0
    assert extraction.retention_time_observations[0].local_identifier == "PMP-glucose"
    assert extraction.retention_time_observations[0].observed_retention_time_min == 16.7
    assert extraction.provenance.source_pages == [1]
    assert any(
        item.snippet.section_label == "Materials and Methods"
        and item.snippet.page_number == 1
        for item in extraction.field_evidence
        if item.field_path.startswith("method_parameters")
        or item.field_path == "chromatography_system"
    )
    assert any(
        snippet.section_label == "Results and Discussion"
        for snippet in extraction.provenance.evidence_snippets
    )


def test_extract_minimal_hplc_truncates_overlong_section_labels_in_evidence() -> None:
    long_heading = "Development, characterization, and skin delivery studies of related ultradeformable vesicles: transfersomes, ethosomes, and transethosomes"
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id="extract-long-section-001",
            source_type="html",
            url="https://example.test/extract-long-section-001",
        ),
        f"""
        <html>
          <head><title>Long Section Heading Example</title></head>
          <body>
            <h2>{long_heading}</h2>
            <p>Waters XBridge C18 (150 x 4.6 mm, 3 um)</p>
            <p>Mobile phase A: phosphate buffer (pH 7.2)</p>
            <p>Mobile phase B: acetonitrile</p>
            <p>The flow rate was 1.0 mL/min.</p>
            <p>Runtime was 18 min.</p>
          </body>
        </html>
        """,
    )

    extraction = extract_minimal_hplc(document)

    assert extraction.method_parameters is not None
    section_labels = [
        snippet.section_label
        for snippet in extraction.provenance.evidence_snippets
        if snippet.section_label is not None
    ]
    assert section_labels
    assert all(len(label) <= 120 for label in section_labels)


def _build_simple_pdf(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        escaped_line = (
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        if index > 0:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({escaped_line}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]

    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{index} 0 obj\n".encode("ascii"))
        parts.append(obj)
        parts.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in parts)
    parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    parts.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        parts.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    parts.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode(
            "ascii"
        )
    )
    return b"".join(parts)

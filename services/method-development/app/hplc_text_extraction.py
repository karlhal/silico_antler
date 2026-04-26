from __future__ import annotations

import json
from hashlib import sha256
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .gemini_orchestration_client import GeminiOrchestrationClient
    from .recommendation_runtime import RecommendationRuntimeTracker

from .hplc_extraction_schemas import (
    AnchoredEntityCandidate,
    ExtractedChromatographySystemCandidate,
    ExtractedFieldEvidence,
    ExtractedGradientCandidate,
    ExtractedMobilePhaseDetailCandidate,
    ExtractedMobilePhaseCandidate,
    ExtractedRetentionTimeObservation,
    ExtractedTimingCandidate,
    HplcMolecularEntityDraft,
    MinimalHplcExtractionResponse,
    MobilePhaseDetailTarget,
    MobilePhaseCandidateRole,
    RetrievalRecordDraft,
    SmilesLinkageStatus,
)
from .hplc_record_validation import validate_record_draft
from .recommendation_context_optimizer import (
    EvidenceUnit,
    build_document_cache_key,
    build_extraction_cache_key,
    build_vetted_snippet_cache_key,
    extraction_cache_lookup,
    get_evidence_units,
    select_evidence_units,
    store_extraction_cache,
    store_vetted_snippet_cache,
    usage_from_response,
    vetted_snippet_cache_lookup,
)
from .retrieval_schemas import (
    ChromatographyMode,
    ChromatographySystem,
    EvidenceSnippet,
    GradientPoint,
    MethodParameters,
    MobilePhase,
    RetrievalProvenance,
)
from .source_document_schemas import RegisteredSourceDocument, SourceDocumentSection

FLOW_RATE_PATTERN = re.compile(
    r"(?:flow\s*rate(?:\s+was|\s+of|\s*=)?|mobile\s+phase\s+flow\s+rate\s+was|delivered\s+at\s+a\s+flow\s+rate\s+of)\s*(?:(?![0-9]).){0,50}?(?P<value>\d+(?:[.,]\d+)?)\s*(?:of\s+)?(?P<unit>[muµ]?L|mL)\s*[/\\|\s]*min(?:[-−^]*1)?",
    re.IGNORECASE,
)
TEMPERATURE_PATTERN = re.compile(
    r"(?:column\s*temperature(?:\s+was|\s+of|\s*=)?|thermostated\s+at|maintained\s+at)\s*(?:(?![0-9]).){0,50}?(?P<value>\d+(?:[.,]\d+)?)\s*(?:°|˚|◦)?\s*C",
    re.IGNORECASE,
)
RUN_TIME_PATTERN = re.compile(
    r"(?:(?:total\s+)?run\s*time(?:\s+of\s+analysis)?(?:\s+was|\s+of|\s*=)?|runtime(?:\s+was|\s+of|\s*=)?|separation\s+of\s+\d+\s+analytes\s+in)\s*(?:(?![0-9]).){0,50}?(?P<value>\d+(?:[.,]\d+)?)\s*min",
    re.IGNORECASE,
)
COLUMN_COMPACT_PATTERN = re.compile(
    r"(?P<column>[A-Za-z0-9][A-Za-z0-9\- /]+?)\s*\(\s*(?P<length>\d+(?:\.\d+)?)\s*[x×]\s*(?P<diameter>\d+(?:\.\d+)?)\s*mm\s*,\s*(?P<particle>\d+(?:\.\d+)?)\s*(?:μm|um|microns?|micron)\s*\)",
    re.IGNORECASE,
)
COLUMN_PARTICLE_FIRST_PATTERN = re.compile(
    r"(?P<column>[A-Za-z0-9][A-Za-z0-9\- /]+?)\s*[S-]?(?P<particle>\d+(?:\.\d+)?)\s*(?:μm|um|microns?|micron)\s*,\s*(?P<length>\d+(?:\.\d+)?)\s*[x×]\s*(?P<diameter>\d+(?:\.\d+)?)\s*mm",
    re.IGNORECASE,
)
COLUMN_VERBOSE_PATTERN = re.compile(
    r"(?:column\s*used\s*was|column\s*was|using\s+an?|using\s+the|on\s+an?|on\s+the)?\s*(?P<column>[A-Za-z0-9][A-Za-z0-9\- /]+?)\s*(?:with\s*a\s*column\s*length\s*of|column\s*length\s*of)\s*(?P<length>\d+(?:\.\d+)?)\s*mm\s*,\s*(?:an\s*)?(?:inside|inner)\s*diameter\s*of\s*(?P<diameter>\d+(?:\.\d+)?)\s*mm\s*(?:,?\s*and\s*)?(?:a\s*)?particle\s*size\s*of\s*(?P<particle>\d+(?:\.\d+)?)\s*(?:μm|um|microns?|micron)",
    re.IGNORECASE,
)
ELUENT_A_PATTERN = re.compile(
    r"(?:eluent|mobile\s*phase|solvent|phase)\s*A\s*(?::|=|consisted\s+of|contained|was)\s*(?P<value>.*?)(?=(?:eluent|mobile\s*phase|solvent|phase)\s*B\s*(?::|=|consisted\s+of|contained|was)|(?!(?:eluent|mobile\s*phase|solvent|phase)\s*A)(?:(?:the\s+)?(?:mobile\s+phase\s+flow\s*rate|flow\s*rate|column\s*temperature|run\s*time|gradient|retention\s*time|injection\s+volume|the\s+linear\s+gradient|analytical\s+procedure))|$)",
    re.IGNORECASE | re.DOTALL,
)
ELUENT_B_PATTERN = re.compile(
    r"(?:eluent|mobile\s*phase|solvent|phase)\s*B\s*(?::|=|consisted\s+of|contained|was)\s*(?P<value>.*?)(?=(?:(?:the\s+)?(?:mobile\s+phase\s+flow\s*rate|flow\s*rate|column\s*temperature|temperature|run\s*time|gradient|retention\s*time|injection\s+volume|the\s+linear\s+gradient|analytical\s+procedure))|$)",
    re.IGNORECASE | re.DOTALL,
)
MOBILE_PHASE_PAIR_PATTERN = re.compile(
    r"mobile\s*phase(?:\s+consisted\s+of|\s+consisting\s+of|\s+of)?\s*(?P<a>water(?:\s+with\s+[^.;\n]+)?|aqueous[^.;\n]*|[^.;\n]*(?:buffer|phosphate)[^.;\n]*)\s*(?:\(A\))?\s*(?:and|,)\s*(?P<b>acetonitrile|ACN|methanol|MeOH|2-propanol|isopropanol|MTBE)(?:\s*\(B\))?",
    re.IGNORECASE,
)
GENERIC_MOBILE_PHASE_PAIR_PATTERN = re.compile(
    r"(?:using\s+(?:a|the)\s+)?mobile\s*phase(?:\s+consisting\s+of|\s+consisted\s+of|\s+of)?\s*(?P<a>[^.;\n]*?(?:buffer|phosphate)[^.;\n]*?)\s+(?:and|,)\s+(?P<b>acetonitrile|ACN|methanol|MeOH|2-propanol|isopropanol|MTBE)\b",
    re.IGNORECASE,
)
ISOCRATIC_PREMIX_PATTERN = re.compile(
    r"mobile\s*phase(?:\s+consisted\s+of|\s+consisting\s+of|\s+of)?\s*(?P<mix>(?:acetonitrile|ACN|methanol|MeOH|water|aqueous|buffer|phosphate|dichloromethane|DCM|hexane|isopropanol|2-propanol)(?:\s*[:/]\s*(?:acetonitrile|ACN|methanol|MeOH|water|aqueous|buffer|phosphate|dichloromethane|DCM|hexane|isopropanol|2-propanol)){1,3})\s*(?:\(\s*(?P<ratios>\d+(?:\s*[:/]\s*\d+){1,3})\s*(?:v/v/v|v/v|v)?\s*\))?",
    re.IGNORECASE,
)
SOLVENT_PAIR_PATTERN = re.compile(
    r"column\s+with\s+(?P<a>water(?:\s+with\s+[^.;\n]+)?|aqueous[^.;\n]*|[^.;\n]*buffer[^.;\n]*)\s+and\s+(?P<b>acetonitrile|ACN|methanol|MeOH|2-propanol|isopropanol)",
    re.IGNORECASE,
)
GRADIENT_PATTERN = re.compile(
    r"(?P<start>\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(?P<end>\d+(?:\.\d+)?)\s*%\s*B\s*over\s*(?P<ramp>\d+(?:\.\d+)?)\s*min(?:utes?)?(?:,?\s*hold\s*(?P<hold>\d+(?:\.\d+)?)\s*min(?:utes?)?)?(?:,?\s*return\s*to\s*initial\s*over\s*(?P<reequil>\d+(?:\.\d+)?)\s*min(?:utes?)?)?",
    re.IGNORECASE,
)
VERBOSE_GRADIENT_PATTERN = re.compile(
    r"(?:linear\s+)?gradient(?:.*?consisted\s+of)?(?P<steps>(?:\s*\d+(?:\.\d+)?\s*(?:%|percent)\s*(?:of\s+)?(?:solvent|phase|eluent)?\s*B\s*(?:for|over)\s*\d+(?:\.\d+)?\s*min(?:ute)?s?(?:,\s*(?:then|followed\s+by))?)+)",
    re.IGNORECASE | re.DOTALL,
)
TABLE_NUMERIC_VALUE_PATTERN = re.compile(r"\d+(?:\.\d+)?")
TABLE_RETENTION_VALUE_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
RETENTION_TIME_PATTERN = re.compile(
    r"retention\s*time(?:s)?(?:\s*of|\s*was|\s*=|\s*were)?\s*(?P<value>\d+(?:\.\d+)?)\s*min",
    re.IGNORECASE,
)
PEAK_TIME_PATTERN = re.compile(
    r"\b(?P<label>[A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+){0,3})\s+peak\b[^.]{0,80}?\bat\s+(?P<value>\d+(?:\.\d+)?)\s*min",
    re.IGNORECASE,
)
PH_PATTERN = re.compile(r"pH\s*(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE)
ADDITIVE_PATTERN = re.compile(
    r"(?P<additive>(?:\d+(?:\.\d+)?\s*g/L\s*)?(?:ammonium\s+acetate|AMAC)(?:\s*(?:\+|and)\s*\d+(?:\.\d+)?%\s*(?:of\s+)?acetic\s+acid)?|\d+(?:\.\d+)?%\s*(?:of\s+)?(?:acetic\s+acid|formic\s+acid)|formic\s+acid|acetic\s+acid|diethylamine|ammonium\s+acetate)",
    re.IGNORECASE,
)
SOLVENT_REFERENCE_PATTERN = r"methyl\s+tert-?butyl\s+ether|MTBE|acetonitrile|ACN|methanol|MeOH|2-propanol|isopropanol|phosphate\s+buffer|buffer|water|aqueous(?:\s+buffer)?"
SOLVENT_REPLACEMENT_PATTERN = re.compile(
    rf"instead\s+of\s+(?P<from>{SOLVENT_REFERENCE_PATTERN})[^.!?;]{{0,80}}?(?:use|used|using|selected|chose|chosen|was\s+used|test|tested|testing|evaluated|screened)\s+(?P<to>{SOLVENT_REFERENCE_PATTERN})",
    re.IGNORECASE,
)
SOLVENT_REPLACED_WITH_PATTERN = re.compile(
    rf"(?:replace|replaced|replacing|substituted)\s+(?P<from>{SOLVENT_REFERENCE_PATTERN})\s+with\s+(?P<to>{SOLVENT_REFERENCE_PATTERN})",
    re.IGNORECASE,
)
FINAL_METHOD_CUES = (
    "final method",
    "selected method",
    "optimized method",
    "optimal method parameters",
    "optimal chromatographic conditions",
    "selected conditions",
    "final chromatographic conditions",
    "the method used",
    "chosen mobile phase",
    "under the selected method",
    "final data acquisition",
    "final composition",
    "selected eluent",
    "the analytical conditions",
    "chosen for the final",
    "was chosen for final",
    "was selected",
    "were selected",
    "the following combination of mobile phases was used",
    "the following linear gradient",
    "for chromatographic separation",
    )

TRIAL_METHOD_CUES = (
    "tested",
    "was tested",
    "were tested",
    "screened",
    "screening",
    "evaluated",
    "examined",
    "compared",
    "during optimization",
    "optimization",
    "preliminary experiments",
    "various optimization experiments",
    "during the infusion experiments",
    "trial",
)
COMPARISON_CUES = (
    "instead of",
    "rather than",
    "replaced",
    "replacing",
    "substituted",
    "switched from",
)
REJECTION_CUES = (
    "not used",
    "was not used",
    "did not use",
    "rejected",
    "discarded",
    "unsuitable",
)


@dataclass(frozen=True)
class _TextSource:
    text: str
    section_label: str | None
    section_kind: str | None
    page_number: int | None
    priority: float

    @property
    def cleaned_text(self) -> str:
        return _clean_text(self.text)


from rich import print as rprint


def extract_minimal_hplc(
    document: RegisteredSourceDocument,
    *,
    request_text: str | None = None,
    gemini_client: GeminiOrchestrationClient | None = None,
    runtime_tracker: RecommendationRuntimeTracker | None = None,
    allow_full_document_llm_fallback: bool = True,
    source_pdf_bytes: bytes | None = None,
    source_pdf_url: str | None = None,
) -> MinimalHplcExtractionResponse:
    rprint(
        f"[bold blue]Extraction: {document.source_document.title or 'Unknown'}[/bold blue] "
        f"(Client: {gemini_client is not None})"
    )
    extraction_cache_key = build_extraction_cache_key(
        document,
        llm_cache_key=_llm_cache_key(gemini_client, request_text=request_text),
    )
    cached_extraction = extraction_cache_lookup(
        extraction_cache_key, MinimalHplcExtractionResponse
    )
    if cached_extraction is not None:
        if runtime_tracker is not None:
            runtime_tracker.note_cache_event(
                "extract_methods",
                cache_name="extraction",
                hit=True,
            )
        return cached_extraction
    if runtime_tracker is not None:
        runtime_tracker.note_cache_event(
            "extract_methods",
            cache_name="extraction",
            hit=False,
        )
    evidence_units, evidence_cache_hit = get_evidence_units(document)
    if runtime_tracker is not None:
        runtime_tracker.note_evidence_units(
            "extract_methods",
            count=len(evidence_units),
            cache_hit=evidence_cache_hit,
        )
    sources = _build_text_sources(document)
    field_evidence: list[ExtractedFieldEvidence] = []
    provenance_snippets: list[EvidenceSnippet] = []
    warnings: list[str] = []

    chromatography_system_candidates = _extract_chromatography_system_candidates(
        sources
    )
    selected_chromatography_system_candidate = _select_chromatography_system_candidate(
        chromatography_system_candidates
    )
    if selected_chromatography_system_candidate is not None:
        chromatography_system = (
            selected_chromatography_system_candidate.chromatography_system
        )
        _record_selected_chromatography_system_evidence(
            selected_chromatography_system_candidate,
            field_evidence,
            provenance_snippets,
        )
        if selected_chromatography_system_candidate.candidate_role != "final":
            warnings.append(
                "Chromatography system selection is based on the best available ambiguous candidate"
            )
    else:
        chromatography_system = None
        if chromatography_system_candidates:
            warnings.append(
                "Alternative or ambiguous chromatography-system statements were detected but no final column/system was resolved"
            )

    flow_rate = _extract_flow_rate_field(
        sources,
        field_evidence,
        provenance_snippets,
    )
    column_temperature = _extract_float_field(
        TEMPERATURE_PATTERN,
        sources,
        "method_parameters.column_temperature_c",
        field_evidence,
        provenance_snippets,
    )
    run_time = None
    mobile_phase_candidates = _extract_mobile_phase_candidates(sources)
    mobile_phase_detail_candidates = _extract_mobile_phase_detail_candidates(sources)
    selected_mobile_phase_candidate = _select_mobile_phase_candidate(
        mobile_phase_candidates
    )
    if selected_mobile_phase_candidate is not None:
        selected_mobile_phase_candidate.selected_for_method_parameters = True
        mobile_phase_a = selected_mobile_phase_candidate.mobile_phase_a
        mobile_phase_b = selected_mobile_phase_candidate.mobile_phase_b
        _record_selected_mobile_phase_evidence(
            selected_mobile_phase_candidate,
            field_evidence,
            provenance_snippets,
        )
        if selected_mobile_phase_candidate.candidate_role != "final":
            warnings.append(
                "Mobile phase A/B selection is based on the best available ambiguous candidate"
            )
    else:
        mobile_phase_a, mobile_phase_b = (None, None)
        if mobile_phase_detail_candidates:
            warnings.append(
                "Standalone mobile-phase detail statements were detected, but no complete mobile-phase A/B system was resolved"
            )

        if mobile_phase_a is None and mobile_phase_candidates:
            warnings.append(
                "Alternative or ambiguous mobile-phase statements were detected but no final mobile-phase A/B system was resolved"
            )

    mobile_phase_a, mobile_phase_b = _apply_mobile_phase_detail_candidates(
        mobile_phase_a,
        mobile_phase_b,
        mobile_phase_detail_candidates,
        field_evidence,
        provenance_snippets,
    )

    gradient_candidates = _extract_gradient_candidates(sources)
    selected_gradient_candidate = _select_gradient_candidate(gradient_candidates)
    if selected_gradient_candidate is not None:
        gradient_profile = selected_gradient_candidate.gradient_profile
        _record_selected_gradient_evidence(
            selected_gradient_candidate,
            field_evidence,
            provenance_snippets,
        )
        if selected_gradient_candidate.candidate_role != "final":
            warnings.append(
                "Gradient selection is based on the best available ambiguous candidate"
            )
    else:
        gradient_profile = []
        if gradient_candidates:
            warnings.append(
                "Alternative or ambiguous gradient statements were detected but no final gradient profile was resolved"
            )

    timing_candidates = _extract_timing_candidates(sources, gradient_candidates)
    selected_timing_candidate = _select_timing_candidate(timing_candidates)
    if selected_timing_candidate is not None:
        run_time = selected_timing_candidate.run_time_min or run_time
        _record_selected_timing_evidence(
            selected_timing_candidate,
            field_evidence,
            provenance_snippets,
        )
        if selected_timing_candidate.candidate_role != "final":
            warnings.append(
                "Run-time selection is based on the best available ambiguous candidate"
            )

    retention_time_observations = _extract_retention_time_observations(
        sources,
        field_evidence,
        provenance_snippets,
    )
    anchored_entity_candidates = _extract_anchored_entity_candidates(
        retention_time_observations
    )
    molecular_entity_drafts = _build_molecular_entity_drafts(anchored_entity_candidates)

    if chromatography_system is None:
        warnings.append("Column geometry was not extracted from text")

    method_parameters = None
    if (
        mobile_phase_a is not None
        and flow_rate is not None
    ):
        try:
            method_parameters = MethodParameters(
                mobile_phase_a=mobile_phase_a,
                mobile_phase_b=mobile_phase_b,
                flow_rate_ml_min=flow_rate,
                column_temperature_c=column_temperature,
                run_time_min=run_time,
                gradient_profile=gradient_profile,
            )
        except ValueError:
            warnings.append("Method parameter extraction is incomplete or invalid")
    
    extraction_mode = "parsed_text"
    llm_data: dict | None = None
    unresolved_field_groups = _build_unresolved_llm_field_groups(
        chromatography_system=chromatography_system,
        method_parameters=method_parameters,
    )
    llm_supports_targeted_extraction = (
        gemini_client is not None
        and hasattr(gemini_client, "extract_targeted_hplc_bundle")
    )
    llm_supports_vetted_snippets = (
        gemini_client is not None and hasattr(gemini_client, "vet_evidence_snippets")
    )
    if unresolved_field_groups and llm_supports_targeted_extraction:
        rprint("[yellow]Triggering evidence-targeted LLM fallback...[/yellow]")
        llm_data = _extract_via_llm(
            evidence_units,
            gemini_client,
            request_text=request_text
            or "Extract the final chromatographic method from this paper.",
            unresolved_field_groups=unresolved_field_groups,
            runtime_tracker=runtime_tracker,
        )
        if llm_data:
            rprint(f"[green]LLM data received: {list(llm_data.keys())}[/green]")
            try:
                updated_chromatography_system = _merge_llm_chromatography_system(
                    chromatography_system,
                    llm_data,
                )
                updated_method_parameters = _merge_llm_method_parameters(
                    method_parameters,
                    llm_data,
                )
                if (
                    updated_chromatography_system is not None
                    or updated_method_parameters is not None
                ):
                    chromatography_system = (
                        updated_chromatography_system or chromatography_system
                    )
                    method_parameters = (
                        updated_method_parameters or method_parameters
                    )
                    extraction_mode = "llm_assisted"
                    warnings.append(
                        "Method extraction was recovered via evidence-targeted LLM assistance because the rules-based parser stayed incomplete"
                    )
                    rprint("[bold green]LLM recovery successful![/bold green]")
            except Exception as exc:
                rprint(f"[bold red]LLM recovery failed: {exc}[/bold red]")
                warnings.append(f"LLM-assisted extraction recovery failed: {exc}")
        else:
            rprint("[red]LLM returned no targeted extraction data.[/red]")

    # Full-document LLM extraction as a last resort when completeness is still low
    completeness = _score_completeness(
        chromatography_system=chromatography_system,
        method_parameters=method_parameters,
    )
    if (
        allow_full_document_llm_fallback
        and completeness < 0.4
        and gemini_client is not None
        and document.source_document.source_type == "pdf"
        and method_parameters is None
    ):
        source = document.source_document
        source_label = source.source_document_id
        if source.title:
            source_label = f"{source_label} — {source.title[:120]}"
        rprint(
            f"[yellow]Completeness {completeness:.2f} < 0.4 for {source_label} — "
            "trying full-document LLM extraction...[/yellow]"
        )

        def _apply_full_document_recovery(
            llm_raw: dict | None,
            *,
            recovery_source: str,
        ) -> bool:
            nonlocal chromatography_system, method_parameters, extraction_mode
            nonlocal provenance_snippets, completeness
            if not llm_raw:
                return False
            try:
                recovered_system = _merge_llm_chromatography_system(
                    chromatography_system, llm_raw
                )
                recovered_params = _merge_llm_method_parameters(
                    method_parameters, llm_raw
                )
                new_completeness = _score_completeness(
                    chromatography_system=recovered_system or chromatography_system,
                    method_parameters=recovered_params or method_parameters,
                )
                if new_completeness > completeness:
                    chromatography_system = recovered_system or chromatography_system
                    method_parameters = recovered_params or method_parameters
                    extraction_mode = "llm_assisted"
                    warnings.append(
                        f"Method extraction was recovered via {recovery_source}"
                    )
                    rprint(
                        f"[bold green]Full-document LLM recovery via {recovery_source} for {source_label}: "
                        f"completeness {completeness:.2f} → {new_completeness:.2f}[/bold green]"
                    )
                    completeness = new_completeness
                    if llm_raw.get("evidence_quote") and not provenance_snippets:
                        provenance_snippets = [
                            EvidenceSnippet(
                                text=str(llm_raw["evidence_quote"])[:4000],
                                page_number=None,
                                section_label="Agent Vetted",
                            )
                        ]
                    return True
            except Exception as exc:
                rprint(f"[red]Full-document LLM recovery failed: {exc}[/red]")
                warnings.append(f"Full-document LLM extraction failed: {exc}")
            return False

        recovered = False
        if source_pdf_bytes:
            llm_raw = extract_hplc_via_pdf_llm(
                document,
                gemini_client,
                pdf_bytes=source_pdf_bytes,
                pdf_url=source_pdf_url,
                request_text=request_text,
            )
            recovered = _apply_full_document_recovery(
                llm_raw,
                recovery_source="OpenRouter PDF parser",
            )
        if not recovered and source_pdf_bytes:
            llm_raw = extract_hplc_via_markdown_pdf_llm(
                document,
                gemini_client,
                pdf_bytes=source_pdf_bytes,
                request_text=request_text,
            )
            recovered = _apply_full_document_recovery(
                llm_raw,
                recovery_source="local PyMuPDF4LLM Markdown extraction",
            )
        if not recovered:
            llm_raw = extract_hplc_via_llm(document, gemini_client)
            _apply_full_document_recovery(
                llm_raw,
                recovery_source="full-document text LLM extraction",
            )

    # Vet Evidence Snippets
    document_cache_key = build_document_cache_key(document)
    if llm_supports_vetted_snippets and provenance_snippets:
        vetted_cache_key = build_vetted_snippet_cache_key(
            document_cache_key,
            [snippet.text for snippet in provenance_snippets],
        )
        cached_quote = vetted_snippet_cache_lookup(vetted_cache_key)
        if cached_quote:
            if runtime_tracker is not None:
                runtime_tracker.note_cache_event(
                    "extract_methods",
                    cache_name="vetted_snippet",
                    hit=True,
                )
            page = provenance_snippets[0].page_number if provenance_snippets else None
            provenance_snippets = [
                EvidenceSnippet(
                    text=cached_quote[:4000],
                    page_number=page,
                    section_label="Agent Vetted",
                )
            ]
        else:
            if runtime_tracker is not None:
                runtime_tracker.note_cache_event(
                    "extract_methods",
                    cache_name="vetted_snippet",
                    hit=False,
                )
            try:
                vetted_quote = gemini_client.vet_evidence_snippets(
                    [snippet.text for snippet in provenance_snippets]
                )
                if vetted_quote:
                    store_vetted_snippet_cache(vetted_cache_key, vetted_quote)
                    page = provenance_snippets[0].page_number if provenance_snippets else None
                    provenance_snippets = [
                        EvidenceSnippet(
                            text=vetted_quote[:4000],
                            page_number=page,
                            section_label="Agent Vetted",
                        )
                    ]
            except Exception as e:
                warnings.append(f"Evidence vetting failed: {e}")
    elif (
        extraction_mode == "llm_assisted"
        and llm_data
        and llm_data.get("evidence_quote")
    ):
        provenance_snippets = [
            EvidenceSnippet(
                text=llm_data.get("evidence_quote")[:4000],
                page_number=None,
                section_label="Agent Vetted",
            )
        ]

    if method_parameters is None:
        warnings.append("Method parameter extraction did not capture required fields (Mobile Phase A and Flow Rate)")

    extraction_confidence = _compute_extraction_confidence(field_evidence)
    provenance = RetrievalProvenance(
        extraction_mode=extraction_mode,
        source_pages=sorted(
            {
                snippet.page_number
                for snippet in provenance_snippets
                if snippet.page_number is not None
            }
        ),
        extraction_confidence=extraction_confidence,
        evidence_snippets=provenance_snippets,
    )

    record_draft = _build_retrieval_record_draft(
        document=document,
        chromatography_system=chromatography_system,
        method_parameters=method_parameters,
        provenance=provenance,
        retention_time_observations=retention_time_observations,
        anchored_entity_candidates=anchored_entity_candidates,
        molecular_entity_drafts=molecular_entity_drafts,
    )
    if record_draft is not None:
        record_draft = record_draft.model_copy(
            update={"validation": validate_record_draft(record_draft)}
        )

    response = MinimalHplcExtractionResponse(
        source_document=document.source_document,
        chromatography_system=chromatography_system,
        method_parameters=method_parameters,
        chromatography_system_candidates=chromatography_system_candidates,
        mobile_phase_candidates=mobile_phase_candidates,
        mobile_phase_detail_candidates=mobile_phase_detail_candidates,
        gradient_candidates=gradient_candidates,
        timing_candidates=timing_candidates,
        retention_time_observations=retention_time_observations,
        anchored_entity_candidates=anchored_entity_candidates,
        molecular_entity_drafts=molecular_entity_drafts,
        provenance=provenance,
        field_evidence=field_evidence,
        warnings=warnings,
        record_draft=record_draft,
        retrieval_record_ready=(
            record_draft.validation.retrieval_ready
            if record_draft is not None
            else False
        ),
    )
    store_extraction_cache(extraction_cache_key, response)
    return response


def _llm_cache_key(
    gemini_client: GeminiOrchestrationClient | None,
    *,
    request_text: str | None = None,
) -> str | None:
    if gemini_client is None:
        return None
    settings = getattr(gemini_client, "_settings", None)
    if settings is None:
        return gemini_client.__class__.__name__
    provider = getattr(settings, "llm_provider", gemini_client.__class__.__name__)
    worker_model = getattr(settings, "worker_model", "worker")
    if not request_text:
        return f"{provider}:{worker_model}"
    request_hash = sha256(request_text.strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"{provider}:{worker_model}:{request_hash}"


def _build_unresolved_llm_field_groups(
    *,
    chromatography_system: ChromatographySystem | None,
    method_parameters: MethodParameters | None,
) -> tuple[str, ...]:
    field_groups: list[str] = []
    if chromatography_system is None:
        field_groups.append("chromatography_system")
    if method_parameters is None or not method_parameters.mobile_phase_a.solvent:
        field_groups.append("mobile_phase_gradient")
    elif method_parameters is None or (
        method_parameters.flow_rate_ml_min is None
        or (
            not method_parameters.gradient_profile
            and method_parameters.isocratic_percent_b is None
            and method_parameters.run_time_min is None
        )
    ):
        field_groups.append("mobile_phase_gradient")
    return tuple(field_groups)


def _merge_llm_chromatography_system(
    chromatography_system: ChromatographySystem | None,
    llm_data: dict,
) -> ChromatographySystem | None:
    if chromatography_system is not None:
        return chromatography_system
    column_name = str(llm_data.get("column_name") or "").strip()
    column_length_mm = _safe_llm_float(llm_data.get("column_length_mm"))
    column_inner_diameter_mm = _safe_llm_float(
        llm_data.get("column_inner_diameter_mm")
    )
    particle_size_um = _safe_llm_float(llm_data.get("particle_size_um"))
    if (
        not column_name
        or column_length_mm is None
        or column_inner_diameter_mm is None
        or particle_size_um is None
    ):
        return None
    chemistry = "unknown"
    if "C18" in column_name.upper():
        chemistry = "C18"
    elif "C8" in column_name.upper():
        chemistry = "C8"
    elif "HILIC" in column_name.upper():
        chemistry = "hilic"
    return ChromatographySystem(
        mode=cast(
            ChromatographyMode,
            (llm_data.get("mode") or "rp_lc"),
        ),
        column_manufacturer=_infer_column_manufacturer(column_name),
        column_name=column_name,
        stationary_phase_chemistry=(
            str(llm_data.get("stationary_phase_chemistry") or "").strip() or chemistry
        ),
        column_length_mm=column_length_mm,
        column_inner_diameter_mm=column_inner_diameter_mm,
        particle_size_um=particle_size_um,
    )


def _merge_llm_method_parameters(
    method_parameters: MethodParameters | None,
    llm_data: dict,
) -> MethodParameters | None:
    mobile_phase_a = _mobile_phase_from_llm(llm_data.get("mobile_phase_a"))
    mobile_phase_b = _mobile_phase_from_llm(llm_data.get("mobile_phase_b"))
    if method_parameters is None and mobile_phase_a is None:
        return None

    gradient_profile = _gradient_profile_from_llm(llm_data.get("gradient_profile"))
    flow_rate = _safe_llm_float(llm_data.get("flow_rate_ml_min"))
    column_temperature = _safe_llm_float(llm_data.get("column_temperature_c"))
    run_time = _safe_llm_float(llm_data.get("run_time_min"))
    isocratic_percent_b = _safe_llm_float(llm_data.get("isocratic_percent_b"))
    gradient_profile, isocratic_percent_b = _normalize_llm_gradient_profile(
        gradient_profile,
        isocratic_percent_b=isocratic_percent_b,
    )

    if method_parameters is None:
        if mobile_phase_a is None or flow_rate is None:
            return None
        return MethodParameters(
            mobile_phase_a=mobile_phase_a,
            mobile_phase_b=mobile_phase_b,
            flow_rate_ml_min=flow_rate,
            column_temperature_c=column_temperature,
            run_time_min=run_time,
            isocratic_percent_b=isocratic_percent_b,
            gradient_profile=gradient_profile,
        )

    return MethodParameters(
        mobile_phase_a=mobile_phase_a or method_parameters.mobile_phase_a,
        mobile_phase_b=mobile_phase_b or method_parameters.mobile_phase_b,
        flow_rate_ml_min=flow_rate or method_parameters.flow_rate_ml_min,
        column_temperature_c=(
            column_temperature
            if column_temperature is not None
            else method_parameters.column_temperature_c
        ),
        run_time_min=run_time if run_time is not None else method_parameters.run_time_min,
        isocratic_percent_b=(
            isocratic_percent_b
            if isocratic_percent_b is not None
            else method_parameters.isocratic_percent_b
        ),
        gradient_profile=gradient_profile or method_parameters.gradient_profile,
    )


def _mobile_phase_from_llm(value: object) -> MobilePhase | None:
    if not isinstance(value, dict):
        return None
    solvent = str(value.get("solvent") or "").strip()
    if not solvent:
        return None
    additive = str(value.get("additive") or "").strip() or None
    ph_estimate = _safe_llm_float(value.get("ph_estimate"))
    return MobilePhase(solvent=solvent, additive=additive, ph_estimate=ph_estimate)


def _gradient_profile_from_llm(value: object) -> list[GradientPoint]:
    if not isinstance(value, list):
        return []
    gradient_profile: list[GradientPoint] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        time_min = _safe_llm_float(item.get("time_min"))
        percent_b = _safe_llm_float(item.get("percent_b"))
        if time_min is None or percent_b is None:
            continue
        gradient_profile.append(
            GradientPoint(time_min=time_min, percent_b=percent_b)
        )
    return gradient_profile


def _normalize_llm_gradient_profile(
    gradient_profile: list[GradientPoint],
    *,
    isocratic_percent_b: float | None,
) -> tuple[list[GradientPoint], float | None]:
    if len(gradient_profile) != 1:
        return gradient_profile, isocratic_percent_b

    single_point = gradient_profile[0]
    if isocratic_percent_b is None and abs(single_point.time_min) < 1e-6:
        return [], single_point.percent_b

    # Treat malformed one-point gradients as unusable instead of letting them
    # invalidate the entire LLM recovery payload.
    return [], isocratic_percent_b


def _safe_llm_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).split()[0].replace(",", "."))
    except (ValueError, IndexError):
        return None


def _build_text_sources(document: RegisteredSourceDocument) -> list[_TextSource]:
    priority_by_kind = {
        "methods": 1.0,
        "results": 0.92,
        "discussion": 0.82,
        "conclusion": 0.78,
        "abstract": 0.68,
        "introduction": 0.55,
        "other": 0.5,
        "references": 0.1,
    }
    sources: list[_TextSource] = []
    for section in document.sections:
        section_priority = priority_by_kind.get(section.normalized_label, 0.4)
        sources.append(
            _TextSource(
                text=section.text,
                section_label=section.label,
                section_kind=section.normalized_label,
                page_number=section.start_page_number,
                priority=section_priority,
            )
        )
        if document.source_document.source_type == "pdf":
            for block_text in _build_pdf_text_blocks(section.text):
                if block_text == section.text:
                    continue
                sources.append(
                    _TextSource(
                        text=block_text,
                        section_label=section.label,
                        section_kind=section.normalized_label,
                        page_number=section.start_page_number,
                        priority=section_priority,
                    )
                )
            normalized_section_text = _normalize_compact_extraction_text(section.text)
            if normalized_section_text != section.text:
                sources.append(
                    _TextSource(
                        text=normalized_section_text,
                        section_label=section.label,
                        section_kind=section.normalized_label,
                        page_number=section.start_page_number,
                        priority=section_priority + 0.02,
                    )
                )
    for page in document.pages:
        if document.source_document.source_type == "pdf":
            for block_text in _build_pdf_text_blocks(page.text):
                if block_text == page.text:
                    continue
                sources.append(
                    _TextSource(
                        text=block_text,
                        section_label=None,
                        section_kind=None,
                        page_number=page.page_number,
                        priority=0.65,
                    )
                )
            normalized_page_text = _normalize_compact_extraction_text(page.text)
            if normalized_page_text != page.text:
                sources.append(
                    _TextSource(
                        text=normalized_page_text,
                        section_label=None,
                        section_kind=None,
                        page_number=page.page_number,
                        priority=0.66,
                    )
                )
        sources.append(
            _TextSource(
                text=page.text,
                section_label=None,
                section_kind=None,
                page_number=page.page_number,
                priority=0.35,
            )
        )
    sources.sort(key=lambda source: (-source.priority, len(source.text)))
    return sources


def _build_pdf_text_blocks(text: str) -> list[str]:
    lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
    if not lines:
        return []

    blocks: list[str] = []
    seen_blocks: set[str] = set()
    current_block: list[str] = []
    for line in lines:
        current_block.append(line)
        if _should_flush_pdf_text_block(line, current_block):
            _append_pdf_text_block(blocks, seen_blocks, current_block)
            current_block = []
    if current_block:
        _append_pdf_text_block(blocks, seen_blocks, current_block)
    return blocks


def _should_flush_pdf_text_block(line: str, current_block: list[str]) -> bool:
    if len(current_block) >= 6:
        return True
    return line.endswith((".", ";", ":", "?", "!"))


def _append_pdf_text_block(
    blocks: list[str], seen_blocks: set[str], block_lines: list[str]
) -> None:
    block_text = _clean_text(" ".join(block_lines))
    if not block_text or block_text in seen_blocks:
        return
    seen_blocks.add(block_text)
    blocks.append(block_text)


def _find_first_match(
    patterns: tuple[re.Pattern, ...], sources: list[_TextSource]
) -> tuple[re.Match, _TextSource] | None:
    for source in sources:
        for pattern in patterns:
            match = pattern.search(source.cleaned_text)
            if match is not None:
                return (match, source)
    return None


def _extract_chromatography_system_candidates(
    sources: list[_TextSource],
) -> list[ExtractedChromatographySystemCandidate]:
    candidates: list[ExtractedChromatographySystemCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()
    for source in sources:
        for pattern in (
            COLUMN_COMPACT_PATTERN,
            COLUMN_PARTICLE_FIRST_PATTERN,
            COLUMN_VERBOSE_PATTERN,
        ):
            for match in pattern.finditer(source.cleaned_text):
                candidate = _build_chromatography_system_candidate(match, source)
                if candidate is None:
                    continue
                dedupe_key = _chromatography_system_candidate_dedupe_key(candidate)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                candidates.append(candidate)
    candidates.sort(key=_chromatography_system_candidate_sort_key, reverse=True)
    selected_candidate = _select_chromatography_system_candidate(candidates)
    if selected_candidate is not None:
        selected_candidate.selected_for_output = True
    return candidates


def _build_chromatography_system_candidate(
    match: re.Match[str], source: _TextSource
) -> ExtractedChromatographySystemCandidate | None:
    sentence_text = _extract_sentence_context(source.text, match.start(), match.end())
    column_label = _clean_column_label(_clean_match_group(match, "column"))
    stationary_phase_chemistry = _infer_stationary_phase_chemistry(column_label)
    if stationary_phase_chemistry is None:
        return None
    try:
        chromatography_system = ChromatographySystem(
            mode=_infer_chromatography_mode(stationary_phase_chemistry),
            column_manufacturer=_infer_column_manufacturer(column_label),
            column_name=column_label,
            stationary_phase_chemistry=stationary_phase_chemistry,
            column_length_mm=_parse_match_float(match, "length"),
            column_inner_diameter_mm=_parse_match_float(match, "diameter"),
            particle_size_um=_parse_match_float(match, "particle"),
        )
    except ValueError:
        return None

    snippet = EvidenceSnippet(
        text=_collapse_whitespace(sentence_text),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    candidate_role = _classify_full_system_candidate_role(sentence_text, source)
    return ExtractedChromatographySystemCandidate(
        candidate_kind="text_match",
        candidate_role=candidate_role,
        statement_text=snippet.text,
        confidence=_system_candidate_confidence(source, candidate_role),
        chromatography_system=chromatography_system,
        evidence_snippets=[snippet],
    )


def _chromatography_system_candidate_dedupe_key(
    candidate: ExtractedChromatographySystemCandidate,
) -> tuple[object, ...]:
    system = candidate.chromatography_system
    return (
        candidate.candidate_kind,
        system.column_name if system is not None else None,
        system.column_length_mm if system is not None else None,
        system.column_inner_diameter_mm if system is not None else None,
        system.particle_size_um if system is not None else None,
    )


def _chromatography_system_candidate_sort_key(
    candidate: ExtractedChromatographySystemCandidate,
) -> tuple[int, float]:
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    return (role_priority, candidate.confidence)


def _select_chromatography_system_candidate(
    candidates: list[ExtractedChromatographySystemCandidate],
) -> ExtractedChromatographySystemCandidate | None:
    eligible_candidates = [
        candidate
        for candidate in candidates
        if candidate.chromatography_system is not None
        and candidate.candidate_role in {"final", "ambiguous"}
    ]
    if not eligible_candidates:
        return None
    return max(eligible_candidates, key=_chromatography_system_candidate_sort_key)


def _record_selected_chromatography_system_evidence(
    candidate: ExtractedChromatographySystemCandidate,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> None:
    if not candidate.evidence_snippets:
        return
    _record_existing_snippet_evidence(
        field_evidence,
        provenance_snippets,
        "chromatography_system",
        candidate.evidence_snippets[0],
        candidate.confidence,
    )


def _system_candidate_confidence(
    source: _TextSource, candidate_role: MobilePhaseCandidateRole
) -> float:
    confidence = _confidence_for_source(source)
    confidence += {
        "final": 0.0,
        "ambiguous": -0.08,
        "comparison": -0.15,
        "trial": -0.2,
        "rejected": -0.3,
    }[candidate_role]
    return round(max(0.0, min(confidence, 1.0)), 2)


def _extract_float_field(
    pattern: re.Pattern[str],
    sources: list[_TextSource],
    field_path: str,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> float | None:
    match_result = _find_first_match((pattern,), sources)
    if match_result is None:
        return None

    match, source = match_result
    _record_field_evidence(
        field_evidence,
        provenance_snippets,
        field_path,
        source,
        match.start(),
        match.end(),
    )
    return _parse_match_float(match, "value")


def _extract_flow_rate_field(
    sources: list[_TextSource],
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> float | None:
    match_result = _find_first_match((FLOW_RATE_PATTERN,), sources)
    if match_result is None:
        return None

    match, source = match_result
    _record_field_evidence(
        field_evidence,
        provenance_snippets,
        "method_parameters.flow_rate_ml_min",
        source,
        match.start(),
        match.end(),
    )
    value = _parse_match_float(match, "value")
    unit = _clean_match_group(match, "unit").lower()
    if unit in {"ul", "µl", "mul"}:
        return round(value / 1000.0, 3)
    return value


def _extract_mobile_phase_candidates(
    sources: list[_TextSource],
) -> list[ExtractedMobilePhaseCandidate]:
    candidates: list[ExtractedMobilePhaseCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()

    for source in sources:
        explicit_candidate = _extract_explicit_mobile_phase_candidate(source)
        if explicit_candidate is not None:
            _append_mobile_phase_candidate(candidates, seen_keys, explicit_candidate)

        for sentence in _split_sentences(source.cleaned_text):
            full_system_candidate = _extract_sentence_mobile_phase_candidate(
                sentence, source
            )
            if full_system_candidate is not None:
                _append_mobile_phase_candidate(
                    candidates, seen_keys, full_system_candidate
                )

            replacement_candidate = _extract_replacement_mobile_phase_candidate(
                sentence, source
            )
            if replacement_candidate is not None:
                _append_mobile_phase_candidate(
                    candidates, seen_keys, replacement_candidate
                )

    candidates.sort(key=_mobile_phase_candidate_sort_key, reverse=True)
    selected_candidate = _select_mobile_phase_candidate(candidates)
    if selected_candidate is not None:
        selected_candidate.selected_for_method_parameters = True
    return candidates


def _extract_explicit_mobile_phase_candidate(
    source: _TextSource,
) -> ExtractedMobilePhaseCandidate | None:
    # Use cleaned_text for matching to handle Unicode artifacts
    match_a = ELUENT_A_PATTERN.search(source.cleaned_text)
    if match_a is None:
        return None

    # Search for match_b within a reasonable distance of match_a
    match_b = ELUENT_B_PATTERN.search(source.text)
    if match_b is not None:
        distance = abs(match_b.start() - match_a.start())
        if distance > 3000:
            match_b = None

    start_index = match_a.start()
    end_index = match_a.end()
    if match_b is not None:
        start_index = min(start_index, match_b.start())
        end_index = max(end_index, match_b.end())

    # Indices are valid for raw text
    exact_text = source.text[start_index:end_index]
    snippet = _build_snippet(source, start_index, end_index)
    candidate_role: MobilePhaseCandidateRole = _classify_full_system_candidate_role(
        exact_text, source
    )
    return ExtractedMobilePhaseCandidate(
        candidate_kind="full_system",
        candidate_role=candidate_role,
        statement_text=_collapse_whitespace(exact_text),
        confidence=_mobile_phase_candidate_confidence(
            source, candidate_role, explicit=True
        ),
        mobile_phase_a=_parse_mobile_phase_text(match_a.group("value")),
        mobile_phase_b=(
            _parse_mobile_phase_text(match_b.group("value"))
            if match_b is not None
            else None
        ),
        evidence_snippets=[snippet],
    )


def _extract_sentence_mobile_phase_candidate(
    sentence: str, source: _TextSource
) -> ExtractedMobilePhaseCandidate | None:
    for pattern in (
        MOBILE_PHASE_PAIR_PATTERN,
        GENERIC_MOBILE_PHASE_PAIR_PATTERN,
        SOLVENT_PAIR_PATTERN,
        ISOCRATIC_PREMIX_PATTERN,
    ):
        match = pattern.search(sentence)
        if match is None:
            continue
        snippet = EvidenceSnippet(
            text=_collapse_whitespace(sentence),
            page_number=source.page_number,
            section_label=source.section_label,
        )
        candidate_role: MobilePhaseCandidateRole = _classify_full_system_candidate_role(
            sentence, source
        )

        if pattern == ISOCRATIC_PREMIX_PATTERN:
            mix_text = match.group("mix")
            ratios = match.group("ratios") or ""
            # For premix, we treat the whole thing as mobile_phase_a for now
            # as it represents the singular isocratic eluent.
            return ExtractedMobilePhaseCandidate(
                candidate_kind="full_system",
                candidate_role=candidate_role,
                statement_text=snippet.text,
                confidence=_mobile_phase_candidate_confidence(source, candidate_role),
                mobile_phase_a=_parse_mobile_phase_text(f"{mix_text} ({ratios})"),
                mobile_phase_b=None,
                evidence_snippets=[snippet],
            )

        return ExtractedMobilePhaseCandidate(
            candidate_kind="full_system",
            candidate_role=candidate_role,
            statement_text=snippet.text,
            confidence=_mobile_phase_candidate_confidence(source, candidate_role),
            mobile_phase_a=_parse_mobile_phase_text(_clean_match_group(match, "a")),
            mobile_phase_b=_parse_mobile_phase_text(_clean_match_group(match, "b")),
            evidence_snippets=[snippet],
        )
    fallback_candidate = _extract_generic_mobile_phase_candidate(sentence, source)
    if fallback_candidate is not None:
        return fallback_candidate
    return None


def _extract_generic_mobile_phase_candidate(
    sentence: str, source: _TextSource
) -> ExtractedMobilePhaseCandidate | None:
    match = GENERIC_MOBILE_PHASE_PAIR_PATTERN.search(sentence)
    if match is not None:
        phase_a_text = _clean_match_group(match, "a")
        phase_b_text = _clean_match_group(match, "b")
    else:
        normalized_sentence = _clean_text(sentence)
        phrase_match = re.search(
            r"mobile\s*phase(?:\s+consisting\s+of|\s+consisted\s+of|\s+of)\s+(?P<body>.+)$",
            normalized_sentence,
            re.IGNORECASE,
        )
        if phrase_match is None:
            return None
        body = phrase_match.group("body")
        split_match = re.search(
            r"(?P<a>.+?)\s+(?:and|,)\s+(?P<b>acetonitrile|ACN|methanol|MeOH|2-propanol|isopropanol|MTBE)\b",
            body,
            re.IGNORECASE,
        )
        if split_match is None:
            return None
        phase_a_text = _clean_match_group(split_match, "a")
        phase_b_text = _clean_match_group(split_match, "b")

    snippet = EvidenceSnippet(
        text=_collapse_whitespace(sentence),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    candidate_role = _classify_full_system_candidate_role(sentence, source)
    return ExtractedMobilePhaseCandidate(
        candidate_kind="full_system",
        candidate_role=candidate_role,
        statement_text=snippet.text,
        confidence=_mobile_phase_candidate_confidence(source, candidate_role),
        mobile_phase_a=_parse_mobile_phase_text(phase_a_text),
        mobile_phase_b=_parse_mobile_phase_text(phase_b_text),
        evidence_snippets=[snippet],
    )


def _extract_replacement_mobile_phase_candidate(
    sentence: str, source: _TextSource
) -> ExtractedMobilePhaseCandidate | None:
    for pattern in (SOLVENT_REPLACEMENT_PATTERN, SOLVENT_REPLACED_WITH_PATTERN):
        match = pattern.search(sentence)
        if match is None:
            continue
        snippet = EvidenceSnippet(
            text=_collapse_whitespace(sentence),
            page_number=source.page_number,
            section_label=source.section_label,
        )
        candidate_role: MobilePhaseCandidateRole = _classify_replacement_candidate_role(
            sentence, source
        )
        return ExtractedMobilePhaseCandidate(
            candidate_kind="replacement_note",
            candidate_role=candidate_role,
            statement_text=snippet.text,
            confidence=_mobile_phase_candidate_confidence(
                source, candidate_role, replacement_note=True
            ),
            comparison_from_text=_infer_solvent(_clean_text(match.group("from"))),
            comparison_to_text=_infer_solvent(_clean_text(match.group("to"))),
            evidence_snippets=[snippet],
        )
    return None


def _append_mobile_phase_candidate(
    candidates: list[ExtractedMobilePhaseCandidate],
    seen_keys: set[tuple[object, ...]],
    candidate: ExtractedMobilePhaseCandidate,
) -> None:
    dedupe_key = _mobile_phase_candidate_dedupe_key(candidate)
    if dedupe_key in seen_keys:
        return
    seen_keys.add(dedupe_key)
    candidates.append(candidate)


def _mobile_phase_candidate_dedupe_key(
    candidate: ExtractedMobilePhaseCandidate,
) -> tuple[object, ...]:
    if candidate.candidate_kind == "full_system":
        return (
            candidate.candidate_kind,
            candidate.mobile_phase_a.model_dump_json()
            if candidate.mobile_phase_a
            else None,
            candidate.mobile_phase_b.model_dump_json()
            if candidate.mobile_phase_b
            else None,
        )
    return (
        candidate.candidate_kind,
        candidate.comparison_from_text,
        candidate.comparison_to_text,
        candidate.statement_text.lower(),
    )


def _mobile_phase_candidate_sort_key(
    candidate: ExtractedMobilePhaseCandidate,
) -> tuple[int, float]:
    kind_priority = 1 if candidate.candidate_kind == "full_system" else 0
    # Prioritize having both A and B over just A (isocratic)
    completeness_priority = 1 if (candidate.mobile_phase_a and candidate.mobile_phase_b) else 0
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    # We want completeness to be a strong signal but not override role
    return (kind_priority * 100 + role_priority * 10 + completeness_priority, candidate.confidence)


def _select_mobile_phase_candidate(
    candidates: list[ExtractedMobilePhaseCandidate],
) -> ExtractedMobilePhaseCandidate | None:
    eligible_candidates = [
        candidate
        for candidate in candidates
        if candidate.candidate_kind == "full_system"
        and candidate.candidate_role in {"final", "ambiguous"}
    ]
    if not eligible_candidates:
        return None
    return max(eligible_candidates, key=_mobile_phase_candidate_sort_key)


def _record_selected_mobile_phase_evidence(
    candidate: ExtractedMobilePhaseCandidate,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> None:
    if not candidate.evidence_snippets:
        return
    snippet = candidate.evidence_snippets[0]
    confidence = candidate.confidence
    if candidate.mobile_phase_a is not None:
        _record_existing_snippet_evidence(
            field_evidence,
            provenance_snippets,
            "method_parameters.mobile_phase_a",
            snippet,
            confidence,
        )
    if candidate.mobile_phase_b is not None:
        _record_existing_snippet_evidence(
            field_evidence,
            provenance_snippets,
            "method_parameters.mobile_phase_b",
            snippet,
            confidence,
        )


def _extract_mobile_phase_detail_candidates(
    sources: list[_TextSource],
) -> list[ExtractedMobilePhaseDetailCandidate]:
    candidates: list[ExtractedMobilePhaseDetailCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()
    for source in sources:
        for sentence in _split_sentences(source.cleaned_text):
            candidate = _extract_mobile_phase_detail_candidate(sentence, source)
            if candidate is None:
                continue
            dedupe_key = (
                candidate.target_phase,
                candidate.additive,
                candidate.ph_estimate,
                candidate.candidate_role,
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            candidates.append(candidate)
    candidates.sort(key=_mobile_phase_detail_candidate_sort_key, reverse=True)
    return candidates


def _extract_mobile_phase_detail_candidate(
    sentence: str, source: _TextSource
) -> ExtractedMobilePhaseDetailCandidate | None:
    normalized = sentence.lower()
    additive_match = ADDITIVE_PATTERN.search(sentence)
    ph_match = PH_PATTERN.search(sentence)
    if additive_match is None and ph_match is None:
        return None
    target_phase: MobilePhaseDetailTarget | None = _infer_mobile_phase_detail_target(
        normalized
    )
    if target_phase is None:
        return None
    snippet = EvidenceSnippet(
        text=_collapse_whitespace(sentence),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    candidate_role = _classify_full_system_candidate_role(sentence, source)
    return ExtractedMobilePhaseDetailCandidate(
        candidate_kind="phase_detail_statement",
        candidate_role=candidate_role,
        target_phase=target_phase,
        statement_text=snippet.text,
        confidence=_mobile_phase_detail_candidate_confidence(source, candidate_role),
        additive=(
            additive_match.group("additive") if additive_match is not None else None
        ),
        ph_estimate=(float(ph_match.group("value")) if ph_match is not None else None),
        evidence_snippets=[snippet],
    )


def _infer_mobile_phase_detail_target(
    normalized_sentence: str,
) -> MobilePhaseDetailTarget | None:
    if "eluent a" in normalized_sentence or "phase a" in normalized_sentence:
        return cast(MobilePhaseDetailTarget, "mobile_phase_a")
    if "eluent b" in normalized_sentence or "phase b" in normalized_sentence:
        return cast(MobilePhaseDetailTarget, "mobile_phase_b")
    if "aqueous phase" in normalized_sentence:
        return cast(MobilePhaseDetailTarget, "mobile_phase_a")
    if "organic phase" in normalized_sentence:
        return cast(MobilePhaseDetailTarget, "mobile_phase_b")
    if "mobile phase" in normalized_sentence or "buffer" in normalized_sentence:
        return cast(MobilePhaseDetailTarget, "unspecified")
    return None


def _mobile_phase_detail_candidate_sort_key(
    candidate: ExtractedMobilePhaseDetailCandidate,
) -> tuple[int, float]:
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    target_priority = 1 if candidate.target_phase != "unspecified" else 0
    return (role_priority * 10 + target_priority, candidate.confidence)


def _mobile_phase_detail_candidate_confidence(
    source: _TextSource, candidate_role: MobilePhaseCandidateRole
) -> float:
    confidence = _confidence_for_source(source) - 0.03
    confidence += {
        "final": 0.0,
        "ambiguous": -0.08,
        "comparison": -0.15,
        "trial": -0.2,
        "rejected": -0.3,
    }[candidate_role]
    return round(max(0.0, min(confidence, 1.0)), 2)


def _apply_mobile_phase_detail_candidates(
    mobile_phase_a: MobilePhase | None,
    mobile_phase_b: MobilePhase | None,
    candidates: list[ExtractedMobilePhaseDetailCandidate],
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> tuple[MobilePhase | None, MobilePhase | None]:
    if mobile_phase_a is None and mobile_phase_b is None:
        return (mobile_phase_a, mobile_phase_b)

    best_a = _select_mobile_phase_detail_candidate(candidates, "mobile_phase_a")
    best_b = _select_mobile_phase_detail_candidate(candidates, "mobile_phase_b")

    if mobile_phase_a is not None and best_a is not None:
        updated_a = _merge_mobile_phase_detail(mobile_phase_a, best_a)
        if updated_a != mobile_phase_a:
            best_a.selected_for_method_parameters = True
            mobile_phase_a = updated_a
            _record_mobile_phase_detail_evidence(
                best_a,
                field_evidence,
                provenance_snippets,
                "method_parameters.mobile_phase_a",
            )
    if mobile_phase_b is not None and best_b is not None:
        updated_b = _merge_mobile_phase_detail(mobile_phase_b, best_b)
        if updated_b != mobile_phase_b:
            best_b.selected_for_method_parameters = True
            mobile_phase_b = updated_b
            _record_mobile_phase_detail_evidence(
                best_b,
                field_evidence,
                provenance_snippets,
                "method_parameters.mobile_phase_b",
            )

    return (mobile_phase_a, mobile_phase_b)


def _select_mobile_phase_detail_candidate(
    candidates: list[ExtractedMobilePhaseDetailCandidate], target_phase: str
) -> ExtractedMobilePhaseDetailCandidate | None:
    eligible_candidates = [
        candidate
        for candidate in candidates
        if candidate.candidate_role in {"final", "ambiguous"}
        and candidate.target_phase in {target_phase, "unspecified"}
    ]
    if not eligible_candidates:
        return None
    return max(eligible_candidates, key=_mobile_phase_detail_candidate_sort_key)


def _merge_mobile_phase_detail(
    mobile_phase: MobilePhase, candidate: ExtractedMobilePhaseDetailCandidate
) -> MobilePhase:
    updated_mobile_phase = mobile_phase.model_copy(
        update={
            "additive": mobile_phase.additive or candidate.additive,
            "ph_estimate": mobile_phase.ph_estimate or candidate.ph_estimate,
        }
    )
    return updated_mobile_phase


def _record_mobile_phase_detail_evidence(
    candidate: ExtractedMobilePhaseDetailCandidate,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
    field_path: str,
) -> None:
    if not candidate.evidence_snippets:
        return
    _record_existing_snippet_evidence(
        field_evidence,
        provenance_snippets,
        field_path,
        candidate.evidence_snippets[0],
        candidate.confidence,
    )


def _record_existing_snippet_evidence(
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
    field_path: str,
    snippet: EvidenceSnippet,
    confidence: float,
) -> None:
    field_evidence.append(
        ExtractedFieldEvidence(
            field_path=field_path,
            confidence=confidence,
            snippet=snippet,
        )
    )
    provenance_snippets.append(snippet)


def _classify_full_system_candidate_role(
    text: str, source: _TextSource
) -> MobilePhaseCandidateRole:
    normalized = text.lower()
    if any(cue in normalized for cue in REJECTION_CUES):
        return "rejected"
    if any(cue in normalized for cue in FINAL_METHOD_CUES):
        return "final"
    if any(cue in normalized for cue in TRIAL_METHOD_CUES):
        return "trial"
    if any(cue in normalized for cue in COMPARISON_CUES) and not any(
        cue in normalized for cue in FINAL_METHOD_CUES
    ):
        return "comparison"
    if "eluent a" in normalized or "eluent b" in normalized:
        return "final"
    if source.section_kind == "methods":
        return "final"
    return "ambiguous"


def _classify_replacement_candidate_role(
    text: str, source: _TextSource
) -> MobilePhaseCandidateRole:
    normalized = text.lower()
    if any(cue in normalized for cue in REJECTION_CUES):
        return "rejected"
    if any(cue in normalized for cue in TRIAL_METHOD_CUES):
        return "trial"
    if any(cue in normalized for cue in COMPARISON_CUES):
        return "comparison"
    if source.section_kind == "methods":
        return "ambiguous"
    return "comparison"


def _mobile_phase_candidate_confidence(
    source: _TextSource,
    candidate_role: MobilePhaseCandidateRole,
    *,
    explicit: bool = False,
    replacement_note: bool = False,
) -> float:
    confidence = _confidence_for_source(source)
    confidence += 0.05 if explicit else 0.0
    confidence -= 0.05 if replacement_note else 0.0
    confidence += {
        "final": 0.0,
        "ambiguous": -0.08,
        "comparison": -0.15,
        "trial": -0.2,
        "rejected": -0.3,
    }[candidate_role]
    return round(max(0.0, min(confidence, 1.0)), 2)


def _parse_mobile_phase_text(text: str) -> MobilePhase:
    cleaned_text = _normalize_mobile_phase_text(_clean_text(text))
    additive_text = _extract_additive_text(cleaned_text)
    ph_match = PH_PATTERN.search(cleaned_text)
    return MobilePhase(
        solvent=_collapse_whitespace(_extract_solvent_text(cleaned_text)),
        additive=_collapse_whitespace(additive_text) if additive_text else None,
        ph_estimate=(float(ph_match.group("value")) if ph_match is not None else None),
    )


def _extract_gradient_candidates(
    sources: list[_TextSource],
) -> list[ExtractedGradientCandidate]:
    candidates: list[ExtractedGradientCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()

    for source in sources:
        for sentence in _split_sentences(source.cleaned_text):
            candidate = _extract_sentence_gradient_candidate(sentence, source)
            if candidate is not None:
                _append_gradient_candidate(candidates, seen_keys, candidate)

        for candidate in _extract_table_gradient_candidates(source):
            _append_gradient_candidate(candidates, seen_keys, candidate)

    candidates.sort(key=_gradient_candidate_sort_key, reverse=True)
    selected_candidate = _select_gradient_candidate(candidates)
    if selected_candidate is not None:
        selected_candidate.selected_for_method_parameters = True
    return candidates


def _extract_sentence_gradient_candidate(
    sentence: str, source: _TextSource
) -> ExtractedGradientCandidate | None:
    match = GRADIENT_PATTERN.search(sentence)
    if match is not None:
        exact_text = _clean_text(sentence[match.start() : match.end()])
        gradient_profile = _build_gradient_profile_from_match(match)
    else:
        match_verbose = VERBOSE_GRADIENT_PATTERN.search(sentence)
        if match_verbose is not None:
            exact_text = _clean_text(sentence[match_verbose.start() : match_verbose.end()])
            gradient_profile = _build_gradient_profile_from_verbose_match(match_verbose)
        else:
            gradient_profile = _parse_tuple_gradient_profile(sentence)
            if not gradient_profile:
                return None
            exact_text = _clean_text(sentence)

    snippet = EvidenceSnippet(
        text=_collapse_whitespace(sentence),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    candidate_role = _classify_full_system_candidate_role(sentence, source)
    return ExtractedGradientCandidate(
        candidate_kind="text_statement",
        candidate_role=candidate_role,
        statement_text=exact_text,
        confidence=_gradient_candidate_confidence(source, candidate_role),
        gradient_profile=gradient_profile,
        evidence_snippets=[snippet],
    )


def _build_gradient_profile_from_verbose_match(match: re.Match) -> list[GradientPoint]:
    steps_text = match.group("steps")
    # Matches "10 % ... B for 10 min"
    step_pattern = re.compile(
        r"(?P<percent>\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:of\s+)?(?:solvent|phase|eluent)?\s*B\s*(?:for|over)\s*(?P<time>\d+(?:\.\d+)?)\s*min",
        re.IGNORECASE,
    )
    profile: list[GradientPoint] = []
    current_time = 0.0
    for step_match in step_pattern.finditer(steps_text):
        percent = float(step_match.group("percent"))
        duration = float(step_match.group("time"))
        profile.append(GradientPoint(time_min=current_time, percent_b=percent))
        current_time += duration
        profile.append(GradientPoint(time_min=current_time, percent_b=percent))
    return profile


def _extract_table_gradient_candidates(
    source: _TextSource,
) -> list[ExtractedGradientCandidate]:
    candidates: list[ExtractedGradientCandidate] = []
    for block_lines in _iter_table_blocks(source):
        candidate = _parse_gradient_table_block(block_lines, source)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _parse_gradient_table_block(
    block_lines: list[str], source: _TextSource
) -> ExtractedGradientCandidate | None:
    block_text = "\n".join(block_lines)
    normalized_block = block_text.lower()
    has_gradient_hint = any(
        hint in normalized_block
        for hint in ("gradient", "%b", "eluentb", "time(min)", "time (min)")
    )
    if not has_gradient_hint:
        return None

    header_lines, data_lines = _extract_table_header_and_data_lines(
        block_lines, _is_gradient_table_header_line
    )
    if not header_lines:
        return None

    time_index = _find_table_header_index(header_lines, _is_time_table_header)
    percent_b_index = _find_table_header_index(header_lines, _is_percent_b_table_header)
    if time_index is None or percent_b_index is None:
        return None

    rows = _chunk_table_rows(data_lines, len(header_lines))
    if len(rows) < 2:
        return None

    gradient_points: list[GradientPoint] = []
    for row in rows:
        time_value = _extract_table_cell_float(row[time_index])
        percent_b_value = _extract_table_cell_float(row[percent_b_index])
        if time_value is None or percent_b_value is None:
            continue
        gradient_points.append(
            GradientPoint(time_min=time_value, percent_b=percent_b_value)
        )
    if len(gradient_points) < 2:
        return None

    candidate_role = _classify_gradient_table_candidate_role(block_text, source)
    snippet = EvidenceSnippet(
        text=_collapse_whitespace("\n".join(block_lines[:80])),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    return ExtractedGradientCandidate(
        candidate_kind="table_derived",
        candidate_role=candidate_role,
        statement_text=snippet.text,
        confidence=_gradient_candidate_confidence(
            source, candidate_role, table_derived=True
        ),
        gradient_profile=gradient_points,
        evidence_snippets=[snippet],
    )


def _append_gradient_candidate(
    candidates: list[ExtractedGradientCandidate],
    seen_keys: set[tuple[object, ...]],
    candidate: ExtractedGradientCandidate,
) -> None:
    dedupe_key = (
        candidate.candidate_kind,
        tuple(
            (point.time_min, point.percent_b) for point in candidate.gradient_profile
        ),
        candidate.candidate_role,
    )
    if dedupe_key in seen_keys:
        return
    seen_keys.add(dedupe_key)
    candidates.append(candidate)


def _gradient_candidate_sort_key(
    candidate: ExtractedGradientCandidate,
) -> tuple[int, float, int]:
    kind_priority = 1 if candidate.candidate_kind == "text_statement" else 0
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    return (
        kind_priority * 10 + role_priority,
        candidate.confidence,
        len(candidate.gradient_profile),
    )


def _select_gradient_candidate(
    candidates: list[ExtractedGradientCandidate],
) -> ExtractedGradientCandidate | None:
    eligible_candidates = [
        candidate
        for candidate in candidates
        if candidate.candidate_role in {"final", "ambiguous"}
        and candidate.gradient_profile
    ]
    if not eligible_candidates:
        return None
    return max(eligible_candidates, key=_gradient_candidate_sort_key)


def _record_selected_gradient_evidence(
    candidate: ExtractedGradientCandidate,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> None:
    if not candidate.evidence_snippets:
        return
    _record_existing_snippet_evidence(
        field_evidence,
        provenance_snippets,
        "method_parameters.gradient_profile",
        candidate.evidence_snippets[0],
        candidate.confidence,
    )


def _extract_timing_candidates(
    sources: list[_TextSource],
    gradient_candidates: list[ExtractedGradientCandidate],
) -> list[ExtractedTimingCandidate]:
    candidates: list[ExtractedTimingCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()

    for source in sources:
        for sentence in _split_sentences(source.cleaned_text):
            match = RUN_TIME_PATTERN.search(sentence)
            if match is None:
                continue
            snippet = EvidenceSnippet(
                text=_collapse_whitespace(sentence),
                page_number=source.page_number,
                section_label=source.section_label,
            )
            candidate_role = _classify_full_system_candidate_role(sentence, source)
            candidate = ExtractedTimingCandidate(
                candidate_kind="run_time_statement",
                candidate_role=candidate_role,
                statement_text=snippet.text,
                confidence=_timing_candidate_confidence(source, candidate_role),
                run_time_min=float(match.group("value")),
                evidence_snippets=[snippet],
            )
            dedupe_key = (
                candidate.candidate_kind,
                candidate.run_time_min,
                candidate.candidate_role,
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            candidates.append(candidate)

    for gradient_candidate in gradient_candidates:
        if not gradient_candidate.gradient_profile:
            continue
        run_time_min = gradient_candidate.gradient_profile[-1].time_min
        reequilibration_time_min = _infer_reequilibration_time(gradient_candidate)
        if run_time_min <= 0:
            continue
        candidate = ExtractedTimingCandidate(
            candidate_kind="gradient_derived",
            candidate_role=gradient_candidate.candidate_role,
            statement_text=gradient_candidate.statement_text,
            confidence=max(0.0, gradient_candidate.confidence - 0.05),
            run_time_min=run_time_min,
            reequilibration_time_min=reequilibration_time_min,
            evidence_snippets=gradient_candidate.evidence_snippets,
        )
        dedupe_key = (
            candidate.candidate_kind,
            candidate.run_time_min,
            candidate.reequilibration_time_min,
            candidate.candidate_role,
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        candidates.append(candidate)

    candidates.sort(key=_timing_candidate_sort_key, reverse=True)
    selected_candidate = _select_timing_candidate(candidates)
    if selected_candidate is not None:
        selected_candidate.selected_for_method_parameters = True
    return candidates


def _timing_candidate_sort_key(
    candidate: ExtractedTimingCandidate,
) -> tuple[int, float]:
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    kind_priority = 1 if candidate.candidate_kind == "run_time_statement" else 0
    return (role_priority * 10 + kind_priority, candidate.confidence)


def _select_timing_candidate(
    candidates: list[ExtractedTimingCandidate],
) -> ExtractedTimingCandidate | None:
    eligible_candidates = [
        candidate
        for candidate in candidates
        if candidate.candidate_role in {"final", "ambiguous"}
        and candidate.run_time_min is not None
    ]
    if not eligible_candidates:
        return None
    return max(eligible_candidates, key=_timing_candidate_sort_key)


def _record_selected_timing_evidence(
    candidate: ExtractedTimingCandidate,
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> None:
    if not candidate.evidence_snippets:
        return
    _record_existing_snippet_evidence(
        field_evidence,
        provenance_snippets,
        "method_parameters.run_time_min",
        candidate.evidence_snippets[0],
        candidate.confidence,
    )


def _timing_candidate_confidence(
    source: _TextSource, candidate_role: MobilePhaseCandidateRole
) -> float:
    confidence = _confidence_for_source(source)
    confidence += {
        "final": 0.0,
        "ambiguous": -0.08,
        "comparison": -0.15,
        "trial": -0.2,
        "rejected": -0.3,
    }[candidate_role]
    return round(max(0.0, min(confidence, 1.0)), 2)


def _infer_reequilibration_time(
    candidate: ExtractedGradientCandidate,
) -> float | None:
    if len(candidate.gradient_profile) < 3:
        return None
    last_point = candidate.gradient_profile[-1]
    previous_point = candidate.gradient_profile[-2]
    if last_point.percent_b != candidate.gradient_profile[0].percent_b:
        return None
    return round(last_point.time_min - previous_point.time_min, 3)


def _extract_anchored_entity_candidates(
    retention_time_observations: list[ExtractedRetentionTimeObservation],
) -> list[AnchoredEntityCandidate]:
    candidates: list[AnchoredEntityCandidate] = []
    seen_keys: set[tuple[object, ...]] = set()
    for observation in retention_time_observations:
        if observation.local_identifier is None:
            continue
        dedupe_key = (
            observation.local_identifier.lower(),
            observation.observed_retention_time_min,
            observation.candidate_role,
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        confidence = observation.confidence or 0.0
        candidates.append(
            AnchoredEntityCandidate(
                candidate_kind="retention_sentence",
                candidate_role=observation.candidate_role,
                alias_group_key=_entity_alias_group_key(observation.local_identifier),
                local_identifier=observation.local_identifier,
                display_name=observation.local_identifier,
                observed_retention_time_min=observation.observed_retention_time_min,
                confidence=confidence,
                selected_for_record_draft=observation.selected_for_record_draft,
                evidence_snippets=observation.evidence_snippets,
            )
        )
    candidates.sort(key=_anchored_entity_candidate_sort_key, reverse=True)
    return candidates


def _build_molecular_entity_drafts(
    anchored_entity_candidates: list[AnchoredEntityCandidate],
) -> list[HplcMolecularEntityDraft]:
    grouped_candidates: dict[str, list[AnchoredEntityCandidate]] = {}
    for candidate in anchored_entity_candidates:
        grouped_candidates.setdefault(candidate.alias_group_key, []).append(candidate)

    grouped_candidates = _merge_generic_anchor_groups(grouped_candidates)

    drafts: list[HplcMolecularEntityDraft] = []
    for alias_group_key, candidates in grouped_candidates.items():
        sorted_candidates = sorted(
            candidates, key=_anchored_entity_candidate_sort_key, reverse=True
        )
        primary_candidate = _select_primary_anchor_candidate(sorted_candidates)
        aliases = sorted(
            {candidate.local_identifier for candidate in sorted_candidates}
        )
        selected_for_record_draft = any(
            candidate.selected_for_record_draft for candidate in sorted_candidates
        )
        confidence = round(
            sum(candidate.confidence for candidate in sorted_candidates)
            / len(sorted_candidates),
            2,
        )
        placeholder_smiles_string = _build_placeholder_smiles_string(primary_candidate)
        smiles_linkage_status: SmilesLinkageStatus = _infer_smiles_linkage_status(
            primary_candidate
        )
        evidence_snippets = [
            snippet
            for candidate in sorted_candidates
            for snippet in candidate.evidence_snippets
        ]
        drafts.append(
            HplcMolecularEntityDraft(
                local_identifier=_canonical_local_identifier(primary_candidate),
                aliases=aliases,
                linkage_lookup_keys=_build_smiles_lookup_keys(
                    primary_candidate, aliases
                ),
                linkage_notes=_build_linkage_notes(primary_candidate, aliases),
                display_name=_display_name_for_anchor(primary_candidate),
                observed_retention_time_min=primary_candidate.observed_retention_time_min,
                placeholder_smiles_string=placeholder_smiles_string,
                smiles_linkage_status=smiles_linkage_status,
                confidence=confidence,
                selected_for_record_draft=selected_for_record_draft,
                ready_for_retrieval_entity=False,
                evidence_snippets=evidence_snippets,
            )
        )
    drafts.sort(
        key=lambda draft: (
            1 if draft.selected_for_record_draft else 0,
            draft.confidence,
        ),
        reverse=True,
    )
    return drafts


def _select_primary_anchor_candidate(
    candidates: list[AnchoredEntityCandidate],
) -> AnchoredEntityCandidate:
    specific_candidates = [
        candidate
        for candidate in candidates
        if not _is_generic_entity_label(candidate.local_identifier)
    ]
    if specific_candidates:
        return specific_candidates[0]
    return candidates[0]


def _canonical_local_identifier(candidate: AnchoredEntityCandidate) -> str:
    label = candidate.local_identifier
    return _canonical_local_identifier_text(label)


def _canonical_local_identifier_text(label: str) -> str:
    coded_match = re.match(
        r"^(?:compound|intermediate|product|impurity)\s+(?P<code>[A-Za-z0-9-]+)$",
        label,
        re.IGNORECASE,
    )
    if coded_match is not None:
        return _clean_text(coded_match.group("code"))
    return label


def _display_name_for_anchor(candidate: AnchoredEntityCandidate) -> str | None:
    if _is_generic_entity_label(candidate.local_identifier):
        return None
    return candidate.display_name or candidate.local_identifier


def _build_smiles_lookup_keys(
    primary_candidate: AnchoredEntityCandidate, aliases: list[str]
) -> list[str]:
    lookup_keys: list[str] = []
    candidates = [
        primary_candidate.local_identifier,
        _canonical_local_identifier(primary_candidate),
        primary_candidate.alias_group_key,
        *aliases,
    ]
    for candidate in candidates:
        for key_variant in _lookup_key_variants(candidate):
            if key_variant not in lookup_keys:
                lookup_keys.append(key_variant)
    return lookup_keys


def _lookup_key_variants(value: str) -> list[str]:
    cleaned_value = _clean_text(value)
    if not cleaned_value:
        return []
    normalized_value = cleaned_value.lower()
    normalized_value = re.sub(r"\s+", " ", normalized_value)
    variants = [normalized_value]
    if "-" in normalized_value:
        variants.append(normalized_value.replace("-", " "))
    if " " in normalized_value:
        variants.append(normalized_value.replace(" ", "-"))
    if _looks_like_code_identifier(cleaned_value):
        variants.append(_canonical_local_identifier_text(cleaned_value).lower())
    deduped: list[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


def _build_linkage_notes(
    primary_candidate: AnchoredEntityCandidate, aliases: list[str]
) -> list[str]:
    notes: list[str] = []
    if any(_is_generic_entity_label(alias) for alias in aliases):
        notes.append("generic co-reference aliases were merged into this entity draft")
    if _looks_like_code_identifier(primary_candidate.local_identifier):
        notes.append(
            "use local identifier and scheme labels first when linking future molecule sources"
        )
    else:
        notes.append(
            "use normalized name aliases first when linking future molecule sources"
        )
    return notes


def _build_placeholder_smiles_string(candidate: AnchoredEntityCandidate) -> str:
    alias_key = candidate.alias_group_key.replace(" ", "-")
    return f"UNRESOLVED::{alias_key}"


def _infer_smiles_linkage_status(
    candidate: AnchoredEntityCandidate,
) -> SmilesLinkageStatus:
    if _looks_like_code_identifier(candidate.local_identifier):
        return cast(SmilesLinkageStatus, "unresolved_local_identifier")
    if _is_generic_entity_label(candidate.local_identifier):
        return cast(SmilesLinkageStatus, "placeholder_generated")
    return cast(SmilesLinkageStatus, "unresolved_named_entity")


def _entity_alias_group_key(local_identifier: str) -> str:
    normalized = _clean_text(local_identifier).lower()
    normalized = re.sub(r"^the\s+", "", normalized)
    normalized = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", normalized)
    coded_match = re.match(
        r"^(?:compound|intermediate|product|impurity)\s+(?P<code>[A-Za-z0-9-]+)$",
        normalized,
    )
    if coded_match is not None:
        return coded_match.group("code")
    if _is_generic_entity_label(normalized):
        return normalized
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _is_generic_entity_label(local_identifier: str) -> bool:
    normalized = re.sub(r"^the\s+", "", _clean_text(local_identifier).lower())
    return normalized in {
        "target compound",
        "target analyte",
        "analyte",
        "product",
        "desired product",
        "desired isomer",
        "main peak",
        "major peak",
        "minor peak",
        "principal peak",
        "main product",
        "api",
        "standard",
    }


def _looks_like_code_identifier(local_identifier: str) -> bool:
    normalized = _clean_text(local_identifier)
    if re.fullmatch(r"[A-Za-z]?\d+[A-Za-z0-9-]*", normalized):
        return True
    if re.fullmatch(
        r"(?:compound|intermediate|product|impurity)\s+[A-Za-z0-9-]+",
        normalized,
        re.IGNORECASE,
    ):
        return True
    return False


def _merge_generic_anchor_groups(
    grouped_candidates: dict[str, list[AnchoredEntityCandidate]],
) -> dict[str, list[AnchoredEntityCandidate]]:
    merged_groups = {key: list(value) for key, value in grouped_candidates.items()}
    generic_keys = [key for key in list(merged_groups) if _is_generic_entity_label(key)]
    for generic_key in generic_keys:
        generic_group = merged_groups.get(generic_key)
        if not generic_group:
            continue
        target_key = _find_specific_anchor_group_for_generic(generic_key, merged_groups)
        if target_key is None or target_key == generic_key:
            continue
        merged_groups.setdefault(target_key, []).extend(generic_group)
        del merged_groups[generic_key]
    return merged_groups


def _find_specific_anchor_group_for_generic(
    generic_key: str,
    grouped_candidates: dict[str, list[AnchoredEntityCandidate]],
) -> str | None:
    generic_group = grouped_candidates.get(generic_key, [])
    if not generic_group:
        return None
    generic_times = {
        candidate.observed_retention_time_min
        for candidate in generic_group
        if candidate.observed_retention_time_min is not None
    }
    selected_time_matches = [
        candidate_key
        for candidate_key, candidates in grouped_candidates.items()
        if candidate_key != generic_key
        and not _is_generic_entity_label(candidate_key)
        and any(candidate.selected_for_record_draft for candidate in candidates)
        and (
            not generic_times
            or {
                candidate.observed_retention_time_min
                for candidate in candidates
                if candidate.observed_retention_time_min is not None
            }
            & generic_times
        )
    ]
    if len(selected_time_matches) == 1:
        return selected_time_matches[0]

    selected_specific_groups = [
        candidate_key
        for candidate_key, candidates in grouped_candidates.items()
        if candidate_key != generic_key
        and not _is_generic_entity_label(candidate_key)
        and any(candidate.selected_for_record_draft for candidate in candidates)
    ]
    if len(selected_specific_groups) == 1:
        return selected_specific_groups[0]

    best_target: str | None = None
    best_score = -1.0
    for candidate_key, candidates in grouped_candidates.items():
        if candidate_key == generic_key or _is_generic_entity_label(candidate_key):
            continue
        candidate_times = {
            candidate.observed_retention_time_min
            for candidate in candidates
            if candidate.observed_retention_time_min is not None
        }
        if generic_times and candidate_times and not (generic_times & candidate_times):
            continue
        score = max(candidate.confidence for candidate in candidates)
        if any(candidate.selected_for_record_draft for candidate in candidates):
            score += 1.0
        if score > best_score:
            best_score = score
            best_target = candidate_key
    return best_target


def _anchored_entity_candidate_sort_key(
    candidate: AnchoredEntityCandidate,
) -> tuple[int, float]:
    role_priority = {
        "final": 4,
        "ambiguous": 3,
        "comparison": 2,
        "trial": 1,
        "rejected": 0,
    }[candidate.candidate_role]
    return (role_priority, candidate.confidence)


def _classify_gradient_table_candidate_role(
    text: str, source: _TextSource
) -> MobilePhaseCandidateRole:
    normalized = text.lower()
    if (
        "optimization" in normalized
        or "screen" in normalized
        or "candidate" in normalized
    ):
        return "trial"
    return _classify_full_system_candidate_role(text, source)


def _gradient_candidate_confidence(
    source: _TextSource,
    candidate_role: MobilePhaseCandidateRole,
    *,
    table_derived: bool = False,
) -> float:
    confidence = _confidence_for_source(source)
    confidence -= 0.05 if table_derived else 0.0
    confidence += {
        "final": 0.0,
        "ambiguous": -0.08,
        "comparison": -0.15,
        "trial": -0.2,
        "rejected": -0.3,
    }[candidate_role]
    return round(max(0.0, min(confidence, 1.0)), 2)


def _build_gradient_profile_from_match(match: re.Match[str]) -> list[GradientPoint]:
    start_percent_b = _parse_match_float(match, "start")
    end_percent_b = _parse_match_float(match, "end")
    ramp_time = _parse_match_float(match, "ramp")
    hold_time = _parse_optional_match_float(match, "hold")
    reequilibration_time = _parse_optional_match_float(match, "reequil")
    points = [
        GradientPoint(time_min=0.0, percent_b=start_percent_b),
        GradientPoint(time_min=ramp_time, percent_b=end_percent_b),
    ]
    if hold_time is not None:
        points.append(
            GradientPoint(time_min=ramp_time + hold_time, percent_b=end_percent_b)
        )
    if reequilibration_time is not None:
        last_time = points[-1].time_min
        points.append(
            GradientPoint(
                time_min=last_time + reequilibration_time,
                percent_b=start_percent_b,
            )
        )
    return points


def _extract_retention_time_observations(
    sources: list[_TextSource],
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
) -> list[ExtractedRetentionTimeObservation]:
    observations: list[ExtractedRetentionTimeObservation] = []
    seen_values: set[tuple[float, str | None, MobilePhaseCandidateRole]] = set()
    for source in sources:
        for sentence in _split_sentences(source.cleaned_text):
            match = RETENTION_TIME_PATTERN.search(sentence)
            if match is None:
                match = PEAK_TIME_PATTERN.search(sentence)
            if match is None:
                continue
            retention_time = float(match.group("value"))
            local_identifier = _infer_retention_time_label(sentence)
            candidate_role = _classify_retention_time_role(sentence, source)
            selected_for_record_draft = _should_select_retention_observation(
                candidate_role, source
            )
            key = (retention_time, local_identifier, candidate_role)
            if key in seen_values:
                continue
            seen_values.add(key)
            snippet = EvidenceSnippet(
                text=_collapse_whitespace(sentence),
                page_number=source.page_number,
                section_label=source.section_label,
            )
            confidence = _confidence_for_source(source)
            observations.append(
                ExtractedRetentionTimeObservation(
                    local_identifier=local_identifier,
                    observed_retention_time_min=retention_time,
                    confidence=confidence,
                    candidate_role=candidate_role,
                    selected_for_record_draft=selected_for_record_draft,
                    evidence_snippets=[snippet],
                )
            )
            field_evidence.append(
                ExtractedFieldEvidence(
                    field_path="retention_time_observations",
                    confidence=confidence,
                    snippet=snippet,
                )
            )
            provenance_snippets.append(snippet)

        for observation in _extract_table_retention_observations(source):
            key = (
                observation.observed_retention_time_min,
                observation.local_identifier,
                observation.candidate_role,
            )
            if key in seen_values:
                continue
            seen_values.add(key)
            observations.append(observation)
            confidence = observation.confidence or _confidence_for_source(source)
            snippet = observation.evidence_snippets[0]
            field_evidence.append(
                ExtractedFieldEvidence(
                    field_path="retention_time_observations",
                    confidence=confidence,
                    snippet=snippet,
                )
            )
            provenance_snippets.append(snippet)

        for observation in _extract_inline_retention_table_observations(source):
            key = (
                observation.observed_retention_time_min,
                observation.local_identifier,
                observation.candidate_role,
            )
            if key in seen_values:
                continue
            seen_values.add(key)
            observations.append(observation)
            confidence = observation.confidence or _confidence_for_source(source)
            snippet = observation.evidence_snippets[0]
            field_evidence.append(
                ExtractedFieldEvidence(
                    field_path="retention_time_observations",
                    confidence=confidence,
                    snippet=snippet,
                )
            )
            provenance_snippets.append(snippet)
    return observations


def _extract_table_retention_observations(
    source: _TextSource,
) -> list[ExtractedRetentionTimeObservation]:
    observations: list[ExtractedRetentionTimeObservation] = []
    for block_lines in _iter_table_blocks(source):
        observations.extend(_parse_retention_table_block(block_lines, source))
    return observations


def _extract_inline_retention_table_observations(
    source: _TextSource,
) -> list[ExtractedRetentionTimeObservation]:
    normalized_text = source.cleaned_text.lower()
    if not any(
        marker in normalized_text
        for marker in ("rt", "retention", "quantification transition", "table 2")
    ):
        return []

    observations: list[ExtractedRetentionTimeObservation] = []
    rows: list[tuple[str, float]] = []
    body_text = source.cleaned_text
    header_match = re.search(
        r"Analyte\s+Rt\s*\(?min\)?\s+DP\s*\(?V\)?\s+EP\s*\(?V\)?\s+CXP\s*\(?V\)?\s+Quantification\s+Transition\s+CE",
        source.cleaned_text,
        re.IGNORECASE,
    )
    if header_match is not None:
        body_text = source.cleaned_text[header_match.end() :]
    row_pattern = re.compile(
        r"(?P<label>[A-Za-z0-9α-ωΑ-Ωβγδεζηθικλμνξοπρστυφχψω'\-()\s/.,]+?)\s+(?P<rt>\d+(?:\.\d+)?)\s+\d+\s+\d+\s+\d+\s+\d+\s*(?:→|->)\s*\d+\s+\d+",
        re.IGNORECASE,
    )
    for row_match in row_pattern.finditer(body_text):
        label = _collapse_whitespace(row_match.group("label"))
        retention_time = float(row_match.group("rt"))
        if len(label) > 80 or not _is_probable_retention_table_label(label):
            continue
        if retention_time <= 0 or retention_time > 120:
            continue
        rows.append((label, retention_time))

    if len(rows) < 3:
        return []

    candidate_role = _classify_gradient_table_candidate_role(source.cleaned_text, source)
    selected_for_record_draft = _should_select_retention_observation(
        candidate_role, source
    )
    confidence = max(0.0, round(_confidence_for_source(source) - 0.08, 2))
    snippet_text = _collapse_whitespace("\n".join(_split_nonempty_lines(source.cleaned_text)[:80]))
    snippet = EvidenceSnippet(
        text=snippet_text[:4000],
        page_number=source.page_number,
        section_label=source.section_label,
    )
    for label, value in rows:
        observations.append(
            ExtractedRetentionTimeObservation(
                local_identifier=label,
                observed_retention_time_min=value,
                confidence=confidence,
                candidate_role=candidate_role,
                selected_for_record_draft=selected_for_record_draft,
                evidence_snippets=[snippet],
            )
        )
    return observations


def _parse_retention_table_block(
    block_lines: list[str], source: _TextSource
) -> list[ExtractedRetentionTimeObservation]:
    block_text = "\n".join(block_lines)
    normalized_block = block_text.lower()
    if "retention" not in normalized_block or "time" not in normalized_block:
        return []
    if not any(
        token in normalized_block
        for token in ("analyte", "compound", "peak", "impurity", "product")
    ):
        return []

    header_lines, data_lines = _extract_table_header_and_data_lines(
        block_lines, _is_retention_table_header_line
    )
    if not header_lines:
        return []

    label_index = _find_label_table_header_index(header_lines)
    time_index = _find_table_header_index(header_lines, _is_retention_time_table_header)
    if label_index is None or time_index is None:
        return []

    rows = _parse_retention_table_rows(
        data_lines, len(header_lines), label_index, time_index
    )
    if not rows:
        return []

    candidate_role = _classify_gradient_table_candidate_role(block_text, source)
    selected_for_record_draft = _should_select_retention_observation(
        candidate_role, source
    )
    confidence = max(0.0, round(_confidence_for_source(source) - 0.05, 2))
    snippet = EvidenceSnippet(
        text=_collapse_whitespace(block_text),
        page_number=source.page_number,
        section_label=source.section_label,
    )
    return [
        ExtractedRetentionTimeObservation(
            local_identifier=label,
            observed_retention_time_min=value,
            confidence=confidence,
            candidate_role=candidate_role,
            selected_for_record_draft=selected_for_record_draft,
            evidence_snippets=[snippet],
        )
        for label, value in rows
    ]


def _parse_retention_table_rows(
    data_lines: list[str], row_width: int, label_index: int, time_index: int
) -> list[tuple[str, float]]:
    scanned_rows = _parse_retention_table_rows_by_label_time_scan(data_lines)
    if scanned_rows:
        return scanned_rows

    rows: list[tuple[str, float]] = []
    for row in _chunk_table_rows(data_lines, row_width):
        label = _collapse_whitespace(row[label_index])
        time_value = _extract_table_cell_float(row[time_index])
        if (
            not label
            or time_value is None
            or not _is_probable_retention_table_label(label)
        ):
            continue
        rows.append((label, time_value))
    return rows


def _parse_retention_table_rows_by_label_time_scan(
    data_lines: list[str],
) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    index = 0
    while index + 1 < len(data_lines):
        label = _clean_text(data_lines[index])
        time_value = _extract_table_cell_float(data_lines[index + 1])
        if (
            label
            and time_value is not None
            and _is_probable_retention_table_label(label)
        ):
            rows.append((label, time_value))
            index += 2
            while index < len(data_lines):
                next_label = _clean_text(data_lines[index])
                next_time_value = (
                    _extract_table_cell_float(data_lines[index + 1])
                    if index + 1 < len(data_lines)
                    else None
                )
                if (
                    next_label
                    and next_time_value is not None
                    and _is_probable_retention_table_label(next_label)
                ):
                    break
                index += 1
            continue
        index += 1
    return rows


def _iter_table_blocks(source: _TextSource) -> list[list[str]]:
    lines = _split_nonempty_lines(source.text)
    blocks: list[list[str]] = []
    for index, line in enumerate(lines):
        if "table" not in line.lower():
            continue
        block_lines = [line]
        for next_line in lines[index + 1 : index + 200]:
            lower_line = next_line.lower()
            if (
                block_lines
                and len(block_lines) > 1
                and _is_table_boundary_line(lower_line)
            ):
                break
            block_lines.append(next_line)
        blocks.append(block_lines)
    return blocks


def _is_table_boundary_line(lower_line: str) -> bool:
    return (
        lower_line.startswith("table ")
        or lower_line.startswith("fig")
        or lower_line.startswith("supplement")
    )


def _is_retention_table_header_line(lower_line: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", lower_line).strip()
    if normalized in {
        "analyte",
        "compound",
        "compound id",
        "peak",
        "peak id",
        "retention time",
        "retention time min",
        "tr",
        "tr min",
        "t r",
        "t r min",
        "rt",
        "rt min",
        "time",
        "time min",
        "min",
    }:
        return True
    return (
        "retention time" in normalized
        or normalized.endswith(" time min")
        or normalized.endswith(" rt min")
    )


def _is_gradient_table_header_line(lower_line: str) -> bool:
    normalized = re.sub(r"[^a-z0-9%]+", " ", lower_line).strip()
    return normalized in {
        "step",
        "program step",
        "time",
        "time min",
        "%a",
        "%b",
        "a %",
        "b %",
        "eluenta",
        "eluent a",
        "eluentb",
        "eluent b",
    }


def _is_time_table_header(line: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
    return normalized in {"time", "time min"}


def _is_percent_b_table_header(line: str) -> bool:
    normalized = line.lower().replace(" ", "")
    normalized = normalized.replace("(", "").replace(")", "")
    return normalized in {"%b", "b%", "eluentb", "eluentb%"}


def _is_label_table_header(line: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
    return normalized in {
        "analyte",
        "compound",
        "compound id",
        "product",
        "impurity",
        "peak",
        "peak id",
    }


def _find_label_table_header_index(header_lines: list[str]) -> int | None:
    preferred_labels = {
        "analyte",
        "compound",
        "compound id",
        "product",
        "impurity",
    }
    for index, header_line in enumerate(header_lines):
        normalized = re.sub(r"[^a-z0-9]+", " ", header_line.lower()).strip()
        if normalized in preferred_labels:
            return index
    return _find_table_header_index(header_lines, _is_label_table_header)


def _is_retention_time_table_header(line: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
    return normalized in {
        "retention time",
        "retention time min",
        "tr",
        "tr min",
        "t r",
        "t r min",
        "rt",
        "rt min",
        "time",
        "time min",
        "min",
    }


def _extract_table_header_and_data_lines(
    block_lines: list[str], is_header_line: Callable[[str], bool]
) -> tuple[list[str], list[str]]:
    header_lines: list[str] = []
    data_lines: list[str] = []
    header_started = False
    data_started = False
    for line in block_lines[1:]:
        lower_line = line.lower()
        if lower_line.startswith("table ") and not header_started:
            continue
        if _is_table_boundary_line(lower_line):
            break
        if not header_started:
            if is_header_line(lower_line):
                header_started = True
                header_lines.append(line)
            continue
        if not data_started and is_header_line(lower_line):
            header_lines.append(line)
            continue
        if data_started and _looks_like_table_tail_narrative(line):
            break
        data_started = True
        data_lines.append(line)
    return (header_lines, data_lines)


def _find_table_header_index(
    header_lines: list[str], predicate: Callable[[str], bool]
) -> int | None:
    for index, header_line in enumerate(header_lines):
        if predicate(header_line):
            return index
    return None


def _chunk_table_rows(data_lines: list[str], row_width: int) -> list[list[str]]:
    if row_width <= 0:
        return []
    usable_value_count = len(data_lines) - (len(data_lines) % row_width)
    if usable_value_count < row_width * 2:
        return []
    return [
        data_lines[offset : offset + row_width]
        for offset in range(0, usable_value_count, row_width)
    ]


def _extract_table_cell_float(value: str) -> float | None:
    match = TABLE_NUMERIC_VALUE_PATTERN.search(value)
    if match is None:
        return None
    return float(match.group(0))


def _looks_like_table_tail_narrative(line: str) -> bool:
    words = line.split()
    if len(words) < 5:
        return False
    return bool(re.search(r"[.!?;:]", line))


def _is_probable_retention_table_label(line: str) -> bool:
    lowered = line.lower()
    if _is_retention_table_header_line(lowered):
        return False
    return bool(re.search(r"[A-Za-z]", line))


def _record_field_evidence(
    field_evidence: list[ExtractedFieldEvidence],
    provenance_snippets: list[EvidenceSnippet],
    field_path: str,
    source: _TextSource,
    start_index: int,
    end_index: int,
) -> None:
    snippet = _build_snippet(source, start_index, end_index)
    confidence = _confidence_for_source(source)
    field_evidence.append(
        ExtractedFieldEvidence(
            field_path=field_path,
            confidence=confidence,
            snippet=snippet,
        )
    )
    provenance_snippets.append(snippet)


def _build_snippet(source: _TextSource, start_index: int, end_index: int) -> EvidenceSnippet:
    snippet_start = max(0, start_index - 120)
    snippet_end = min(len(source.text), end_index + 120)
    return EvidenceSnippet(
        text=_collapse_whitespace(source.text[snippet_start:snippet_end]),
        page_number=source.page_number,
        section_label=source.section_label,
    )


def _infer_column_manufacturer(column_label: str) -> str | None:
    tokens = column_label.split()
    if not tokens:
        return None
    return tokens[0]


def _clean_column_label(column_label: str) -> str:
    cleaned_label = _clean_text(column_label)
    cleaned_label = re.sub(
        r"^\d+\s+\d+of\d+\s+", "", cleaned_label, flags=re.IGNORECASE
    )
    cleaned_label = re.sub(r"^\d+of\d+\s+", "", cleaned_label, flags=re.IGNORECASE)
    prefix_match = re.search(
        r"(?:reversed\s+phase\s+column|column\s+used\s+was|column\s+was|separation\s+was\s+performed\s+on\s+(?:a\s+)?)\s+(?P<label>.+)$",
        cleaned_label,
        flags=re.IGNORECASE,
    )
    if prefix_match is not None:
        cleaned_label = _clean_text(prefix_match.group("label"))
    cleaned_label = re.sub(
        r"^separationwasperformedonareversedphasecolumn\s+",
        "",
        cleaned_label,
        flags=re.IGNORECASE,
    )
    cleaned_label = re.sub(r"^(?:a|an|the)\s+", "", cleaned_label, flags=re.IGNORECASE)
    lower_label = cleaned_label.lower()
    for marker in (
        " used a ",
        " used an ",
        " used the ",
        " using a ",
        " using an ",
        " using the ",
        " on a ",
        " on an ",
        " on the ",
    ):
        if marker in lower_label:
            marker_index = lower_label.rfind(marker)
            return _clean_text(cleaned_label[marker_index + len(marker) :])
    return cleaned_label


def _infer_stationary_phase_chemistry(column_label: str) -> str | None:
    normalized = column_label.lower()
    if "carotenoid" in normalized or "c30" in normalized:
        return "carotenoid"
    if "c18" in normalized or "ods" in normalized:
        return "C18"
    if "c8" in normalized:
        return "C8"
    if "hilic" in normalized:
        return "HILIC"
    if "phenyl" in normalized:
        return "phenyl"
    if "amylose" in normalized:
        return "amylose"
    if "cellulose" in normalized:
        return "cellulose"
    return None


def _infer_chromatography_mode(
    stationary_phase_chemistry: str,
) -> ChromatographyMode:
    normalized = stationary_phase_chemistry.lower()
    if normalized == "hilic":
        return cast(ChromatographyMode, "hilic")
    if normalized in {"c18", "c8", "phenyl", "carotenoid"}:
        return cast(ChromatographyMode, "rp_lc")
    return cast(ChromatographyMode, "unknown")


def _infer_solvent(text: str) -> str:
    normalized = text.lower()
    if "me oh" in normalized:
        normalized = normalized.replace("me oh", "meoh")
    if "a cn" in normalized:
        normalized = normalized.replace("a cn", "acn")

    # If it looks like a mixture already (contains ratios or multiple solvents separated by : or /)
    if ":" in text or "/" in text:
        if any(s in normalized for s in ["acetonitrile", "acn", "methanol", "meoh", "water", "aqueous", "dichloromethane", "dcm", "hexane", "isopropanol", "2-propanol"]):
            return _clean_text(text)

    if "mtbe" in normalized or "methyl tert" in normalized:
        return "MTBE"
    if "phosphate" in normalized:
        return "phosphate buffer"
    if "acetonitrile" in normalized or "acn" in normalized:
        return "acetonitrile"
    if "methanol" in normalized or "meoh" in normalized:
        return "methanol"
    if "2-propanol" in normalized or "isopropanol" in normalized:
        return "2-propanol"
    if "water" in normalized or "aqueous" in normalized:
        return "water"
    if "buffer" in normalized:
        return "buffer"
    return text


def _normalize_mobile_phase_text(text: str) -> str:
    normalized = text
    replacements = {
        "AMAC": "ammonium acetate",
        "AA": "acetic acid",
        "MeOH": "methanol",
        "Me OH": "methanol",
        "ACN": "acetonitrile",
        "A CN": "acetonitrile",
        "ofaceticacid": "of acetic acid",
        "offormicacid": "of formic acid",
    }
    for old, new in replacements.items():
        normalized = re.sub(rf"\b{old}\b", new, normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?<=\d)g/[lL]\b", " g/L", normalized)
    normalized = re.sub(r"(?<=\d)%of\b", "% of", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"ammonium\s+acetate\s+at\s+a\s+concentration\s+of\s+(\d+(?:\.\d+)?\s*g/L)",
        r"\1 ammonium acetate",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\bmobile\s*phase\s*[AB]\b", "", normalized, flags=re.IGNORECASE
    )
    normalized = re.sub(r"\beluent\s*[AB]\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\b(?:consisted\s+of|contained)\b", "", normalized, flags=re.IGNORECASE
    )
    return _clean_text(normalized)


def _extract_additive_text(text: str) -> str | None:
    normalized = text.lower()
    ammonium_match = re.search(
        r"(?P<value>\d+(?:\.\d+)?\s*g/[lL]\s*ammonium\s+acetate|ammonium\s+acetate)",
        normalized,
    )
    acid_match = re.search(
        r"(?P<value>\d+(?:\.\d+)?%\s*(?:of\s+)?acetic\s+acid|acetic\s+acid|\d+(?:\.\d+)?%\s*(?:of\s+)?formic\s+acid|formic\s+acid)",
        normalized,
    )
    parts: list[str] = []
    if ammonium_match is not None:
        parts.append(_clean_text(ammonium_match.group("value")))
    if acid_match is not None:
        acid_text = _clean_text(acid_match.group("value"))
        if acid_text not in parts:
            parts.append(acid_text)
    if parts:
        return " and ".join(parts)

    additive_match = ADDITIVE_PATTERN.search(text)
    if additive_match is None:
        return None
    return _clean_text(additive_match.group("additive"))


def _extract_solvent_text(text: str) -> str:
    normalized = text.lower()
    if (
        "mtbe" in normalized or "methyl tert" in normalized
    ) and "methanol" in normalized:
        ratio_match = re.search(
            r"\((?P<ratio>\d+(?::\d+)+)\s*,?\s*v\s*/\s*v\s*\)", text, re.IGNORECASE
        )
        ratio_suffix = (
            f" {ratio_match.group('ratio')}" if ratio_match is not None else ""
        )
        return f"MTBE/methanol{ratio_suffix}".strip()
    if "phosphate" in normalized:
        concentration_match = re.search(
            r"(?P<value>\d+(?:\.\d+)?\s*mM\s+potassium\s+phosphate\s+dibasic)",
            text,
            re.IGNORECASE,
        )
        if concentration_match is not None:
            return f"{_clean_text(concentration_match.group('value'))} buffer"
        return "phosphate buffer"
    if "water" in normalized and (
        "acetonitrile" in normalized or "methanol" in normalized
    ):
        return _infer_solvent(text)
    return _infer_solvent(text)


def _normalize_compact_extraction_text(text: str) -> str:
    normalized = text
    replacements = {
        "Mobilephase": "Mobile phase ",
        "MobilephaseA": "Mobile phase A ",
        "MobilephaseB": "Mobile phase B ",
        "phaseflowrate": "phase flow rate ",
        "Themobile": "The mobile ",
        "EluentA": "Eluent A ",
        "EluentB": "Eluent B ",
        "Aconsisted": "A consisted ",
        "Bcontained": "B contained ",
        "Thefollowingcombinationofmobilephaseswasused": "The following combination of mobile phases was used ",
        "Chromatographicseparationwasperformedonareversedphasecolumn": "Chromatographic separation was performed on a reversed phase column ",
        "MTBEandMeOH": "MTBE and MeOH ",
        "AMACataconcentrationof": "AMAC at a concentration of ",
        "Flowrate": "Flow rate ",
        "Runtime": "Run time ",
        "Totalruntimeofanalysiswas": "Total run time of analysis was ",
        "maintainedat": "maintained at ",
        "Columntemperature": "Column temperature ",
        "ChromatographicConditions": "Chromatographic Conditions ",
        "Optimizationof": "Optimization of ",
        "Thefollowinglineargradientof": "The following linear gradient of ",
        "Thecolumnusedwasa": "The column used was a ",
        "MethodDevelopment": "Method Development ",
        "Resultsanddiscussion": "Results and discussion ",
        "Materialsandmethods": "Materials and methods ",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"(?i)table(?=\d)", "Table ", normalized)
    normalized = re.sub(r"(?i)figure(?=\d)", "Figure ", normalized)
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=\d{2,}\.\d+\b)", " ", normalized)
    return _clean_text(normalized)


def _parse_tuple_gradient_profile(sentence: str) -> list[GradientPoint]:
    normalized = sentence.lower()
    if "gradient" not in normalized:
        return []
    pair_matches = re.findall(
        r"\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)", sentence
    )
    if len(pair_matches) < 2:
        return []
    basis_match = re.search(
        r"%(?P<basis>[ab])|gradient\s+of\s+(?P<basis_word>[ab])", normalized
    )
    if basis_match is None:
        return []
    basis = basis_match.group("basis") or basis_match.group("basis_word")
    gradient_points: list[GradientPoint] = []
    for time_text, percent_text in pair_matches:
        time_min = float(time_text)
        component_percent = float(percent_text)
        percent_b = component_percent if basis == "b" else 100.0 - component_percent
        gradient_points.append(GradientPoint(time_min=time_min, percent_b=percent_b))
    return gradient_points


def _normalize_solvent_reference(text: str) -> str:
    return _infer_solvent(_clean_text(text))


def _infer_retention_time_label(sentence: str) -> str | None:
    explicit_identifier_match = re.search(
        r"\b(?P<label>(?:compound|intermediate|impurity|product)\s+[A-Za-z0-9\-]+|target\s+compound|target\s+analyte|desired\s+product|desired\s+isomer|main\s+peak|major\s+peak|minor\s+peak|principal\s+peak|main\s+product|the\s+product|API|standard)\b",
        sentence,
        re.IGNORECASE,
    )
    if explicit_identifier_match is not None:
        return _clean_text(explicit_identifier_match.group("label"))
    peak_match = re.search(
        r"(?P<label>[A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+){0,3})\s+peak",
        sentence,
        re.IGNORECASE,
    )
    if peak_match is not None:
        return _clean_text(
            re.sub(
                r"^(?:the|a|an)\s+", "", peak_match.group("label"), flags=re.IGNORECASE
            )
        )
    compound_match = re.search(
        r"(?:compound|analyte)\s+(?P<label>[A-Za-z0-9\-]+)",
        sentence,
        re.IGNORECASE,
    )
    if compound_match is not None:
        return _clean_text(compound_match.group("label"))
    return None


def _classify_retention_time_role(
    sentence: str, source: _TextSource
) -> MobilePhaseCandidateRole:
    return _classify_full_system_candidate_role(sentence, source)


def _should_select_retention_observation(
    candidate_role: MobilePhaseCandidateRole, source: _TextSource
) -> bool:
    if candidate_role not in {"final", "ambiguous"}:
        return False
    return source.section_kind in {"methods", "results", "discussion", None}


def _build_retrieval_record_draft(
    *,
    document: RegisteredSourceDocument,
    chromatography_system: ChromatographySystem | None,
    method_parameters: MethodParameters | None,
    provenance: RetrievalProvenance,
    retention_time_observations: list[ExtractedRetentionTimeObservation],
    anchored_entity_candidates: list[AnchoredEntityCandidate],
    molecular_entity_drafts: list[HplcMolecularEntityDraft],
) -> RetrievalRecordDraft | None:
    if chromatography_system is None or method_parameters is None:
        return None

    selected_observations = [
        observation
        for observation in retention_time_observations
        if observation.selected_for_record_draft
    ]
    unresolved_requirements = [
        "molecular entity anchoring and SMILES mapping are still required before RetrievalMethodRecord assembly"
    ]
    if not selected_observations:
        unresolved_requirements.append(
            "no final retention-time observations were selected for the draft"
        )
    elif not any(observation.local_identifier for observation in selected_observations):
        unresolved_requirements.append(
            "selected retention-time observations do not yet carry stable local identifiers"
        )
    if not anchored_entity_candidates:
        unresolved_requirements.append(
            "no anchored entity candidates were produced from local identifiers"
        )
    if not molecular_entity_drafts:
        unresolved_requirements.append(
            "no molecular entity drafts were generated from the anchored entity candidates"
        )
    if not any(draft.ready_for_retrieval_entity for draft in molecular_entity_drafts):
        unresolved_requirements.append(
            "molecular entity drafts still require SMILES linkage before RetrievalMethodRecord assembly"
        )

    return RetrievalRecordDraft(
        record_id=f"draft-{document.source_document.source_document_id}",
        source_document=document.source_document,
        chromatography_system=chromatography_system,
        method_parameters=method_parameters,
        provenance=provenance,
        anchored_entities=anchored_entity_candidates,
        molecular_entity_drafts=molecular_entity_drafts,
        selected_retention_time_observations=selected_observations,
        unresolved_requirements=unresolved_requirements,
        ready_for_record_assembly=False,
    )


def _split_sentences(text: str) -> list[str]:
    return [segment for segment in re.split(r"(?<=[.!?])\s+", text) if segment]


def _split_nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_sentence_context(text: str, start_index: int, end_index: int) -> str:
    # Find the nearest boundary BEFORE start_index
    # We add 1 to the index because rfind returns the position of the character,
    # and we want to start AFTER it.
    sentence_start = max(
        0, text.rfind(".", 0, start_index) + 1, text.rfind("\n", 0, start_index) + 1
    )
    sentence_end_candidates = [
        position
        for position in (text.find(".", end_index), text.find("\n", end_index))
        if position != -1
    ]
    sentence_end = (
        min(sentence_end_candidates) if sentence_end_candidates else len(text)
    )
    return _collapse_whitespace(text[sentence_start:sentence_end])


def _compute_extraction_confidence(
    field_evidence: list[ExtractedFieldEvidence],
) -> float | None:
    if not field_evidence:
        return None
    return round(
        sum(item.confidence for item in field_evidence) / len(field_evidence),
        3,
    )


def _confidence_for_source(source: _TextSource) -> float:
    return round(min(source.priority, 1.0), 2)


def _parse_match_float(match: re.Match[str], group_name: str) -> float:
    raw_value = match.group(group_name)
    return float(raw_value.replace(",", "."))


def _parse_optional_match_float(match: re.Match[str], group_name: str) -> float | None:
    raw_value = match.group(group_name)
    if raw_value is None:
        return None
    return float(raw_value.replace(",", "."))


def _clean_match_group(match: re.Match[str], group_name: str) -> str:
    return _clean_text(match.group(group_name))


def _clean_text(text: str) -> str:
    # Length-preserving normalization for consistent indices.
    # MUST NOT change length or structure (newlines).
    return text.replace("\xa0", " ").replace("·", ".").replace("−", "-")


def _collapse_whitespace(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip(" \n\t")


def _extract_via_llm(
    evidence_units: tuple[EvidenceUnit, ...],
    gemini_client: GeminiOrchestrationClient,
    *,
    request_text: str,
    unresolved_field_groups: tuple[str, ...],
    runtime_tracker: RecommendationRuntimeTracker | None = None,
) -> dict | None:
    if not evidence_units:
        return None
    aggregated: dict[str, object] = {}
    collected_quotes: list[str] = []

    for field_group in unresolved_field_groups:
        selected_units = select_evidence_units(
            evidence_units,
            field_group=cast(
                Literal[
                    "chromatography_system",
                    "mobile_phase_gradient",
                    "detector_ionization",
                    "target_impurity_linkage",
                ],
                field_group,
            ),
            limit=4,
        )
        if not selected_units:
            continue
        context_text = _format_evidence_units_for_prompt(selected_units)
        bundle, response_json, model = gemini_client.extract_targeted_hplc_bundle(
            field_group=field_group,
            request_text=request_text,
            context_text=context_text,
            broadened_context=False,
        )
        if response_json and runtime_tracker is not None:
            usage = usage_from_response(
                response_json=response_json,
                prompt_text=context_text,
                response_text=json.dumps(bundle or {}, sort_keys=True),
                model=model,
            )
            runtime_tracker.note_llm_usage(
                "extract_methods",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
            )
        if not _llm_bundle_has_signal(field_group, bundle):
            broadened_units = select_evidence_units(
                evidence_units,
                field_group=cast(
                    Literal[
                        "chromatography_system",
                        "mobile_phase_gradient",
                        "detector_ionization",
                        "target_impurity_linkage",
                    ],
                    field_group,
                ),
                limit=7,
                allow_broad_follow_up=True,
            )
            if len(broadened_units) > len(selected_units):
                if runtime_tracker is not None:
                    runtime_tracker.note_branch_decision(
                        f"Escalated {field_group.replace('_', ' ')} extraction to broader evidence context."
                    )
                context_text = _format_evidence_units_for_prompt(broadened_units)
                bundle, response_json, model = gemini_client.extract_targeted_hplc_bundle(
                    field_group=field_group,
                    request_text=request_text,
                    context_text=context_text,
                    broadened_context=True,
                )
                if response_json and runtime_tracker is not None:
                    usage = usage_from_response(
                        response_json=response_json,
                        prompt_text=context_text,
                        response_text=json.dumps(bundle or {}, sort_keys=True),
                        model=model,
                    )
                    runtime_tracker.note_llm_usage(
                        "extract_methods",
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        estimated_cost_usd=usage.estimated_cost_usd,
                    )
        if not bundle:
            continue
        evidence_quote = str(bundle.get("evidence_quote") or "").strip()
        if evidence_quote:
            collected_quotes.append(evidence_quote)
        aggregated.update(
            {
                key: value
                for key, value in bundle.items()
                if key != "confidence"
                and key != "evidence_quote"
                and value is not None
            }
        )

    if collected_quotes and "evidence_quote" not in aggregated:
        aggregated["evidence_quote"] = " ".join(dict.fromkeys(collected_quotes))[:4000]
    return aggregated or None


def _format_evidence_units_for_prompt(units: tuple[object, ...]) -> str:
    serialized_units: list[dict[str, object]] = []
    for unit in units:
        serialized_units.append(
            {
                "unit_id": getattr(unit, "unit_id", None),
                "text": getattr(unit, "text", ""),
                "section_label": getattr(unit, "section_label", None),
                "page_number": getattr(unit, "page_number", None),
                "source_kind": getattr(unit, "source_kind", "unknown"),
                "feature_tags": list(getattr(unit, "feature_tags", ()) or ()),
            }
        )
    return json.dumps(serialized_units, ensure_ascii=True, indent=2, sort_keys=True)


def _llm_bundle_has_signal(field_group: str, bundle: dict | None) -> bool:
    if not bundle:
        return False
    if field_group == "chromatography_system":
        return bool(bundle.get("column_name"))
    if field_group == "mobile_phase_gradient":
        return bool(
            (
                isinstance(bundle.get("mobile_phase_a"), dict)
                and bundle["mobile_phase_a"].get("solvent")
            )
            or bundle.get("flow_rate_ml_min") is not None
            or bundle.get("run_time_min") is not None
            or bundle.get("gradient_profile")
        )
    return bool(bundle)


def _score_completeness(
    *,
    chromatography_system: object,
    method_parameters: object,
) -> float:
    """Return a 0–1 score indicating how complete the current extraction is."""
    score = 0.0
    total = 4.0
    if chromatography_system is not None:
        score += 1.0
    if method_parameters is not None:
        mp = method_parameters
        if getattr(getattr(mp, "mobile_phase_a", None), "solvent", None):
            score += 1.0
        if getattr(mp, "flow_rate_ml_min", None) is not None:
            score += 1.0
        if getattr(mp, "gradient_profile", None) or getattr(mp, "isocratic_percent_b", None) is not None:
            score += 1.0
    return score / total


def extract_hplc_via_llm(
    document: RegisteredSourceDocument,
    gemini_client: "GeminiOrchestrationClient",
) -> dict | None:
    """Full-document LLM extraction when regex produces insufficient results.

    Returns raw LLM dict suitable for _merge_llm_* helpers, or None.
    """
    full_text = " ".join(
        section.text
        for section in document.sections
        if section.text
    )
    if not full_text.strip():
        return None
    return gemini_client.extract_hplc_parameters(full_text)


def extract_hplc_via_pdf_llm(
    document: RegisteredSourceDocument,
    gemini_client: "GeminiOrchestrationClient",
    *,
    pdf_bytes: bytes,
    pdf_url: str | None = None,
    request_text: str | None = None,
) -> dict | None:
    """Ask a provider-native PDF parser/model path to extract method parameters."""
    extractor = getattr(gemini_client, "extract_hplc_parameters_from_pdf", None)
    if extractor is None:
        return None
    filename = document.source_document.file_name or "source.pdf"
    return extractor(
        pdf_bytes=pdf_bytes,
        filename=filename,
        pdf_url=pdf_url,
        request_text=request_text,
        title=document.source_document.title,
    )


def extract_hplc_via_markdown_pdf_llm(
    document: RegisteredSourceDocument,
    gemini_client: "GeminiOrchestrationClient",
    *,
    pdf_bytes: bytes,
    request_text: str | None = None,
) -> dict | None:
    """Convert the PDF locally to Markdown, then ask the worker to normalize HPLC fields."""
    if not pdf_bytes:
        return None
    extractor = getattr(gemini_client, "extract_hplc_parameters_from_markdown", None)
    if extractor is None:
        return None
    try:
        import pymupdf
        import pymupdf4llm

        pdf = pymupdf.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        markdown_text = pymupdf4llm.to_markdown(
            pdf,
            show_progress=False,
            force_text=True,
            table_strategy="lines_strict",
        )
    except Exception as exc:
        from rich import print as rprint

        rprint(f"[yellow]Local PDF Markdown extraction failed: {exc}[/yellow]")
        return None
    return extractor(
        markdown_text,
        request_text=request_text,
        title=document.source_document.title,
    )

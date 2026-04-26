from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass

import httpx

from .ai_runtime_settings import AiRuntimeSettings
from .recommendation_prompt_pack import (
    CandidateRerankResponse,
    ChromatographySystemExtractionResponse,
    DetectorIonizationExtractionResponse,
    MethodEvidenceSniffResponse,
    MobilePhaseGradientExtractionResponse,
    QueryPlannerResponse,
    RenderedPrompt,
    TargetImpurityLinkageExtractionResponse,
    build_candidate_reranker_prompt,
    build_field_extraction_prompt,
    build_method_evidence_sniff_prompt,
    build_query_planner_prompt,
    parse_candidate_reranker_response,
    parse_field_extraction_response,
    parse_method_evidence_sniff_response,
    parse_query_planner_response,
)


_HPLC_SIGNALS = [
    "mobile phase",
    "flow rate",
    "gradient",
    "column temperature",
    "acetonitrile",
    "methanol",
    "mL/min",
    "% B",
]


def _clean_json_response_text(response_text: str) -> str:
    clean_text = response_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()
    brace_idx = next((i for i, c in enumerate(clean_text) if c in ("{", "[")), None)
    if brace_idx is not None and brace_idx > 0:
        clean_text = clean_text[brace_idx:]
    return clean_text


def _select_dense_chunks(text: str, max_chars: int) -> str:
    """Return the highest-density HPLC chunks from text, up to max_chars."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    for i, sent in enumerate(sentences):
        score = sum(1 for sig in _HPLC_SIGNALS if sig.lower() in sent.lower())
        scored.append((score, i, sent))
    scored.sort(reverse=True)
    top = sorted(scored[:20], key=lambda x: x[1])
    result = " ".join(s for _, _, s in top)
    return result[:max_chars]


class OrchestrationClientError(RuntimeError):
    pass


# Backward-compatible alias
GeminiClientError = OrchestrationClientError


@dataclass(frozen=True)
class ConnectivityProbe:
    ok: bool
    model: str
    response_text: str


# Backward-compatible alias
GeminiConnectivityProbe = ConnectivityProbe


@dataclass(frozen=True)
class ObserverInsight:
    model: str
    summary: str
    recommended_next_action: str
    concerns: tuple[str, ...]


# Backward-compatible alias
GeminiObserverInsight = ObserverInsight


ROLE_WORKER = "__worker__"
ROLE_PLANNER = "__planner__"


class _BaseOrchestrationClient:
    def __init__(self, settings: AiRuntimeSettings) -> None:
        self._settings = settings
        self._max_context_chars = 12000
        self._max_vetting_chars = 12000

    def run_prompt(
        self,
        *,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> tuple[str, dict, str]:
        if model == ROLE_WORKER:
            selected_model = self._settings.worker_model
        elif model == ROLE_PLANNER:
            selected_model = self._settings.planner_model
        else:
            selected_model = model or self._settings.worker_model
        response_json = self._generate_content(
            model=selected_model,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            system_prompt=system_prompt,
        )
        response_text = self._extract_response_text(response_json)

        # Clean markdown code blocks and prose prefixes for JSON responses
        if response_mime_type == "application/json":
            response_text = _clean_json_response_text(response_text)

        return response_text, response_json, self._normalize_model_name(selected_model)

    def probe_connection(self) -> ConnectivityProbe:
        response_text, _response_json, model = self.run_prompt(
            prompt="Reply with OK only.",
            max_output_tokens=64,
            response_mime_type="text/plain",
            model=ROLE_WORKER,
        )
        return ConnectivityProbe(
            ok="ok" in response_text.lower(),
            model=model,
            response_text=response_text,
        )

    def summarize_c12_outcome(
        self,
        *,
        source_document_id: str,
        review_record_id: str,
        review_record_status: str,
        validation_status: str,
        retrieval_ready: bool,
        approval_status: str,
        approval_reason: str | None,
    ) -> ObserverInsight:
        prompt = (
            "You are a concise orchestration observer for an HPLC literature extraction demo. "
            "Return JSON only with keys summary, recommended_next_action, concerns. "
            "Keep summary under 30 words, recommended_next_action under 8 words, and concerns as an array of short strings.\n"
            f"source_document_id: {source_document_id}\n"
            f"review_record_id: {review_record_id}\n"
            f"review_record_status: {review_record_status}\n"
            f"validation_status: {validation_status}\n"
            f"retrieval_ready: {str(retrieval_ready).lower()}\n"
            f"approval_status: {approval_status}\n"
            f"approval_reason: {approval_reason or 'none'}\n"
        )
        response_text, _response_json, model = self.run_prompt(
            prompt=prompt,
            max_output_tokens=200,
            response_mime_type="application/json",
            model=ROLE_PLANNER,
        )
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise OrchestrationClientError(
                f"LLM returned non-JSON observer output: {response_text}"
            ) from exc
        concerns = payload.get("concerns", [])
        if not isinstance(concerns, list):
            concerns = []
        return ObserverInsight(
            model=model,
            summary=str(payload.get("summary", "")).strip() or "No summary provided",
            recommended_next_action=str(
                payload.get("recommended_next_action", "manual_review")
            ).strip()
            or "manual_review",
            concerns=tuple(str(item).strip() for item in concerns if str(item).strip()),
        )

    def extract_hplc_parameters(self, text: str) -> dict | None:
        from rich import print as rprint

        dense_text = _select_dense_chunks(text, self._max_context_chars)
        prompt = (
            "You are an expert analytical chemist and data extractor specializing in HPLC (High-Performance Liquid Chromatography). "
            "Your task is to extract method parameters from the provided literature text snippet. "
            "IMPORTANT: The text is extracted from a PDF and may contain interjected headers, page numbers, or footers in the middle of sentences. "
            "Ignore this noise and reconstruct the actual method descriptions.\n\n"
            "Papers often describe several trial methods before the final one. "
            "ONLY extract the method described as final, selected, optimized, or used for all samples. "
            "If no such cue exists, extract the LAST method described in detail.\n\n"
            "Return JSON only with the following keys:\n"
            "- chromatography_mode: one of 'rp_lc' (reverse phase), 'hilic', 'other', or null\n"
            "- column_name: column model or name (e.g. 'Waters XBridge C18') or null\n"
            "- column_length_mm: float or null\n"
            "- column_inner_diameter_mm: float or null\n"
            "- particle_size_um: float or null\n"
            "- mobile_phase_a: object with 'solvent' and 'additive' (e.g. {'solvent': 'water', 'additive': '0.1% formic acid'}) or null\n"
            "- mobile_phase_b: object with 'solvent' and 'additive' or null\n"
            "- flow_rate_ml_min: float or null\n"
            "- column_temperature_c: float or null\n"
            "- run_time_min: float or null\n"
            "- isocratic_percent_b: float or null (if isocratic)\n"
            "- gradient_profile: list of objects with 'time_min' and 'percent_b'. IMPORTANT: If providing a gradient, you MUST provide at least two points (e.g. start and end). If it is isocratic, set this to null and use isocratic_percent_b instead.\n"
            "- evidence_quote: a single concise string containing the most telling 1-2 sentences that prove these parameters, or null\n\n"
            "If a value is explicitly mentioned as 'premixed' or isocratic, reflect that. "
            "Be precise with units and decimal values.\n\n"
            f"Text snippet: {dense_text}"
        )
        response_text, _response_json, _model = self.run_prompt(
            prompt=prompt,
            max_output_tokens=2000,
            response_mime_type="application/json",
            model=ROLE_WORKER,
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            rprint(
                f"[red]LLM returned non-JSON for extract_hplc_parameters "
                f"(first 500 chars): {response_text[:500]}[/red]"
            )
            return self._extract_hplc_minimal_fallback(dense_text)

    def extract_hplc_parameters_from_pdf(
        self,
        *,
        pdf_bytes: bytes,
        filename: str,
        pdf_url: str | None = None,
        request_text: str | None = None,
        title: str | None = None,
    ) -> dict | None:
        del pdf_bytes, filename, pdf_url, request_text, title
        return None

    def extract_hplc_parameters_from_markdown(
        self,
        markdown_text: str,
        *,
        request_text: str | None = None,
        title: str | None = None,
    ) -> dict | None:
        if not markdown_text.strip():
            return None
        context = _select_dense_chunks(markdown_text, self._max_context_chars)
        prompt = (
            "You are an expert analytical chemist extracting a final LC/HPLC/LC-MS method from Markdown converted from a scientific PDF. "
            "The Markdown may preserve tables better than raw text but may still contain headers, footers, and page noise. "
            "Find the final, optimized, validated, or sample-analysis method, not screening trials. "
            "Return JSON only with keys chromatography_mode, column_name, column_length_mm, column_inner_diameter_mm, "
            "particle_size_um, mobile_phase_a, mobile_phase_b, flow_rate_ml_min, column_temperature_c, run_time_min, "
            "isocratic_percent_b, gradient_profile, evidence_quote. "
            "mobile_phase_a and mobile_phase_b should be objects with solvent and additive keys or null. "
            "gradient_profile must be null unless at least two time/percent_b points are present.\n"
        )
        if title:
            prompt += f"\nPaper title: {title}"
        if request_text:
            prompt += f"\nUser request: {request_text}"
        prompt += f"\n\nMarkdown context:\n{context}"
        response_text, _response_json, _model = self.run_prompt(
            prompt=prompt,
            max_output_tokens=2200,
            response_mime_type="application/json",
            model=ROLE_WORKER,
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None

    def _extract_hplc_minimal_fallback(self, text: str) -> dict | None:
        prompt = (
            "From the HPLC method text below, extract ONLY these three values as JSON:\n"
            "{\"mobile_phase_a\": {\"solvent\": \"...\", \"additive\": \"...\"}, "
            "\"mobile_phase_b\": {\"solvent\": \"...\", \"additive\": \"...\"}, "
            "\"flow_rate_ml_min\": null}\n"
            "If a value is not present, use null. No other keys.\n\n"
            f"Text: {text[:2000]}"
        )
        response_text, _response_json, _model = self.run_prompt(
            prompt=prompt,
            max_output_tokens=200,
            response_mime_type="application/json",
            model=ROLE_WORKER,
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            from rich import print as rprint

            rprint(
                f"[red]Minimal fallback also returned non-JSON: {response_text[:200]}[/red]"
            )
            return None

    def clarify_request(
        self,
        *,
        request_text: str,
        analyte_name: str | None,
        max_run_time_min: float | None,
        matrix_hint: str | None,
        detector_types: list[str],
        require_mass_spectrometry: bool,
    ) -> list[dict]:
        del analyte_name
        specified_parts: list[str] = []
        if max_run_time_min is not None:
            specified_parts.append(f"max run time: {max_run_time_min} min")
        if matrix_hint:
            specified_parts.append(f"matrix: {matrix_hint}")
        if detector_types:
            specified_parts.append(f"detectors: {', '.join(detector_types)}")
        if require_mass_spectrometry:
            specified_parts.append("mass spectrometry required")

        specified_str = (
            "; ".join(specified_parts) if specified_parts else "none explicitly set"
        )

        prompt = (
            "You are an HPLC method discovery assistant. A scientist submitted a separation request. "
            "Your default behavior should be to ask ZERO questions to ensure a fast, seamless user experience.\n\n"
            f"Request: \"{request_text}\"\n"
            f"Parameters already specified: {specified_str}\n\n"
            "ONLY ask a question if the request is extremely vague and impossible to search literature for (e.g., 'give me a method for a drug' without specifying the matrix or the analyte context). "
            "If the request mentions a specific analyte and at least one context clue (like 'plasma', 'urine', 'formulation', or 'bioequivalence'), DO NOT ask any questions.\n\n"
            "If you MUST ask to avoid complete failure, limit it to:\n"
            "1. matrix: What is the sample matrix? (Only if completely unguessable)\n"
            "2. detector: Is a specific detector required? (Only if totally omitted and critical)\n\n"
            "Return an empty array [] in almost all cases. Return JSON only:\n"
            "{\"questions\": []}"
        )

        try:
            response_text, _response_json, _model = self.run_prompt(
                prompt=prompt,
                max_output_tokens=300,
                response_mime_type="application/json",
                model=ROLE_PLANNER,
            )
            data = json.loads(response_text)
            result = []
            for q in (data.get("questions") or [])[:2]:
                if isinstance(q, dict) and q.get("id") and q.get("question"):
                    result.append(
                        {
                            "id": str(q["id"]),
                            "question": str(q["question"]),
                            "placeholder": str(q.get("placeholder", "")),
                        }
                    )
            return result
        except Exception:
            return []

    def prioritize_paper_candidates(
        self,
        *,
        request_text: str,
        analyte_name: str | None,
        matrix_hint: str | None,
        require_mass_spectrometry: bool,
        candidates: list[dict],
    ) -> list[str]:
        """Rank candidate papers by likelihood of yielding a complete, extractable LC method.

        Returns an ordered list of paper_ids (most promising first).
        Falls back to empty list on any error so the caller can use heuristic ordering.
        """
        analyte_str = analyte_name or "the target analyte"
        matrix_str = matrix_hint or "biological sample"
        ms_note = "MS/MS detection is required. " if require_mass_spectrometry else ""

        preamble = (
            f"You are an expert bioanalytical chemist helping select literature papers for method development.\n"
            f"Goal: find papers containing a complete, extractable HPLC-MS/MS method for quantifying "
            f"{analyte_str} in {matrix_str}. {ms_note}\n"
            f"Request: \"{request_text}\"\n\n"
            f"Rank the candidate papers below from MOST to LEAST likely to contain "
            f"a complete, reproducible chromatographic method. Favour:\n"
            f"  1. Papers directly analysing {analyte_str} in {matrix_str} (or similar matrix)\n"
            f"  2. Bioanalytical method validation papers (full methods section, column/mobile-phase detail)\n"
            f"  3. Open-access sources (PLOS ONE, PMC, MDPI, Innovare Academics) over paywalled journals\n"
            f"Penalise: review articles, pharmacological/toxicology studies without HPLC detail, "
            f"animal-only studies, papers about different analytes.\n\n"
            f"Candidates:\n"
        )
        suffix = "\nReturn JSON only: {\"priority_order\": [\"<paper_id>\", ...]}\nInclude every paper_id exactly once."

        # Build candidate lines within the available context budget.
        char_budget = self._max_context_chars - len(preamble) - len(suffix) - 200
        candidate_lines: list[str] = []
        included_ids: list[str] = []
        for i, c in enumerate(candidates, start=1):
            abstract_snippet = (c.get("abstract") or "")[:120].replace("\n", " ")
            line = (
                f"[{i}] id={c['paper_id']!r} | {c.get('year') or 'n/a'} | "
                f"score={c.get('screening_score', 0):.2f} | {c['title'][:100]}"
            )
            if abstract_snippet:
                line += f"\n     {abstract_snippet}"
            if char_budget - len(line) - 1 < 0:
                break
            candidate_lines.append(line)
            included_ids.append(c["paper_id"])
            char_budget -= len(line) + 1

        candidates_text = "\n".join(candidate_lines)
        prompt = preamble + candidates_text + suffix

        try:
            response_text, _response_json, _model = self.run_prompt(
                prompt=prompt,
                max_output_tokens=1200,
                response_mime_type="application/json",
                model=ROLE_PLANNER,
            )
            data = json.loads(response_text)
            return [str(pid) for pid in data.get("priority_order", []) if pid]
        except Exception as exc:
            from rich import print as rprint
            rprint(f"[yellow]Planner prioritization failed: {exc}[/yellow]")
            return []

    def plan_recommendation_queries(
        self,
        *,
        request_text: str,
        analyte_name: str | None,
        target_smiles_present: bool,
        impurity_count: int,
        matrix_hint: str | None,
        preferred_mode: str | None,
        require_mass_spectrometry: bool,
    ) -> QueryPlannerResponse | None:
        prompt = build_query_planner_prompt(
            request_text=request_text,
            analyte_name=analyte_name,
            target_smiles_present=target_smiles_present,
            impurity_count=impurity_count,
            matrix_hint=matrix_hint,
            preferred_mode=preferred_mode,
            require_mass_spectrometry=require_mass_spectrometry,
        )
        return self._run_structured_prompt(
            prompt=prompt,
            max_output_tokens=900,
            response_mime_type="application/json",
            model=ROLE_PLANNER,
            parser=parse_query_planner_response,
        )

    def rerank_paper_candidates(
        self,
        *,
        request_text: str,
        analyte_name: str | None,
        matrix_hint: str | None,
        preferred_mode: str | None,
        require_mass_spectrometry: bool,
        candidates: list[dict[str, object]],
    ) -> CandidateRerankResponse | None:
        prompt = build_candidate_reranker_prompt(
            request_text=request_text,
            analyte_name=analyte_name,
            matrix_hint=matrix_hint,
            preferred_mode=preferred_mode,
            require_mass_spectrometry=require_mass_spectrometry,
            candidates=candidates,
        )
        return self._run_structured_prompt(
            prompt=prompt,
            max_output_tokens=1600,
            response_mime_type="application/json",
            model=ROLE_PLANNER,
            parser=parse_candidate_reranker_response,
        )

    def sniff_method_bearing_evidence(
        self,
        *,
        request_text: str,
        analyte_name: str | None,
        matrix_hint: str | None,
        require_mass_spectrometry: bool,
        evidence_units: list[dict[str, object]],
    ) -> MethodEvidenceSniffResponse | None:
        prompt = build_method_evidence_sniff_prompt(
            request_text=request_text,
            analyte_name=analyte_name,
            matrix_hint=matrix_hint,
            require_mass_spectrometry=require_mass_spectrometry,
            evidence_units=evidence_units,
        )
        return self._run_structured_prompt(
            prompt=prompt,
            max_output_tokens=500,
            response_mime_type="application/json",
            model=ROLE_WORKER,
            parser=parse_method_evidence_sniff_response,
        )

    def vet_evidence_snippets(self, snippets: list[str]) -> str | None:
        if not snippets:
            return None
        combined = "\n---\n".join(snippets)[:self._max_vetting_chars]
        prompt = (
            "You are an expert analytical chemist reviewing raw text snippets extracted from an HPLC methodology paper. "
            "These snippets are currently too long and contain noise. "
            "Your task is to 'vet' these snippets and return ONLY the most telling 1-3 sentences that definitively describe the final HPLC method parameters (like the column, mobile phase, and flow rate). "
            "Do not include any JSON formatting, just return the plain text quote. Keep it extremely concise, under 300 characters if possible.\n\n"
            f"Raw Snippets:\n{combined}"
        )
        try:
            response_text, _response_json, _model = self.run_prompt(
                prompt=prompt,
                max_output_tokens=200,
                response_mime_type="text/plain",
                model=ROLE_WORKER,
            )
            return response_text.strip()
        except Exception as exc:
            from rich import print as rprint

            rprint(f"[red]Evidence vetting failed: {exc}[/red]")
            return None

    def extract_targeted_hplc_bundle(
        self,
        *,
        field_group: str,
        request_text: str | None = None,
        context_text: str,
        broadened_context: bool = False,
    ) -> tuple[dict | None, dict, str]:
        if field_group not in {
            "chromatography_system",
            "mobile_phase_gradient",
            "detector_ionization",
            "target_impurity_linkage",
        }:
            raise OrchestrationClientError(f"Unsupported field group: {field_group}")

        try:
            evidence_units = json.loads(context_text)
            if not isinstance(evidence_units, list):
                evidence_units = []
        except json.JSONDecodeError:
            evidence_units = []
        if not evidence_units:
            evidence_units = [
                {
                    "unit_id": "context-1",
                    "text": context_text[: self._max_context_chars],
                    "section_label": None,
                    "page_number": None,
                    "source_kind": "prompt_context",
                    "feature_tags": [],
                }
            ]

        prompt = build_field_extraction_prompt(
            field_group=field_group,
            request_text=request_text
            or (
                "Extract the final chromatographic method from the provided evidence units."
            ),
            evidence_units=evidence_units,
        )
        try:
            response_text, response_json, model = self.run_prompt(
                prompt=prompt.user_prompt,
                max_output_tokens=450,
                response_mime_type="application/json",
                model=ROLE_WORKER,
                system_prompt=prompt.system_prompt,
            )
            payload = parse_field_extraction_response(field_group, response_text)
            if payload is None:
                return None, response_json, model
            return payload.model_dump(mode="json", exclude_none=False), response_json, model
        except Exception:
            return None, {}, self._normalize_model_name(ROLE_WORKER)

    def _run_structured_prompt(
        self,
        *,
        prompt: RenderedPrompt,
        max_output_tokens: int,
        response_mime_type: str,
        model: str,
        parser,
    ):
        try:
            response_text, _response_json, _model = self.run_prompt(
                prompt=prompt.user_prompt,
                max_output_tokens=max_output_tokens,
                response_mime_type=response_mime_type,
                model=model,
                system_prompt=prompt.system_prompt,
            )
        except Exception:
            return None
        return parser(response_text)

    def _generate_content(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        system_prompt: str | None = None,
    ) -> dict:
        raise NotImplementedError

    def _extract_response_text(self, response_json: dict) -> str:
        raise NotImplementedError

    def _normalize_model_name(self, model: str) -> str:
        return model.strip()


class GeminiOrchestrationClient(_BaseOrchestrationClient):
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    _MODEL_ALIASES = {
        "gemini-1.5-flash": "gemini-2.5-flash",
        "gemini-1.5-pro": "gemini-2.5-pro",
        "gemini-flash-latest": "gemini-2.5-flash",
        "gemini-pro-latest": "gemini-2.5-pro",
        "gemini-flash-lite": "gemini-2.5-flash-lite",
        "models/gemini-1.5-flash": "models/gemini-2.5-flash",
        "models/gemini-1.5-pro": "models/gemini-2.5-pro",
        "models/gemini-flash-latest": "models/gemini-2.5-flash",
        "models/gemini-pro-latest": "models/gemini-2.5-pro",
        "models/gemini-flash-lite": "models/gemini-2.5-flash-lite",
    }

    def __init__(self, settings: AiRuntimeSettings) -> None:
        super().__init__(settings)
        if not settings.google_api_key:
            raise OrchestrationClientError(
                "Google API key is required to create Gemini client"
            )

    def _generate_content(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        system_prompt: str | None = None,
    ) -> dict:
        from rich import print as rprint

        normalized_model = self._normalize_model_name(model)
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self._settings.llm_timeout_sec) as client:
                    response = client.post(
                        f"{self._BASE_URL}/{normalized_model}:generateContent",
                        params={"key": self._settings.google_api_key},
                        json={
                            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                            **(
                                {
                                    "systemInstruction": {
                                        "parts": [{"text": system_prompt}]
                                    }
                                }
                                if system_prompt
                                else {}
                            ),
                            "generationConfig": {
                                "temperature": 0,
                                "topP": 1,
                                "maxOutputTokens": max_output_tokens,
                                "responseMimeType": response_mime_type,
                            },
                        },
                    )

                if response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    rprint(
                        f"[yellow]Gemini rate limit (429) hit. Retrying in {delay}s (Attempt {attempt + 1}/{max_retries})...[/yellow]"
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                if attempt == max_retries - 1:
                    raise OrchestrationClientError(
                        f"Gemini request failed for model '{normalized_model}' after {max_retries} attempts: {exc}"
                    ) from exc
                if not (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429
                ):
                    raise OrchestrationClientError(
                        f"Gemini request failed for model '{normalized_model}': {exc}"
                    ) from exc

        raise OrchestrationClientError("Failed to get response from Gemini after all retries.")

    def _extract_response_text(self, response_json: dict) -> str:
        candidates = response_json.get("candidates", [])
        if not candidates:
            raise OrchestrationClientError("Gemini response did not include candidates")
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        if not text_parts:
            raise OrchestrationClientError("Gemini response did not include text output")
        return "\n".join(text_parts).strip()

    def _normalize_model_name(self, model: str) -> str:
        normalized = self._MODEL_ALIASES.get(model.strip(), model.strip())
        return normalized.removeprefix("models/")


class OpenAICompatibleClient(_BaseOrchestrationClient):
    """Generic OpenAI-chat-compatible client. Subclass and set _DEFAULT_BASE_URL + api_key."""

    _DEFAULT_BASE_URL: str = ""
    _DEFAULT_MAX_CONTEXT_CHARS: int = 8000
    _DEFAULT_MAX_VETTING_CHARS: int = 6000

    def __init__(
        self,
        settings: AiRuntimeSettings,
        *,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(settings)
        self._api_key = api_key
        self._base_url = (base_url or self._DEFAULT_BASE_URL).rstrip("/")
        self._max_context_chars = self._DEFAULT_MAX_CONTEXT_CHARS
        self._max_vetting_chars = self._DEFAULT_MAX_VETTING_CHARS

    def _generate_content(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        system_prompt: str | None = None,
    ) -> dict:
        from rich import print as rprint

        normalized_model = self._normalize_model_name(model)
        max_retries = 3
        base_delay = 2.0
        payload: dict[str, object] = {
            "model": normalized_model,
            "messages": [
                *(
                    [{"role": "system", "content": system_prompt}]
                    if system_prompt
                    else []
                ),
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "top_p": 1,
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        if response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self._settings.llm_timeout_sec) as client:
                    response = client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                if response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    rprint(
                        f"[yellow]Rate limit (429) hit for {self._base_url}. Retrying in {delay}s (Attempt {attempt + 1}/{max_retries})...[/yellow]"
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                if attempt == max_retries - 1:
                    raise OrchestrationClientError(
                        f"Request to {self._base_url} failed for model '{normalized_model}' after {max_retries} attempts: {exc}"
                    ) from exc
                if not (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429
                ):
                    raise OrchestrationClientError(
                        f"Request to {self._base_url} failed for model '{normalized_model}': {exc}"
                    ) from exc

        raise OrchestrationClientError(
            f"Failed to get response from {self._base_url} after all retries."
        )

    def _extract_response_text(self, response_json: dict) -> str:
        choices = response_json.get("choices", [])
        if not choices:
            raise OrchestrationClientError("Response did not include choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                text_value = part.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    text_parts.append(text_value)
            if text_parts:
                return "\n".join(text_parts).strip()
        raise OrchestrationClientError("Response did not include text output")


class GroqOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    _DEFAULT_MAX_CONTEXT_CHARS = 8000
    _DEFAULT_MAX_VETTING_CHARS = 6000

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.groq_api_key:
            raise OrchestrationClientError("Groq API key required")
        super().__init__(settings, api_key=settings.groq_api_key)


class ZaiOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
    _DEFAULT_MAX_CONTEXT_CHARS = 32000
    _DEFAULT_MAX_VETTING_CHARS = 16000

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.zai_api_key:
            raise OrchestrationClientError("Z.AI API key required")
        super().__init__(settings, api_key=settings.zai_api_key)


class OpenRouterOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    _DEFAULT_MAX_CONTEXT_CHARS = 32000
    _DEFAULT_MAX_VETTING_CHARS = 16000
    # Client-side fallback chain: tried in order on 429 or 404 (model unavailable).
    # All free, no credits consumed. Last entry auto-routes to any available free model.
    _FREE_FALLBACK_MODELS = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "mistralai/mistral-nemo:free",
        "openrouter/free",  # auto-routes to whichever free model isn't rate-limited
    ]

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.openrouter_api_key:
            raise OrchestrationClientError("OpenRouter API key required")
        super().__init__(settings, api_key=settings.openrouter_api_key)

    def _model_rotation(self, primary_model: str) -> list[str]:
        """Return [primary] + fallbacks, deduped, preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for m in [primary_model, *self._FREE_FALLBACK_MODELS]:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    def _generate_content(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        system_prompt: str | None = None,
    ) -> dict:
        from rich import print as rprint

        models_to_try = self._model_rotation(self._normalize_model_name(model))
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://silico.bio",
            "X-Title": "Silico HPLC Method Discovery",
        }

        last_exc: Exception | None = None
        for candidate in models_to_try:
            payload: dict[str, object] = {
                "model": candidate,
                "messages": [
                    *(
                        [{"role": "system", "content": system_prompt}]
                        if system_prompt
                        else []
                    ),
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "top_p": 1,
                "max_tokens": max_output_tokens,
                "stream": False,
            }
            if response_mime_type == "application/json":
                payload["response_format"] = {"type": "json_object"}

            try:
                with httpx.Client(timeout=self._settings.llm_timeout_sec) as client:
                    response = client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                _SKIP_CODES = {429, 404, 400}
                if response.status_code in _SKIP_CODES:
                    reasons = {429: "rate limited", 404: "unavailable (404)", 400: "rejected (400)"}
                    reason = reasons.get(response.status_code, str(response.status_code))
                    rprint(
                        f"[yellow]OpenRouter {reason} for {candidate}, rotating to next model...[/yellow]"
                    )
                    last_exc = OrchestrationClientError(
                        f"{reason} on {candidate}: {response.text[:200]}"
                    )
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                raise OrchestrationClientError(
                    f"OpenRouter request failed for model '{candidate}': {exc}"
                ) from exc

        raise OrchestrationClientError(
            f"All OpenRouter models exhausted: {models_to_try}"
        ) from last_exc

    def extract_hplc_parameters_from_pdf(
        self,
        *,
        pdf_bytes: bytes,
        filename: str,
        pdf_url: str | None = None,
        request_text: str | None = None,
        title: str | None = None,
    ) -> dict | None:
        from rich import print as rprint

        if not pdf_bytes and not pdf_url:
            return None
        normalized_model = self._normalize_model_name(self._settings.worker_model)
        file_data = pdf_url
        if not file_data:
            file_data = (
                "data:application/pdf;base64,"
                + base64.b64encode(pdf_bytes).decode("ascii")
            )
        prompt = (
            "You are an expert analytical chemist extracting a final LC/HPLC/LC-MS method from a scientific PDF. "
            "Use the PDF parser output directly; do not rely on a lossy pre-extracted text snippet. "
            "Find the final, optimized, validated, or sample-analysis method, not screening trials. "
            "Return JSON only with keys:\n"
            "- chromatography_mode: 'rp_lc', 'hilic', 'other', or null\n"
            "- column_name: string or null\n"
            "- column_length_mm: float or null\n"
            "- column_inner_diameter_mm: float or null\n"
            "- particle_size_um: float or null\n"
            "- mobile_phase_a: object with solvent and additive, or null\n"
            "- mobile_phase_b: object with solvent and additive, or null\n"
            "- flow_rate_ml_min: float or null\n"
            "- column_temperature_c: float or null\n"
            "- run_time_min: float or null\n"
            "- isocratic_percent_b: float or null\n"
            "- gradient_profile: list of {time_min, percent_b} with at least two points, or null\n"
            "- evidence_quote: one concise quote proving column/mobile phase/flow rate, or null\n\n"
            "Prefer method sections, chromatographic conditions tables, captions, and validation/sample-analysis sections. "
            "If the PDF describes multiple methods, extract the method used for real samples or bioequivalence/PK samples.\n"
        )
        if title:
            prompt += f"\nPaper title: {title}"
        if request_text:
            prompt += f"\nUser request: {request_text}"

        payload: dict[str, object] = {
            "model": normalized_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "file",
                            "file": {
                                "filename": filename or "source.pdf",
                                "file_data": file_data,
                            },
                        },
                    ],
                }
            ],
            "plugins": [
                {
                    "id": "file-parser",
                    "pdf": {"engine": "cloudflare-ai"},
                }
            ],
            "temperature": 0,
            "top_p": 1,
            "max_tokens": 2500,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://silico.bio",
            "X-Title": "Silico HPLC Method Discovery",
        }
        max_retries = 3
        base_delay = 2.0
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self._settings.llm_timeout_sec) as client:
                    response = client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                if response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    rprint(
                        f"[yellow]OpenRouter PDF parser rate limit (429) hit. Retrying in {delay}s "
                        f"(Attempt {attempt + 1}/{max_retries})...[/yellow]"
                    )
                    time.sleep(delay)
                    continue
                if response.status_code >= 400:
                    body = response.text[:1000]
                    raise OrchestrationClientError(
                        f"OpenRouter PDF request failed with {response.status_code}: {body}"
                    )
                response_text = _clean_json_response_text(
                    self._extract_response_text(response.json())
                )
                return json.loads(response_text)
            except (httpx.HTTPError, json.JSONDecodeError, OrchestrationClientError) as exc:
                if attempt == max_retries - 1:
                    rprint(f"[red]OpenRouter PDF extraction failed: {exc}[/red]")
                    return None
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    continue
                rprint(f"[yellow]OpenRouter PDF extraction failed: {exc}[/yellow]")
                return None
        return None


def create_orchestration_client(settings: AiRuntimeSettings) -> _BaseOrchestrationClient:
    match settings.llm_provider:
        case "gemini":
            return GeminiOrchestrationClient(settings)
        case "groq":
            return GroqOrchestrationClient(settings)
        case "zai":
            return ZaiOrchestrationClient(settings)
        case "openrouter":
            return OpenRouterOrchestrationClient(settings)
        case "openai_compatible":
            if not settings.llm_base_url:
                raise OrchestrationClientError(
                    "openai_compatible provider requires LLM_BASE_URL"
                )
            api_key = (
                settings.zai_api_key
                or settings.groq_api_key
                or settings.openrouter_api_key
                or ""
            )
            return OpenAICompatibleClient(
                settings, api_key=api_key, base_url=settings.llm_base_url
            )
        case _:
            raise OrchestrationClientError(
                f"Unsupported LLM provider: {settings.llm_provider}"
            )

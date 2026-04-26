# Slice 2 — Fix LLM Extraction Fallback

## Problem

In `hplc_text_extraction.py`, the regex layer fires first. When it fails (or produces incomplete results), it falls back to `gemini_client.extract_hplc_parameters(text)`. This fallback:

1. **Truncates context to 4500 chars** (`_max_context_chars` for Groq). Most HPLC methods span 2–4 paragraphs spread across a paper — often more than 4500 chars into the content.
2. **Sends the whole document** rather than the relevant sections — the model wastes tokens on acknowledgements, references, funding statements.
3. **Returns `None` silently** on `JSONDecodeError` — the caller has no way to distinguish "no method found" from "model returned garbage".
4. **Never retries with a simpler prompt** — if the structured JSON extraction fails, there is no fallback prompt.

The logs say "Triggering LLM fallback" then extraction produces nothing. This is the primary cause of zero results on open-access HPLC papers.

## Root cause diagnosis checklist

Before implementing, confirm which failure mode is hitting:

```bash
# Add temporary print in extract_hplc_parameters before json.loads:
# print("LLM raw response:", response_text[:500])
# Then run a known HPLC paper through the extraction endpoint and read the output.
```

Likely culprits (in order):
- [ ] Groq model returns non-JSON or wraps JSON in markdown even with `response_format=json_object`
- [ ] Context is truncated before the methods section
- [ ] The model extracts trial methods, not the final method
- [ ] `JSONDecodeError` swallowed; `None` propagated silently

## Files to change

### `services/method-development/app/gemini_orchestration_client.py`

#### Fix `extract_hplc_parameters`

1. **Pre-select relevant sections** — before calling the LLM, run a quick regex pass to find the 3 most HPLC-dense chunks (sections containing "mobile phase", "flow rate", "gradient", "column"). Feed only those chunks to the LLM. This brings the relevant content into the context window regardless of document size.

   ```python
   def _select_dense_chunks(text: str, max_chars: int) -> str:
       """Return the highest-density HPLC chunks from text, up to max_chars."""
       HPLC_SIGNALS = ["mobile phase", "flow rate", "gradient", "column temperature",
                       "acetonitrile", "methanol", "mL/min", "% B"]
       sentences = re.split(r'(?<=[.!?])\s+', text)
       scored = []
       for i, sent in enumerate(sentences):
           score = sum(1 for sig in HPLC_SIGNALS if sig.lower() in sent.lower())
           scored.append((score, i, sent))
       scored.sort(reverse=True)
       # Take top sentences by score, then sort back by position for coherence
       top = sorted(scored[:20], key=lambda x: x[1])
       result = " ".join(s for _, _, s in top)
       return result[:max_chars]
   ```

2. **Raise `max_context_chars` for non-Groq providers**. For DeepSeek set it to `32000`. The `_max_context_chars` is set in `_BaseOrchestrationClient.__init__` — move it to a class attribute that subclasses override.

3. **Add structured error classification** — instead of returning `None`, return a `dataclass` with `data: dict | None` and `failure_reason: str | None`. Callers can then log the reason.

4. **Add a two-shot fallback**: if the full structured extraction fails JSON parse, retry with a simpler prompt asking only for mobile phase A, mobile phase B, and flow rate. This partial result is better than nothing.

   ```python
   def _extract_hplc_minimal_fallback(self, text: str) -> dict | None:
       prompt = (
           "From the HPLC method text below, extract ONLY these three values as JSON:\n"
           "{\"mobile_phase_a\": \"...\", \"mobile_phase_b\": \"...\", \"flow_rate_ml_min\": ...}\n"
           "If not present, use null. No other keys.\n\n"
           f"Text: {text[:2000]}"
       )
       response_text, _, _ = self.run_prompt(
           prompt=prompt, max_output_tokens=200,
           response_mime_type="application/json"
       )
       try:
           return json.loads(response_text)
       except json.JSONDecodeError:
           return None
   ```

### `services/method-development/app/hplc_text_extraction.py`

#### Fix the fallback invocation

Current code (approx):
```python
rprint("[yellow]Triggering evidence-targeted LLM fallback...[/yellow]")
fallback_candidate = _extract_generic_mobile_phase_candidate(sentence, source)
```

The fallback only operates on a single sentence. For papers where the mobile phase is described across multiple sentences, this always fails.

**Change**: when regex extraction produces fewer than 2 populated fields (mobile phase A or B missing), collect all HPLC-bearing sentences from the document and pass them as a block to `extract_hplc_parameters`. Use `_select_dense_chunks` from the client to pre-filter.

#### Add a document-level LLM extraction path

Add a new function:
```python
def extract_hplc_via_llm(
    document: RegisteredSourceDocument,
    gemini_client: GeminiOrchestrationClient,
) -> MinimalHplcExtractionResponse | None:
    """Full-document LLM extraction when regex produces insufficient results."""
    full_text = " ".join(
        section.content
        for section in document.source_document.sections or []
        if section.content
    )
    result = gemini_client.extract_hplc_parameters(full_text)
    if not result:
        return None
    return _map_llm_result_to_extraction_response(result, document)
```

Then in `extract_minimal_hplc`, after the regex pass:
```python
completeness = _score_completeness(extraction)  # existing logic
if completeness < 0.4 and gemini_client is not None:
    llm_result = extract_hplc_via_llm(document, gemini_client)
    if llm_result and _score_completeness(llm_result) > completeness:
        extraction = llm_result
```

## Prompt improvement

The current `extract_hplc_parameters` prompt is good but has one problem: it tells the model to "extract the final or optimized" method, but doesn't explain that papers often describe multiple trial methods before the final one. Add:

```
"Papers often describe several trial methods before the final one. 
ONLY extract the method described as final, selected, optimized, or used for all samples.
If no such cue exists, extract the LAST method described in detail."
```

## Validation

Run the extraction endpoint on a known open-access HPLC paper:
- PubMed Central paper on an LC-MS/MS bioanalytical method
- Expected: non-null mobile_phase_a, mobile_phase_b, flow_rate_ml_min, column_name

```bash
curl -X POST http://localhost:8002/source-documents/{id}/extract-hplc \
  -H "Content-Type: application/json"
```

## Acceptance criteria

- LLM fallback produces non-null extraction for at least 3/5 test open-access HPLC papers
- `JSONDecodeError` is logged with model response, not silently dropped
- Completeness score after fallback is ≥ 0.4 for papers with clearly described methods
- Partial results (mobile phase only) are stored rather than discarded

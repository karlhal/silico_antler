# Slice 3 — Open-Access Paper Pipeline

## Problem

The recommendation engine fetches open-access papers from PubMed/Unpaywall/Semantic Scholar but the fetch-to-extraction conversion rate is low. Main failure modes:

1. **HTML fetch succeeds but content is empty** — some publishers return 200 with a JS-rendered shell. `ingest_html_document` gets nearly no text.
2. **PDF fallback is not reliably triggered** — `_can_try_pdf_fallback()` has conditions that prevent fallback even when the HTML is clearly empty.
3. **Text extraction produces wall-of-text** — `pdfplumber` dumps everything with no section awareness, so HPLC signals are buried after page headers, reference lists, figure captions.
4. **HPLC signal check is too strict** — `sniff_method_bearing_evidence` may reject a paper because the abstract doesn't mention HPLC explicitly, even though the methods section has a complete LC-MS/MS method.

## Files to change

### `services/method-development/app/source_document_ingestion.py`

#### Make section detection smarter

Current: sections are split by HTML headings (`h1`–`h4`). This misses papers that use bold text or numbered headings without semantic HTML.

Add a fallback section detector:
```python
def _detect_sections_from_text(text: str) -> list[tuple[str, str]]:
    """Detect section headers by looking for short all-caps or title-case lines."""
    SECTION_HEADER = re.compile(
        r'^(?:(?:[A-Z][A-Z\s]{2,40})|(?:\d+\.\s+[A-Z][A-Za-z\s]{3,40}))$',
        re.MULTILINE
    )
    ...
```

#### Add content quality check after HTML parse

```python
def _html_content_is_usable(sections: list) -> bool:
    total_chars = sum(len(s.content or "") for s in sections)
    return total_chars > 800  # Below this it's probably a JS shell
```

If `not _html_content_is_usable(sections)`: immediately trigger PDF fallback rather than returning a near-empty document.

#### Improve PDF text extraction

Replace raw `pdfplumber.extract_text()` with a page-by-page approach that:
1. Skips the first page (usually title/abstract/keywords — already in metadata)
2. Skips reference pages (detectable: >60% of lines start with `[` or `\d+.`)
3. Joins hyphenated line breaks: `word-\nbreak` → `wordbreak`
4. Strips running headers (lines < 60 chars appearing 3+ times across pages)

This dramatically improves the signal-to-noise for the HPLC regex and LLM.

### `services/method-development/app/recommendation_engine.py`

#### Fix PDF fallback gating

Find `_can_try_pdf_fallback()`. It currently checks if `open_access_pdf_url` is non-None. Also check that the HTML artifact isn't already a PDF and that the HTML content is actually sparse.

```python
def _can_try_pdf_fallback(artifact: FetchedSourceArtifact, html_char_count: int) -> bool:
    return (
        artifact.pdf_url is not None
        and html_char_count < 1000  # sparse HTML = fallback warranted
    )
```

#### Add HPLC signal pre-filter before extraction

Before sending a paper to full extraction (expensive), do a fast text scan:

```python
HPLC_REQUIRED_SIGNALS = ["mobile phase", "flow rate", "column", "gradient", "mL/min"]
HPLC_STRONG_SIGNALS = ["acetonitrile", "methanol", "LC-MS", "HPLC", "UHPLC", "RP-HPLC"]

def _paper_has_hplc_signal(text: str) -> bool:
    text_lower = text.lower()
    required = sum(1 for s in HPLC_REQUIRED_SIGNALS if s.lower() in text_lower)
    strong = sum(1 for s in HPLC_STRONG_SIGNALS if s.lower() in text_lower)
    return required >= 2 or strong >= 1
```

Papers failing this check get skipped with a clear skip reason (`"no_hplc_signal"`) rather than going through extraction and producing null results.

#### Increase extraction concurrency for open-access papers

`_EXTRACTION_BATCH_SIZE = 5` and `_DEFAULT_EXTRACTION_CONCURRENCY = 1` means papers are extracted one at a time. For the website use case where we want fast results:
- Increase `_DEFAULT_EXTRACTION_CONCURRENCY = 3`
- Add a configurable env var `SILICO_METHOD_DEVELOPMENT_EXTRACTION_CONCURRENCY`

### `services/method-development/app/open_access_client.py`

#### Add User-Agent and retry on 403

Some PubMed Central HTML responses return 403 if there's no User-Agent. Add:
```python
headers = {
    "User-Agent": "Silico/1.0 (HPLC method research; contact@silico.bio)",
    "Accept": "text/html,application/xhtml+xml",
}
```

Also retry once on 403 with a different URL form (e.g., PMC full-text vs abstract page).

#### Prefer PMC full-text URLs

When a DOI resolves to a PubMed abstract page (`pubmed.ncbi.nlm.nih.gov/...`), attempt to convert it to the PMC full-text URL before fetching. PMC HTML is much more parseable than publisher HTML.

```python
def _try_pmc_fulltext_url(url: str, pmc_id: str | None) -> str | None:
    if pmc_id:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
    return None
```

## Acceptance criteria

- Fetching a known PMC open-access HPLC paper returns usable text (> 2000 chars, contains "mobile phase")
- PDF fallback fires when HTML fetch returns < 1000 chars
- `"no_hplc_signal"` skip reason appears in skipped_papers list for non-HPLC papers
- End-to-end: `recommend_methods` for a well-studied analyte (e.g., metformin in plasma) returns ≥ 1 candidate with non-null mobile phase A and B

## Test data (known good open-access papers)

| Analyte | PMC ID | Expected method |
|---------|--------|----------------|
| Metformin in plasma | PMC3984587 | RP-HPLC, ACN/water |
| Amlodipine in serum | PMC4142442 | RP-HPLC, methanol/phosphate |
| Ibuprofen in urine | PMC6682274 | RP-HPLC, ACN/buffer gradient |

Use these as integration test fixtures.

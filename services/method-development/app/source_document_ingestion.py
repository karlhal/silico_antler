from __future__ import annotations

import base64
import io
import re
from collections.abc import Iterable

import pdfplumber
from bs4.builder import LXMLTreeBuilder
from bs4 import BeautifulSoup, NavigableString, Tag
from lxml import etree

from .retrieval_schemas import SourceDocumentMetadata
from .source_document_schemas import (
    RegisteredSourceDocument,
    SourceDocumentAssetPlaceholder,
    SourceDocumentPage,
    SourceDocumentRegisterRequest,
    SourceDocumentSection,
    SourceDocumentSectionKind,
)

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
SECTION_HEADER = re.compile(
    r"^(?:(?:[A-Z][A-Z\s]{2,40})|(?:\d+\.\s+[A-Z][A-Za-z\s]{3,40}))$",
    re.MULTILINE,
)
ARTICLE_ROOT_SELECTORS = (
    "section.article-body",
    "div.html-dynamic",
    "article",
    "main article",
    "main#main-content article",
    "div[itemprop='articleBody']",
    "div.c-article-body",
    "div.article__body",
    "main#main-content",
    "main",
)
ROOT_FALLBACK_SELECTORS = (
    "div#main-content",
    "section.main-section",
)
HTML_BACK_MATTER_LABELS = {
    "acknowledgments",
    "acknowledgements",
    "author contributions",
    "funding",
    "institutional review board statement",
    "informed consent statement",
    "data availability statement",
    "conflicts of interest",
    "conflict of interest",
    "abbreviations",
    "supporting information",
    "supplementary information",
    "supplementary materials",
    "patents",
}
HTML_NON_BODY_HINTS = (
    "fig",
    "figure",
    "table",
    "caption",
    "share",
    "download",
    "metric",
    "author",
    "affiliation",
    "citation",
    "breadcrumb",
    "sidebar",
    "related",
    "popup",
)
HEADING_PATTERN = re.compile(
    r"^(abstract|introduction|materials? and methods?|methods?|experimental|results?( and discussion)?|discussion|conclusions?|references)$",
    re.IGNORECASE,
)
TABLE_PATTERN = re.compile(r"\b(Table\s+[A-Za-z0-9.-]+)\b")
FIGURE_PATTERN = re.compile(r"\b(Fig(?:ure)?\.?\s+[A-Za-z0-9.-]+)\b", re.IGNORECASE)
SUPPLEMENT_PATTERN = re.compile(
    r"\b(Supplement(?:ary)?(?:\s+(?:Information|Table|Figure|Fig|Text)\s*[A-Za-z0-9.-]*)?)\b",
    re.IGNORECASE,
)
SUPPLEMENT_SHORT_PATTERN = re.compile(
    r"\b(S\d+\s*(?:Table|Figure|Fig|Text)\.?)\b",
    re.IGNORECASE,
)
PDF_SECTION_HEADINGS: tuple[
    tuple[str, SourceDocumentSectionKind, tuple[str, ...]], ...
] = (
    ("Abstract", "abstract", ("abstract",)),
    ("Introduction", "introduction", ("introduction",)),
    (
        "Materials and Methods",
        "methods",
        ("materialsandmethods", "materialandmethods", "methods", "experimental"),
    ),
    (
        "Results and Discussion",
        "results",
        ("resultsanddiscussion", "results", "resultsanddiscussion"),
    ),
    ("Discussion", "discussion", ("discussion",)),
    ("Conclusions", "conclusion", ("conclusion", "conclusions")),
    ("Supporting Information", "other", ("supportinginformation",)),
    ("Acknowledgments", "other", ("acknowledgments", "acknowledgements")),
    (
        "Author Contributions",
        "other",
        ("authorcontributions",),
    ),
    ("Conflicts of Interest", "other", ("conflictsofinterest",)),
    ("Abbreviations", "other", ("abbreviations",)),
    ("References", "references", ("references",)),
)


class SourceDocumentIngestionError(ValueError):
    pass


class _NoStripCdataLXMLTreeBuilder(LXMLTreeBuilder):
    def default_parser(self, encoding: str | None) -> type[etree.HTMLParser] | object:
        return _build_lxml_html_parser


def ingest_source_document(
    payload: SourceDocumentRegisterRequest,
) -> RegisteredSourceDocument:
    metadata = payload.source_document
    if metadata.source_type == "html":
        return ingest_html_document(metadata, payload.html_content or "")
    return ingest_pdf_document(metadata, _decode_base64_pdf(payload.pdf_base64 or ""))


def _html_content_is_usable(sections: list[SourceDocumentSection]) -> bool:
    total_chars = sum(len(s.text or "") for s in sections)
    return total_chars > 800


def ingest_html_document(
    metadata: SourceDocumentMetadata, html_content: str
) -> RegisteredSourceDocument:
    soup = _build_html_soup(html_content)
    root = _select_html_root(soup)

    sections = _extract_html_sections(root)
    table_sections = _extract_html_table_sections(root, sections)
    if table_sections:
        sections.extend(table_sections)
    if not sections:
        fallback_text = _clean_text(root.get_text("\n", strip=True))
        if not fallback_text:
            raise SourceDocumentIngestionError(
                "HTML ingestion produced no readable text"
            )
        sections = [
            SourceDocumentSection(
                section_id="section-1",
                label="Document",
                normalized_label="other",
                text=fallback_text,
            )
        ]

    source_document = _with_inferred_title(
        metadata, _infer_html_title(soup, root, sections)
    )
    raw_text = _join_section_text(sections)
    table_placeholders = _extract_html_table_placeholders(root)
    figure_placeholders = _extract_html_figure_placeholders(root)
    supplement_placeholders = _extract_html_supplement_placeholders(root)

    return RegisteredSourceDocument(
        source_document=source_document,
        raw_text=raw_text,
        sections=sections,
        table_placeholders=table_placeholders,
        figure_placeholders=figure_placeholders,
        supplement_placeholders=supplement_placeholders,
    )


def _is_reference_page(lines: list[str]) -> bool:
    """Return True if >60% of non-empty lines look like reference list entries."""
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return False
    ref_pattern = re.compile(r"^(\[|\d+\.)")
    ref_count = sum(1 for line in non_empty if ref_pattern.match(line.strip()))
    return ref_count / len(non_empty) > 0.6


def _join_hyphenated_lines(text: str) -> str:
    """Join word-hyphen-newline sequences into a single word."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def _collect_running_headers(page_texts: list[str]) -> set[str]:
    """Find short lines (< 60 chars) that appear on 3+ pages — running headers/footers."""
    if len(page_texts) < 3:
        return set()
    line_counts: dict[str, int] = {}
    for page_text in page_texts:
        seen_on_page: set[str] = set()
        for line in page_text.splitlines():
            clean = line.strip()
            if clean and len(clean) < 60 and clean not in seen_on_page:
                line_counts[clean] = line_counts.get(clean, 0) + 1
                seen_on_page.add(clean)
    return {line for line, count in line_counts.items() if count >= 3}


def ingest_pdf_document(
    metadata: SourceDocumentMetadata, pdf_bytes: bytes
) -> RegisteredSourceDocument:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pdf_metadata = dict(pdf.metadata or {})
            total_pages = len(pdf.pages)
            raw_page_texts = [page.extract_text() or "" for page in pdf.pages]

        running_headers = _collect_running_headers(raw_page_texts)
        pages: list[SourceDocumentPage] = []
        warnings: list[str] = []
        for page_number, raw_text in enumerate(raw_page_texts, start=1):
            if page_number == 1 and total_pages > 1:
                continue
            joined = _join_hyphenated_lines(raw_text)
            lines = joined.splitlines()
            if _is_reference_page(lines):
                continue
            filtered_lines = [
                line for line in lines if line.strip() not in running_headers
            ]
            page_text = _clean_text("\n".join(filtered_lines))
            if not page_text:
                warnings.append(f"Page {page_number} did not yield readable text")
                continue
            pages.append(SourceDocumentPage(page_number=page_number, text=page_text))
    except Exception as exc:  # pragma: no cover - parser/library exception surface
        raise SourceDocumentIngestionError("PDF ingestion failed") from exc

    if not pages:
        raise SourceDocumentIngestionError("PDF ingestion produced no readable text")

    sections = _extract_pdf_sections(pages)
    source_document = _with_inferred_title(
        metadata, _infer_pdf_title(pages, sections, pdf_metadata)
    )
    raw_text = _join_section_text(sections)
    table_placeholders = _extract_pdf_asset_placeholders(pages, sections, kind="table")
    figure_placeholders = _extract_pdf_asset_placeholders(
        pages, sections, kind="figure"
    )
    supplement_placeholders = _extract_pdf_asset_placeholders(
        pages, sections, kind="supplement"
    )

    return RegisteredSourceDocument(
        source_document=source_document,
        raw_text=raw_text,
        pages=pages,
        sections=sections,
        table_placeholders=table_placeholders,
        figure_placeholders=figure_placeholders,
        supplement_placeholders=supplement_placeholders,
        ingestion_warnings=warnings,
    )


def _decode_base64_pdf(raw_value: str) -> bytes:
    try:
        return base64.b64decode(raw_value, validate=True)
    except Exception as exc:
        raise SourceDocumentIngestionError("pdf_base64 must be valid base64") from exc


def _build_html_soup(html_content: str) -> BeautifulSoup:
    return BeautifulSoup(
        html_content,
        builder=_NoStripCdataLXMLTreeBuilder(),
    )


def _build_lxml_html_parser(**kwargs: object) -> etree.HTMLParser:
    parser_kwargs = {
        key: value for key, value in kwargs.items() if key != "strip_cdata"
    }
    return etree.HTMLParser(**parser_kwargs)


def _extract_html_sections(root: Tag) -> list[SourceDocumentSection]:
    sections = _extract_html_section_tags(root)
    if sections:
        return sections
    sections = _extract_html_section_divs(root)
    if sections:
        return sections
    sections = _extract_html_heading_siblings(root)
    if sections:
        return sections
    raw_text = _clean_text(root.get_text("\n", strip=True))
    return _detect_sections_from_text(raw_text)


def _select_html_root(soup: BeautifulSoup) -> Tag:
    for selector in ARTICLE_ROOT_SELECTORS:
        selected = soup.select_one(selector)
        if selected is not None:
            if _root_has_minimal_article_structure(selected):
                return selected
            for fallback_selector in ROOT_FALLBACK_SELECTORS:
                fallback = soup.select_one(fallback_selector)
                if fallback is not None and _root_has_minimal_article_structure(
                    fallback
                ):
                    return fallback
            return selected
    return soup.body or soup


def _root_has_minimal_article_structure(root: Tag) -> bool:
    heading_count = len(root.find_all(HEADING_TAGS))
    section_count = len(root.find_all("section"))
    return heading_count >= 3 or section_count >= 3


def _detect_sections_from_text(text: str) -> list[SourceDocumentSection]:
    """Detect section headers by looking for short all-caps or title-case lines."""
    if not text:
        return []
    sections: list[SourceDocumentSection] = []
    current_label = "Document"
    current_lines: list[str] = []
    section_count = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if SECTION_HEADER.match(stripped):
            if current_lines:
                content = _clean_text("\n".join(current_lines))
                if content:
                    section_count += 1
                    sections.append(
                        SourceDocumentSection(
                            section_id=f"section-text-{section_count}",
                            label=current_label,
                            normalized_label=_classify_section_label(current_label),
                            text=content,
                        )
                    )
            current_label = stripped.title() if stripped.isupper() else stripped
            current_lines = []
        else:
            current_lines.append(stripped)

    if current_lines:
        content = _clean_text("\n".join(current_lines))
        if content:
            section_count += 1
            sections.append(
                SourceDocumentSection(
                    section_id=f"section-text-{section_count}",
                    label=current_label,
                    normalized_label=_classify_section_label(current_label),
                    text=content,
                )
            )
    return sections


def _extract_html_section_tags(root: Tag) -> list[SourceDocumentSection]:
    sections: list[SourceDocumentSection] = []
    seen_labels: set[tuple[str, str]] = set()
    for index, section_tag in enumerate(root.find_all("section"), start=1):
        heading = section_tag.find(HEADING_TAGS)
        if heading is None:
            continue
        section = _build_html_section_candidate(
            section_tag, heading, section_id=f"section-{index}"
        )
        if section is None:
            continue
        key = (_normalize_label(section.label), section.text[:120])
        if key in seen_labels:
            continue
        seen_labels.add(key)
        sections.append(section)
    return sections


def _extract_html_section_divs(root: Tag) -> list[SourceDocumentSection]:
    sections: list[SourceDocumentSection] = []
    seen_labels: set[tuple[str, str]] = set()
    candidates = root.select("div.section, div.toc-section, div[class*='section']")
    for candidate in candidates:
        heading = candidate.find(HEADING_TAGS)
        if heading is None:
            continue
        section = _build_html_section_candidate(
            candidate, heading, section_id=f"section-{len(sections) + 1}"
        )
        if section is None:
            continue
        key = (_normalize_label(section.label), section.text[:120])
        if key in seen_labels:
            continue
        seen_labels.add(key)
        sections.append(section)
    return sections


def _build_html_section_candidate(
    candidate: Tag, heading: Tag, *, section_id: str
) -> SourceDocumentSection | None:
    label = _clean_text(heading.get_text(" ", strip=True))
    if not label:
        return None
    text = _clean_text(candidate.get_text("\n", strip=True))
    text = _strip_heading_prefix(label, text)
    if not text or not _is_probable_html_section_candidate(candidate, label, text):
        return None
    return SourceDocumentSection(
        section_id=section_id,
        label=label,
        normalized_label=_classify_section_label(label),
        text=text,
    )


def _is_probable_html_section_candidate(candidate: Tag, label: str, text: str) -> bool:
    normalized_label = _normalize_label(label)
    if normalized_label in HTML_BACK_MATTER_LABELS:
        return False
    if FIGURE_PATTERN.search(label) or TABLE_PATTERN.search(label):
        return False

    hint_values = [candidate.get("id", "")]
    class_values = candidate.get("class")
    if isinstance(class_values, list):
        hint_values.extend(class_values)
    hint_text = " ".join(str(value).lower() for value in hint_values if value)
    if any(hint in hint_text for hint in HTML_NON_BODY_HINTS):
        return False

    if normalized_label in {
        "abstract",
        "introduction",
        "materials and methods",
        "material and methods",
        "methods",
        "experimental",
        "results",
        "results and discussion",
        "discussion",
        "conclusion",
        "conclusions",
        "references",
    }:
        return True

    meaningful_words = re.findall(r"[A-Za-z]{3,}", text)
    return len(text) >= 80 and len(meaningful_words) >= 12


def _extract_html_heading_siblings(root: Tag) -> list[SourceDocumentSection]:
    sections: list[SourceDocumentSection] = []
    headings = root.find_all(HEADING_TAGS)
    for index, heading in enumerate(headings, start=1):
        label = _clean_text(heading.get_text(" ", strip=True))
        if not label:
            continue
        sibling_text: list[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag) and sibling.name in HEADING_TAGS:
                break
            if isinstance(sibling, Tag):
                text = _clean_text(sibling.get_text("\n", strip=True))
                if text:
                    sibling_text.append(text)
        section_text = _clean_text("\n\n".join(sibling_text))
        if not section_text:
            continue
        sections.append(
            SourceDocumentSection(
                section_id=f"section-{index}",
                label=label,
                normalized_label=_classify_section_label(label),
                text=section_text,
            )
        )
    return sections


def _extract_html_table_sections(
    root: Tag, existing_sections: list[SourceDocumentSection]
) -> list[SourceDocumentSection]:
    sections: list[SourceDocumentSection] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, table in enumerate(root.find_all("table"), start=1):
        rows = []
        for row in table.find_all("tr"):
            cells = [
                _clean_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"])
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            continue

        caption_text = (
            _clean_text(table.find("caption").get_text(" ", strip=True))
            if table.find("caption")
            else None
        )
        context_label = _find_nearest_html_heading_label(table)
        section_text_lines = []
        if caption_text:
            section_text_lines.append(caption_text)
        for row in rows:
            section_text_lines.extend(row)
        section_text = _clean_text("\n".join(section_text_lines))
        if not section_text:
            continue

        section_label = context_label or caption_text or f"Table {index}"
        if _table_text_is_already_present(
            section_text, section_label, existing_sections
        ):
            continue
        dedupe_key = (_normalize_label(section_label), section_text[:200])
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        sections.append(
            SourceDocumentSection(
                section_id=f"table-section-{index}",
                label=section_label,
                normalized_label=_classify_section_label(section_label),
                text=section_text,
            )
        )
    return sections


def _table_text_is_already_present(
    table_text: str,
    section_label: str,
    existing_sections: list[SourceDocumentSection],
) -> bool:
    table_lines = [line for line in table_text.splitlines() if line.strip()]
    marker_lines = [line for line in table_lines[:4] if len(line) >= 4]
    normalized_label = _normalize_label(section_label)
    for section in existing_sections:
        if _normalize_label(section.label) != normalized_label:
            continue
        normalized_section_text = section.text.lower()
        if marker_lines and all(
            line.lower() in normalized_section_text for line in marker_lines
        ):
            return True
    return False


def _find_nearest_html_heading_label(node: Tag) -> str | None:
    for ancestor in node.parents:
        if not isinstance(ancestor, Tag):
            continue
        heading = ancestor.find(HEADING_TAGS)
        if heading is not None:
            label = _clean_text(heading.get_text(" ", strip=True))
            if label:
                return label

    previous_heading = node.find_previous(HEADING_TAGS)
    if previous_heading is None:
        return None
    label = _clean_text(previous_heading.get_text(" ", strip=True))
    return label or None


def _infer_html_title(
    soup: BeautifulSoup, root: Tag, sections: list[SourceDocumentSection]
) -> str | None:
    for selector in (
        'meta[name="citation_title"]',
        'meta[property="og:title"]',
        'meta[name="dc.title"]',
    ):
        meta_tag = soup.select_one(selector)
        if meta_tag is None:
            continue
        meta_content = meta_tag.attrs.get("content")
        title = _clean_text(str(meta_content) if meta_content is not None else "")
        if title:
            return title

    title_tag = soup.find("title")
    if title_tag is not None:
        title = _clean_text(title_tag.get_text(" ", strip=True))
        if title:
            return title

    heading = root.find("h1") or root.find("h2")
    if heading is not None:
        title = _clean_text(heading.get_text(" ", strip=True))
        if title:
            return title

    first_section = next(iter(sections), None)
    if first_section is None:
        return None
    return first_section.label if first_section.label != "Document" else None


def _extract_html_table_placeholders(root: Tag) -> list[SourceDocumentAssetPlaceholder]:
    placeholders: list[SourceDocumentAssetPlaceholder] = []
    seen_labels: set[str] = set()
    for index, table in enumerate(root.find_all("table"), start=1):
        caption = table.find("caption")
        caption_text = (
            _clean_text(caption.get_text(" ", strip=True)) if caption else None
        )
        label = (
            _extract_label_from_text(caption_text, TABLE_PATTERN) or f"Table {index}"
        )
        _append_unique_placeholder(
            placeholders,
            seen_labels,
            SourceDocumentAssetPlaceholder(
                asset_kind="table",
                label=label,
                caption_hint=caption_text,
            ),
        )

    for node in root.select("div.figure, div.html-table-wrap"):
        caption_text = _extract_html_caption_text(
            node,
            ".figcaption, .html-table_wrap_discription, .html-caption, caption",
        )
        label = _extract_label_from_text(caption_text, TABLE_PATTERN)
        if label is None:
            continue
        _append_unique_placeholder(
            placeholders,
            seen_labels,
            SourceDocumentAssetPlaceholder(
                asset_kind="table",
                label=label,
                caption_hint=caption_text,
            ),
        )
    return placeholders


def _extract_html_figure_placeholders(
    root: Tag,
) -> list[SourceDocumentAssetPlaceholder]:
    placeholders: list[SourceDocumentAssetPlaceholder] = []
    seen_labels: set[str] = set()
    for index, figure in enumerate(root.find_all("figure"), start=1):
        figcaption = figure.find("figcaption")
        caption_text = (
            _clean_text(figcaption.get_text(" ", strip=True)) if figcaption else None
        )
        label = (
            _extract_label_from_text(caption_text, FIGURE_PATTERN) or f"Figure {index}"
        )
        _append_unique_placeholder(
            placeholders,
            seen_labels,
            SourceDocumentAssetPlaceholder(
                asset_kind="figure",
                label=label,
                caption_hint=caption_text,
            ),
        )

    for node in root.select("div.figure, div.html-fig-wrap, div.html-fig_show"):
        caption_text = _extract_html_caption_text(
            node,
            ".figcaption, .html-fig_description, .html-caption, figcaption",
        )
        label = _extract_label_from_text(caption_text, FIGURE_PATTERN)
        if label is None:
            continue
        _append_unique_placeholder(
            placeholders,
            seen_labels,
            SourceDocumentAssetPlaceholder(
                asset_kind="figure",
                label=label,
                caption_hint=caption_text,
            ),
        )
    return placeholders


def _extract_html_supplement_placeholders(
    root: Tag,
) -> list[SourceDocumentAssetPlaceholder]:
    placeholders: list[SourceDocumentAssetPlaceholder] = []
    seen: set[tuple[str | None, str | None]] = set()
    for link in root.find_all("a", href=True):
        candidate_text = _clean_text(link.get_text(" ", strip=True)) or _clean_text(
            link.get("href", "")
        )
        if not candidate_text or not (
            SUPPLEMENT_PATTERN.search(candidate_text)
            or SUPPLEMENT_SHORT_PATTERN.search(candidate_text)
        ):
            continue
        label = (
            _extract_label_from_text(candidate_text, SUPPLEMENT_PATTERN)
            or _extract_label_from_text(candidate_text, SUPPLEMENT_SHORT_PATTERN)
            or candidate_text
        )
        key = (label, link.get("href"))
        if key in seen:
            continue
        seen.add(key)
        placeholders.append(
            SourceDocumentAssetPlaceholder(
                asset_kind="supplement",
                label=label,
                caption_hint=candidate_text,
            )
        )

    for heading in root.select(".supplementary-material .siTitle, h3.siTitle"):
        candidate_text = _clean_text(heading.get_text(" ", strip=True))
        label = _extract_label_from_text(
            candidate_text, SUPPLEMENT_PATTERN
        ) or _extract_label_from_text(candidate_text, SUPPLEMENT_SHORT_PATTERN)
        if label is None:
            continue
        key = (label, None)
        if key in seen:
            continue
        seen.add(key)
        placeholders.append(
            SourceDocumentAssetPlaceholder(
                asset_kind="supplement",
                label=label,
                caption_hint=candidate_text,
            )
        )
    return placeholders


def _extract_html_caption_text(node: Tag, selector: str) -> str | None:
    caption_node = node.select_one(selector)
    if caption_node is None:
        return None
    return _clean_text(caption_node.get_text(" ", strip=True))


def _append_unique_placeholder(
    placeholders: list[SourceDocumentAssetPlaceholder],
    seen_labels: set[str],
    placeholder: SourceDocumentAssetPlaceholder,
) -> None:
    if placeholder.label is None:
        placeholders.append(placeholder)
        return
    normalized_label = placeholder.label.lower()
    if normalized_label in seen_labels:
        return
    seen_labels.add(normalized_label)
    placeholders.append(placeholder)


def _extract_pdf_sections(
    pages: list[SourceDocumentPage],
) -> list[SourceDocumentSection]:
    sections: list[SourceDocumentSection] = []
    current_label = "Document"
    current_kind: SourceDocumentSectionKind = "other"
    current_start_page: int | None = None
    current_end_page: int | None = None
    current_lines: list[str] = []

    for page in pages:
        for line in page.text.splitlines():
            clean_line = _clean_text(line)
            if not clean_line:
                continue

            detected_heading = _detect_pdf_heading(clean_line)
            if detected_heading is not None:
                heading_label, heading_kind, heading_remainder = detected_heading
                if current_lines:
                    sections.append(
                        _build_pdf_section(
                            len(sections) + 1,
                            current_label,
                            current_kind,
                            current_start_page,
                            current_end_page,
                            current_lines,
                        )
                    )
                    current_lines = []
                current_label = heading_label
                current_kind = heading_kind
                current_start_page = page.page_number
                current_end_page = page.page_number
                if heading_remainder:
                    current_lines.append(heading_remainder)
                continue

            if current_start_page is None:
                current_start_page = page.page_number
                current_end_page = page.page_number
            current_end_page = page.page_number
            current_lines.append(clean_line)

    if current_lines:
        sections.append(
            _build_pdf_section(
                len(sections) + 1,
                current_label,
                current_kind,
                current_start_page,
                current_end_page,
                current_lines,
            )
        )

    if sections:
        return sections

    raw_text = _clean_text("\n\n".join(page.text for page in pages))
    return [
        SourceDocumentSection(
            section_id="section-1",
            label="Document",
            normalized_label="other",
            start_page_number=pages[0].page_number,
            end_page_number=pages[-1].page_number,
            text=raw_text,
        )
    ]


def _build_pdf_section(
    index: int,
    label: str,
    normalized_label: SourceDocumentSectionKind,
    start_page_number: int | None,
    end_page_number: int | None,
    lines: list[str],
) -> SourceDocumentSection:
    return SourceDocumentSection(
        section_id=f"section-{index}",
        label=label,
        normalized_label=normalized_label,
        start_page_number=start_page_number,
        end_page_number=end_page_number,
        text=_clean_text("\n".join(lines)),
    )


def _infer_pdf_title(
    pages: list[SourceDocumentPage],
    sections: list[SourceDocumentSection],
    pdf_metadata: dict[str, object],
) -> str | None:
    metadata_title = _extract_pdf_metadata_title(pdf_metadata)
    if metadata_title is not None:
        return metadata_title

    first_page_lines = [
        _clean_text(line) for line in pages[0].text.splitlines() if _clean_text(line)
    ]
    title_lines: list[str] = []
    for line in first_page_lines:
        if _is_probable_pdf_title_noise(line):
            continue
        line = _strip_pdf_title_prefix_noise(line)
        if not line:
            continue
        if _is_probable_author_line(line) or _normalize_label(line) == "abstract":
            break
        if _detect_heading_kind(line) is not None:
            continue
        title_lines.append(line)
        if len(title_lines) >= 5 or len(" ".join(title_lines)) >= 140:
            break

    if title_lines:
        return _clean_text(" ".join(title_lines))

    first_section = next(iter(sections), None)
    if first_section is None or first_section.label == "Document":
        return None
    return first_section.label


def _extract_pdf_metadata_title(pdf_metadata: dict[str, object]) -> str | None:
    raw_title = pdf_metadata.get("Title")
    if not isinstance(raw_title, str):
        return None
    cleaned_title = _clean_text(raw_title)
    if not cleaned_title or _is_probable_pdf_title_noise(cleaned_title):
        return None
    return cleaned_title


def _is_probable_pdf_title_noise(line: str) -> bool:
    normalized = _normalize_label(line)
    if normalized in {"plos one", "researcharticle", "open", "open access"}:
        return True
    if normalized.startswith("www.") or normalized.startswith("http"):
        return True
    return False


def _is_probable_author_line(line: str) -> bool:
    normalized = line.strip()
    if "@" in normalized:
        return True
    if len(normalized) > 120:
        return False
    return bool(re.search(r"\b[A-Z][a-z]+\b.*[,&]\s*\b[A-Z]", normalized))


def _strip_pdf_title_prefix_noise(line: str) -> str:
    stripped_line = re.sub(r"^(OPEN|Open Access)\s+", "", line).strip()
    return stripped_line


def _extract_pdf_asset_placeholders(
    pages: list[SourceDocumentPage],
    sections: list[SourceDocumentSection],
    *,
    kind: str,
) -> list[SourceDocumentAssetPlaceholder]:
    pattern = {
        "table": TABLE_PATTERN,
        "figure": FIGURE_PATTERN,
        "supplement": SUPPLEMENT_PATTERN,
    }[kind]
    seen: set[tuple[str, int]] = set()
    placeholders: list[SourceDocumentAssetPlaceholder] = []
    for page in pages:
        for match in pattern.finditer(page.text):
            label = _clean_text(match.group(1))
            key = (label.lower(), page.page_number)
            if key in seen:
                continue
            seen.add(key)
            placeholders.append(
                SourceDocumentAssetPlaceholder(
                    asset_kind=kind,  # type: ignore[arg-type]
                    label=label,
                    page_number=page.page_number,
                    section_label=_find_section_label_for_page(
                        sections, page.page_number
                    ),
                    caption_hint=label,
                )
            )
    return placeholders


def _find_section_label_for_page(
    sections: Iterable[SourceDocumentSection], page_number: int
) -> str | None:
    for section in sections:
        start_page = section.start_page_number
        end_page = section.end_page_number
        if start_page is None or end_page is None:
            continue
        if start_page <= page_number <= end_page:
            return section.label
    return None


def _with_inferred_title(
    metadata: SourceDocumentMetadata, inferred_title: str | None
) -> SourceDocumentMetadata:
    if metadata.title is not None or not inferred_title:
        return metadata
    return metadata.model_copy(update={"title": inferred_title})


def _detect_heading_kind(label: str) -> SourceDocumentSectionKind | None:
    clean_label = _normalize_label(label)
    if not clean_label or len(clean_label.split()) > 6:
        return None
    if not HEADING_PATTERN.match(clean_label):
        return None
    return _classify_section_label(clean_label)


def _detect_pdf_heading(
    label: str,
) -> tuple[str, SourceDocumentSectionKind, str | None] | None:
    candidate = _trim_pdf_heading_candidate(label)
    if not candidate:
        return None

    detected_kind = _detect_heading_kind(candidate)
    if detected_kind is not None:
        return (_canonicalize_heading_label(candidate), detected_kind, None)

    collapsed_label = _collapse_label(candidate)
    if not collapsed_label:
        return None

    best_prefix_match: tuple[str, SourceDocumentSectionKind, str] | None = None
    for canonical_label, heading_kind, aliases in PDF_SECTION_HEADINGS:
        for alias in aliases:
            if collapsed_label == alias:
                return (canonical_label, heading_kind, None)
            remainder = _consume_pdf_heading_prefix(candidate, alias)
            if remainder is None or not _is_probable_pdf_heading_remainder(remainder):
                continue
            if best_prefix_match is None or len(alias) > len(
                _collapse_label(best_prefix_match[0])
            ):
                best_prefix_match = (canonical_label, heading_kind, remainder)
    return best_prefix_match


def _trim_pdf_heading_candidate(label: str) -> str:
    candidate = _clean_text(label)
    previous_candidate = None
    while candidate and candidate != previous_candidate:
        previous_candidate = candidate
        candidate = re.sub(r"^[A-Za-z]?\d{4,}[A-Za-z0-9-]*\s+", "", candidate)
        candidate = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", candidate)
    return candidate


def _consume_pdf_heading_prefix(text: str, alias: str) -> str | None:
    text_index = 0
    alias_index = 0
    while text_index < len(text) and alias_index < len(alias):
        current_char = text[text_index].lower()
        if current_char.isalpha():
            if current_char != alias[alias_index]:
                return None
            alias_index += 1
            text_index += 1
            continue
        if current_char.isdigit():
            return None
        text_index += 1

    if alias_index != len(alias):
        return None

    return _clean_text(text[text_index:].lstrip(" :-–—.;,/"))


def _is_probable_pdf_heading_remainder(remainder: str) -> bool:
    if not remainder:
        return True
    return bool(re.match(r"^[A-Z0-9(]", remainder))


def _classify_section_label(label: str) -> SourceDocumentSectionKind:
    clean_label = _normalize_label(label)
    if clean_label == "abstract":
        return "abstract"
    if clean_label == "introduction":
        return "introduction"
    if clean_label in {
        "materials and methods",
        "material and methods",
        "methods",
        "experimental",
        "chromatographic conditions",
        "instrumentation",
        "sample preparation",
    }:
        return "methods"
    if clean_label in {"results", "results and discussion"}:
        return "results"
    if clean_label == "discussion":
        return "discussion"
    if clean_label in {"conclusion", "conclusions"}:
        return "conclusion"
    if clean_label == "references":
        return "references"
    return "other"


def _normalize_label(label: str) -> str:
    normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", label.strip().lower())
    normalized = normalized.rstrip(":")
    return re.sub(r"\s+", " ", normalized)


def _collapse_label(label: str) -> str:
    return re.sub(r"[^a-z]", "", _normalize_label(label))


def _canonicalize_heading_label(label: str) -> str:
    normalized_label = _normalize_label(label)
    for canonical_label, _, aliases in PDF_SECTION_HEADINGS:
        if _collapse_label(normalized_label) in aliases:
            return canonical_label
    return normalized_label.title()


def _extract_label_from_text(text: str | None, pattern: re.Pattern[str]) -> str | None:
    if not text:
        return None
    match = pattern.search(text)
    if match is None:
        return None
    return _clean_text(match.group(1))


def _strip_heading_prefix(label: str, text: str) -> str:
    if text.startswith(label):
        return _clean_text(text[len(label) :])
    return text


def _join_section_text(sections: Iterable[SourceDocumentSection]) -> str:
    return _clean_text("\n\n".join(section.text for section in sections))


def _clean_text(text: str) -> str:
    normalized = text.replace("\xa0", " ").replace("·", ".")
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()

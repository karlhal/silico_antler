import base64
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval_schemas import SourceDocumentMetadata
from app.source_document_ingestion import ingest_html_document, ingest_pdf_document

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_html_ingestion_extracts_sections_and_placeholders() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="html-doc-001",
        source_type="html",
        url="https://example.test/article",
    )

    document = ingest_html_document(
        metadata,
        (FIXTURES_DIR / "sample_hplc_article.html").read_text(),
    )

    assert document.source_document.title == "Open-access HPLC Example Article"
    assert document.pages == []
    assert [section.normalized_label for section in document.sections] == [
        "abstract",
        "methods",
        "results",
    ]
    assert "flow rate was 0.4 mL/min" in document.raw_text
    assert document.table_placeholders[0].label == "Table 1"
    assert document.figure_placeholders[0].label == "Fig. 1"
    assert document.supplement_placeholders[0].label == "Supplementary Table S1"


def test_html_ingestion_extracts_plos_style_placeholders() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="plos-doc-001",
        source_type="html",
        url="https://example.test/plos",
    )

    document = ingest_html_document(
        metadata,
        (FIXTURES_DIR / "sample_plos_article_excerpt.html").read_text(),
    )

    assert document.source_document.title == "PLOS HPLC Example"
    assert document.figure_placeholders[0].label == "Fig 1"
    assert document.table_placeholders[0].label == "Table 1"
    assert document.supplement_placeholders[0].label == "S1 Fig"


def test_html_ingestion_extracts_mdpi_style_placeholders() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="mdpi-doc-001",
        source_type="html",
        url="https://example.test/mdpi",
    )

    document = ingest_html_document(
        metadata,
        (FIXTURES_DIR / "sample_mdpi_article_excerpt.html").read_text(),
    )

    assert document.source_document.title == "MDPI HPLC Example"
    assert document.sections[1].normalized_label == "introduction"
    assert document.figure_placeholders[0].label == "Figure 1"
    assert document.table_placeholders[0].label == "Table 1"


def test_html_ingestion_filters_mdpi_back_matter_and_utility_sections() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="mdpi-doc-002",
        source_type="html",
        url="https://example.test/mdpi-filtered",
    )

    document = ingest_html_document(
        metadata,
        """
        <html>
          <head>
            <meta name="citation_title" content="MDPI Filter Example" />
          </head>
          <body>
            <div id="main-content">
              <section id="sec-abstract"><h2>Abstract</h2><div class="html-p">Short abstract.</div></section>
              <section id="sec-methods"><h2>Materials and Methods</h2><div class="html-p">Separation was performed on a C18 column with a 0.4 mL/min flow rate.</div></section>
              <section id="sec-conflicts"><h2>Conflicts of Interest</h2><div class="html-p">The authors declare no conflict of interest.</div></section>
              <section id="sec-data"><h2>Data Availability Statement</h2><div class="html-p">Data are available on request.</div></section>
              <div class="share-panel section" id="share-tools"><h2>Share and Cite</h2><div>Copy link.</div></div>
            </div>
          </body>
        </html>
        """,
    )

    assert document.source_document.title == "MDPI Filter Example"
    assert [section.label for section in document.sections] == [
        "Abstract",
        "Materials and Methods",
    ]


def test_pdf_ingestion_extracts_pages_sections_and_placeholders() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="pdf-doc-001",
        source_type="pdf",
        file_name="sample.pdf",
    )

    pdf_bytes = _build_simple_pdf(
        [
            "Open-access HPLC PDF Example",
            "Abstract",
            "A compact PDF example for C5.",
            "Materials and Methods",
            "Flow rate 0.4 mL/min on a C18 column.",
            "Table 1 Gradient profile",
            "Fig. 1 Example chromatogram",
            "Supplementary Table S1",
        ]
    )

    document = ingest_pdf_document(metadata, pdf_bytes)

    assert document.source_document.title == "Open-access HPLC PDF Example"
    assert len(document.pages) == 1
    assert document.pages[0].page_number == 1
    assert [section.normalized_label for section in document.sections] == [
        "other",
        "abstract",
        "methods",
    ]
    assert "Flow rate 0.4 mL/min" in document.raw_text
    assert document.table_placeholders[0].label == "Table 1"
    assert document.figure_placeholders[0].label == "Fig. 1"
    assert document.supplement_placeholders[0].label == "Supplementary Table S1"


def test_pdf_ingestion_accepts_base64_round_trip() -> None:
    pdf_bytes = _build_simple_pdf(
        ["Base64 PDF Example", "Methods", "Flow rate 0.5 mL/min"]
    )
    encoded = base64.b64encode(pdf_bytes).decode("ascii")

    assert encoded
    assert pdf_bytes == base64.b64decode(encoded)


def test_pdf_ingestion_detects_compact_plos_style_section_headings() -> None:
    metadata = SourceDocumentMetadata(
        source_document_id="pdf-doc-plos-001",
        source_type="pdf",
        file_name="plos-style.pdf",
    )

    pdf_bytes = _build_simple_pdf(
        [
            "PLOS ONE",
            "RESEARCHARTICLE",
            "Development of a RP-HPLC method for determination of glucose",
            "a1111111111 Abstract",
            "A compact abstract example.",
            "Materialsandmethods",
            "Instrumentation",
            "The flow rate was 1.0 mL/min.",
            "Resultsanddiscussion",
            "The PMP-glucose peak had a retention time of 16.7 min.",
            "Conclusions",
            "The method was robust.",
            "Supportinginformation",
            "S1Table Robustness study.",
            "References",
            "1. Example reference.",
        ]
    )

    document = ingest_pdf_document(metadata, pdf_bytes)

    assert [section.label for section in document.sections] == [
        "Document",
        "Abstract",
        "Materials and Methods",
        "Results and Discussion",
        "Conclusions",
        "Supporting Information",
        "References",
    ]
    assert [section.normalized_label for section in document.sections] == [
        "other",
        "abstract",
        "methods",
        "results",
        "conclusion",
        "other",
        "references",
    ]


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

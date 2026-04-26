import base64
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.source_document_registry import InMemorySourceDocumentRegistry

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

client = TestClient(app)


def test_register_source_document_from_html() -> None:
    _reset_registry()

    response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "html-api-001",
                "source_type": "html",
                "url": "https://example.test/html-api-001",
            },
            "html_content": (FIXTURES_DIR / "sample_hplc_article.html").read_text(),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["source_document"]["title"] == "Open-access HPLC Example Article"
    assert payload["sections"][1]["normalized_label"] == "methods"
    assert payload["table_placeholders"][0]["label"] == "Table 1"


def test_register_source_document_from_pdf_and_fetch_it() -> None:
    _reset_registry()
    pdf_base64 = base64.b64encode(
        _build_simple_pdf(
            [
                "PDF API Example",
                "Methods",
                "Flow rate 0.6 mL/min",
                "Table 2 Instrument settings",
            ]
        )
    ).decode("ascii")

    create_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "pdf-api-001",
                "source_type": "pdf",
                "file_name": "pdf-api-001.pdf",
            },
            "pdf_base64": pdf_base64,
        },
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["pages"][0]["page_number"] == 1
    assert created_payload["table_placeholders"][0]["label"] == "Table 2"

    get_response = client.get("/source-documents/pdf-api-001")

    assert get_response.status_code == 200
    fetched_payload = get_response.json()
    assert fetched_payload["source_document"]["source_document_id"] == "pdf-api-001"
    assert fetched_payload["raw_text"] == created_payload["raw_text"]


def test_register_source_document_rejects_duplicate_ids() -> None:
    _reset_registry()
    html_content = (FIXTURES_DIR / "sample_hplc_article.html").read_text()
    payload = {
        "source_document": {
            "source_document_id": "duplicate-001",
            "source_type": "html",
        },
        "html_content": html_content,
    }

    first_response = client.post("/source-documents/", json=payload)
    second_response = client.post("/source-documents/", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "Source document already registered: duplicate-001"
    )


def test_register_source_document_rejects_content_shape_mismatch() -> None:
    _reset_registry()

    response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "mismatch-001",
                "source_type": "html",
            },
            "pdf_base64": "Zm9v",
        },
    )

    assert response.status_code == 422
    assert "html_content is required" in response.text


def _reset_registry() -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()


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

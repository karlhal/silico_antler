from pathlib import Path
import sys

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.open_access_client import (
    OpenAccessPaperClient,
    _build_fetch_targets,
    _parse_openalex_abstract,
    _parse_openalex_work,
)
from app.recommendation_schemas import OpenAccessPaperCandidate


def test_parse_openalex_abstract_reconstructs_text_order() -> None:
    abstract = _parse_openalex_abstract(
        {"carotenoids": [1], "Plasma": [0], "analysis": [2]}
    )

    assert abstract == "Plasma carotenoids analysis"


def test_parse_openalex_work_extracts_open_access_candidate() -> None:
    payload = {
        "id": "https://openalex.org/W123",
        "display_name": "Open-access HPLC paper",
        "doi": "https://doi.org/10.1000/test-doi",
        "publication_year": 2024,
        "abstract_inverted_index": {"HPLC": [0], "paper": [1]},
        "open_access": {"is_oa": True},
        "best_oa_location": {
            "landing_page_url": "https://example.test/paper",
            "pdf_url": "https://example.test/paper.pdf",
            "source": {"display_name": "Example Journal"},
        },
    }

    candidate = _parse_openalex_work(payload)

    assert candidate is not None
    assert candidate.paper_id == "https://openalex.org/W123"
    assert candidate.doi == "10.1000/test-doi"
    assert candidate.pdf_url == "https://example.test/paper.pdf"
    assert candidate.source_name == "Example Journal"


def test_parse_openalex_work_can_fall_back_to_locations_with_fetchable_urls() -> None:
    payload = {
        "id": "https://openalex.org/W999",
        "display_name": "Open-access fallback paper",
        "publication_year": 2025,
        "open_access": {"is_oa": True},
        "best_oa_location": {"landing_page_url": None, "pdf_url": None},
        "locations": [
            {
                "landing_page_url": "https://example.test/fallback-paper",
                "pdf_url": "https://example.test/fallback-paper.pdf",
                "source": {"display_name": "Fallback Journal"},
            }
        ],
    }

    candidate = _parse_openalex_work(payload)

    assert candidate is not None
    assert candidate.url == "https://example.test/fallback-paper"
    assert candidate.pdf_url == "https://example.test/fallback-paper.pdf"
    assert candidate.source_name == "Fallback Journal"


def test_parse_openalex_work_prefers_repository_style_location_over_publisher_location() -> None:
    payload = {
        "id": "https://openalex.org/Wrepo",
        "display_name": "Open-access repository-backed paper",
        "publication_year": 2025,
        "open_access": {"is_oa": True},
        "best_oa_location": {
            "landing_page_url": "https://www.mdpi.com/1422-0067/17/10/1719",
            "pdf_url": "https://www.mdpi.com/1422-0067/17/10/1719/pdf",
            "source": {"display_name": "MDPI"},
        },
        "locations": [
            {
                "landing_page_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
                "pdf_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf",
                "source": {"display_name": "PubMed Central"},
            }
        ],
    }

    candidate = _parse_openalex_work(payload)

    assert candidate is not None
    assert candidate.url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"
    assert candidate.pdf_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf"
    assert candidate.source_name == "PubMed Central"
    assert candidate.alternate_urls == ["https://www.mdpi.com/1422-0067/17/10/1719"]
    assert candidate.alternate_pdf_urls == ["https://www.mdpi.com/1422-0067/17/10/1719/pdf"]


def test_build_fetch_targets_prefers_repository_pdf_before_blocked_publisher_html() -> None:
    candidate = OpenAccessPaperCandidate(
        paper_id="paper-repo-first",
        title="Repository-first paper",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        pdf_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf",
    )

    assert _build_fetch_targets(candidate) == [
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf", "pdf"),
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/", "html"),
    ]


def test_build_fetch_targets_includes_alternate_open_access_locations() -> None:
    candidate = OpenAccessPaperCandidate(
        paper_id="paper-with-alternates",
        title="Paper with alternate mirrors",
        url="https://www.mdpi.com/1422-0067/17/10/1719",
        pdf_url="https://www.mdpi.com/1422-0067/17/10/1719/pdf",
        alternate_urls=["https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"],
        alternate_pdf_urls=["https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf"],
    )

    assert _build_fetch_targets(candidate) == [
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/pdf/main.pdf", "pdf"),
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/", "html"),
        ("https://www.mdpi.com/1422-0067/17/10/1719/pdf", "pdf"),
        ("https://www.mdpi.com/1422-0067/17/10/1719", "html"),
    ]


def test_fetch_source_artifact_falls_back_to_pdf_when_html_landing_page_is_blocked(
    monkeypatch,
) -> None:
    candidate = OpenAccessPaperCandidate(
        paper_id="paper-blocked-html",
        title="Blocked HTML paper",
        url="https://example.test/paper",
        pdf_url="https://example.test/paper.pdf",
    )

    html_response = _FakeResponse(
        url=candidate.url,
        text="<html><body>Enable JavaScript and cookies to continue</body></html>",
        headers={"content-type": "text/html"},
    )
    pdf_response = _FakeResponse(
        url=candidate.pdf_url,
        content=b"%PDF-1.4 synthetic pdf payload",
        headers={"content-type": "application/pdf"},
    )

    monkeypatch.setattr(
        "app.open_access_client.httpx.Client",
        lambda **_: _FakeHttpxClient(
            {
                candidate.url: html_response,
                candidate.pdf_url: pdf_response,
            }
        ),
    )

    artifact = OpenAccessPaperClient().fetch_source_artifact(candidate)

    assert artifact.kind == "pdf"
    assert artifact.url == "https://example.test/paper.pdf"
    assert artifact.pdf_bytes == b"%PDF-1.4 synthetic pdf payload"


def test_fetch_source_artifact_retries_embedded_pdf_from_thin_html_landing_page(
    monkeypatch,
) -> None:
    candidate = OpenAccessPaperCandidate(
        paper_id="paper-embedded-pdf",
        title="Embedded PDF paper",
        url="https://example.test/paper",
        pdf_url=None,
    )

    html_response = _FakeResponse(
        url=candidate.url,
        text="""
        <html>
          <head>
            <meta name="citation_pdf_url" content="https://example.test/downloads/paper.pdf" />
            <meta name="citation_abstract_html_url" content="https://example.test/article/full" />
          </head>
          <body>Enable JavaScript to continue</body>
        </html>
        """,
        headers={"content-type": "text/html"},
    )
    pdf_response = _FakeResponse(
        url="https://example.test/downloads/paper.pdf",
        content=b"%PDF-1.4 embedded pdf payload",
        headers={"content-type": "application/pdf"},
    )

    monkeypatch.setattr(
        "app.open_access_client.httpx.Client",
        lambda **_: _FakeHttpxClient(
            {
                candidate.url: html_response,
                "https://example.test/downloads/paper.pdf": pdf_response,
            }
        ),
    )

    artifact = OpenAccessPaperClient().fetch_source_artifact(candidate)

    assert artifact.kind == "pdf"
    assert artifact.url == "https://example.test/downloads/paper.pdf"
    assert artifact.pdf_bytes == b"%PDF-1.4 embedded pdf payload"


def test_open_run_reuses_one_http_client_across_search_and_fetch(monkeypatch) -> None:
    search_url = "https://api.openalex.org/works"
    candidate_url = "https://example.test/paper"
    candidate_pdf_url = "https://example.test/paper.pdf"
    constructed_clients: list[_FakeHttpxClient] = []

    search_response = _FakeResponse(
        url=search_url,
        json_payload={
            "results": [
                {
                    "id": "https://openalex.org/W123",
                    "display_name": "Reusable client paper",
                    "doi": "https://doi.org/10.1000/test-doi",
                    "publication_year": 2024,
                    "open_access": {"is_oa": True},
                    "best_oa_location": {
                        "landing_page_url": candidate_url,
                        "pdf_url": candidate_pdf_url,
                        "source": {"display_name": "Example Journal"},
                    },
                }
            ]
        },
        headers={"content-type": "application/json"},
    )
    pdf_response = _FakeResponse(
        url=candidate_pdf_url,
        content=b"%PDF-1.4 reusable client payload",
        headers={"content-type": "application/pdf"},
    )

    def _build_client(**_: object) -> _FakeHttpxClient:
        client = _FakeHttpxClient(
            {
                search_url: search_response,
                candidate_pdf_url: pdf_response,
            }
        )
        constructed_clients.append(client)
        return client

    monkeypatch.setattr("app.open_access_client.httpx.Client", _build_client)

    client = OpenAccessPaperClient()
    with client.open_run() as run_client:
        candidates = run_client.search_papers("reusable client paper", max_papers=1)
        artifact = run_client.fetch_source_artifact(candidates[0])

    assert len(constructed_clients) == 1
    assert constructed_clients[0].requested_urls == [search_url, candidate_pdf_url]
    assert artifact.kind == "pdf"
    assert artifact.pdf_bytes == b"%PDF-1.4 reusable client payload"


class _FakeResponse:
    def __init__(
        self,
        *,
        url: str | None,
        text: str = "",
        content: bytes | None = None,
        json_payload: object | None = None,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> None:
        self.url = url or "https://example.test/unknown"
        self.text = text
        self.content = content if content is not None else text.encode()
        self._json_payload = json_payload
        self.headers = headers or {}
        self.status_code = status_code

    def json(self) -> object:
        if self._json_payload is None:
            raise AssertionError("JSON payload not configured for fake response")
        return self._json_payload

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return
        request = httpx.Request("GET", self.url)
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError(
            f"{self.status_code} error",
            request=request,
            response=response,
        )


class _FakeHttpxClient:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self._responses = responses
        self.requested_urls: list[str] = []

    def __enter__(self) -> "_FakeHttpxClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **_: object) -> _FakeResponse:
        self.requested_urls.append(url)
        return self._responses[url]

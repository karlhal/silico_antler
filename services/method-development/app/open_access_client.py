from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import re
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

from .recommendation_schemas import FetchedSourceArtifact, OpenAccessPaperCandidate


class OpenAccessClientError(RuntimeError):
    pass


class OpenAccessPaperClientSession(Protocol):
    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]: ...

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact: ...


class OpenAccessPaperClient:
    def __init__(self, *, timeout_sec: int = 20) -> None:
        self._timeout_sec = timeout_sec

    @contextmanager
    def open_run(self) -> Iterator[OpenAccessPaperClientSession]:
        if type(self) is not OpenAccessPaperClient:
            yield self
            return

        with self._build_http_client() as http_client:
            yield _RunScopedOpenAccessPaperClient(self, http_client)

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        with self._build_http_client() as http_client:
            return self._search_papers_with_client(
                query,
                max_papers=max_papers,
                http_client=http_client,
            )

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        with self._build_http_client() as http_client:
            return self._fetch_source_artifact_with_client(
                candidate,
                http_client=http_client,
            )

    def _build_http_client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout_sec, follow_redirects=True)

    def _search_papers_with_client(
        self,
        query: str,
        *,
        max_papers: int,
        http_client: httpx.Client,
    ) -> list[OpenAccessPaperCandidate]:
        try:
            response = http_client.get(
                "https://api.openalex.org/works",
                params={
                    "search": query,
                    "filter": "is_oa:true",
                    "per-page": max_papers,
                    "sort": "relevance_score:desc",
                },
                headers=_request_headers("https://api.openalex.org/works"),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OpenAccessClientError(f"OpenAlex search failed: {exc}") from exc

        payload = response.json()
        results = payload.get("results", [])
        candidates: list[OpenAccessPaperCandidate] = []
        for item in results:
            candidate = _parse_openalex_work(item)
            if candidate is not None and (candidate.url or candidate.pdf_url):
                candidates.append(candidate)
        return candidates

    def _fetch_source_artifact_with_client(
        self,
        candidate: OpenAccessPaperCandidate,
        *,
        http_client: httpx.Client,
    ) -> FetchedSourceArtifact:
        fetch_targets = _build_fetch_targets(candidate)
        if not fetch_targets:
            raise OpenAccessClientError(
                f"Open-access candidate '{candidate.title}' does not expose a fetchable URL"
            )

        attempt_errors: list[str] = []
        attempted_urls: set[str] = set()
        index = 0
        while index < len(fetch_targets):
            fetch_url, preferred_kind = fetch_targets[index]
            index += 1
            if fetch_url in attempted_urls:
                continue
            attempted_urls.add(fetch_url)
            try:
                response = http_client.get(
                    fetch_url,
                    headers=_request_headers(fetch_url),
                )
            except httpx.HTTPError as exc:
                attempt_errors.append(f"{preferred_kind} fetch failed: {exc}")
                continue
            if response.status_code == 403:
                pmc_retry = _derive_pmc_fallback_url(fetch_url)
                if pmc_retry and pmc_retry not in attempted_urls and not any(
                    u == pmc_retry for u, _ in fetch_targets
                ):
                    fetch_targets.append((pmc_retry, "html"))
                attempt_errors.append(f"{preferred_kind} returned 403 for {fetch_url}")
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                attempt_errors.append(f"{preferred_kind} fetch failed: {exc}")
                continue

            content_type = response.headers.get("content-type", "").lower()
            is_pdf = (
                preferred_kind == "pdf"
                or "application/pdf" in content_type
                or fetch_url.lower().endswith(".pdf")
                or response.content.startswith(b"%PDF")
            )
            if is_pdf:
                return FetchedSourceArtifact(
                    paper_id=candidate.paper_id,
                    kind="pdf",
                    title=candidate.title,
                    abstract=candidate.abstract,
                    doi=candidate.doi,
                    url=fetch_url,
                    published_year=candidate.published_year,
                    file_name=_safe_file_name(candidate.title, suffix=".pdf"),
                    pdf_bytes=response.content,
                )

            if _should_fallback_from_html(response.text):
                discovered_targets = _extract_embedded_fetch_targets(
                    response.text,
                    fetch_url,
                )
                appended_target = False
                for discovered_url, discovered_kind in discovered_targets:
                    if discovered_url in attempted_urls or any(
                        existing_url == discovered_url
                        for existing_url, _ in fetch_targets
                    ):
                        continue
                    fetch_targets.append((discovered_url, discovered_kind))
                    appended_target = True
                if appended_target:
                    attempt_errors.append(
                        "html fetch returned a thin landing page but exposed follow-up fetch targets"
                    )
                    continue
                attempt_errors.append(
                    "html fetch returned a thin or blocked landing page"
                )
                continue

            return FetchedSourceArtifact(
                paper_id=candidate.paper_id,
                kind="html",
                title=candidate.title,
                abstract=candidate.abstract,
                doi=candidate.doi,
                url=fetch_url,
                published_year=candidate.published_year,
                file_name=_safe_file_name(candidate.title, suffix=".html"),
                html_content=response.text,
            )

        joined_errors = "; ".join(attempt_errors) or "no successful fetch attempts"
        raise OpenAccessClientError(
            f"Open-access fetch failed for '{candidate.title}': {joined_errors}"
        )


class _RunScopedOpenAccessPaperClient:
    def __init__(
        self,
        owner: OpenAccessPaperClient,
        http_client: httpx.Client,
    ) -> None:
        self._owner = owner
        self._http_client = http_client

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        return self._owner._search_papers_with_client(
            query,
            max_papers=max_papers,
            http_client=self._http_client,
        )

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        return self._owner._fetch_source_artifact_with_client(
            candidate,
            http_client=self._http_client,
        )


def _extract_pmc_id(payload: dict) -> str | None:
    ids = payload.get("ids") or {}
    pmcid = ids.get("pmcid")
    if isinstance(pmcid, str) and pmcid.startswith("PMC"):
        return pmcid
    for location in (payload.get("locations") or []):
        landing = location.get("landing_page_url") or ""
        match = re.search(r"pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)", landing)
        if match:
            return match.group(1)
    return None


def _try_pmc_fulltext_url(url: str, pmc_id: str | None) -> str | None:
    if pmc_id:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
    return None


def _parse_openalex_work(payload: dict) -> OpenAccessPaperCandidate | None:
    title = payload.get("display_name")
    if not title:
        return None
    ranked_locations = _rank_open_access_locations(payload)
    best_location = ranked_locations[0] if ranked_locations else {}
    source = best_location.get("source") or {}
    alternate_urls: list[str] = []
    alternate_pdf_urls: list[str] = []
    for location in ranked_locations[1:]:
        landing_page_url = location.get("landing_page_url")
        pdf_url = location.get("pdf_url")
        if landing_page_url and landing_page_url not in alternate_urls:
            alternate_urls.append(landing_page_url)
        if pdf_url and pdf_url not in alternate_pdf_urls:
            alternate_pdf_urls.append(pdf_url)
    pmc_id = _extract_pmc_id(payload)
    pmc_url = _try_pmc_fulltext_url("", pmc_id)
    primary_url = best_location.get("landing_page_url")
    if pmc_url and pmc_url != primary_url and pmc_url not in alternate_urls:
        alternate_urls.insert(0, pmc_url)
    return OpenAccessPaperCandidate(
        paper_id=str(payload.get("id") or title),
        title=title,
        doi=_strip_doi_prefix(payload.get("doi")),
        url=best_location.get("landing_page_url"),
        pdf_url=best_location.get("pdf_url"),
        alternate_urls=alternate_urls,
        alternate_pdf_urls=alternate_pdf_urls,
        published_year=payload.get("publication_year"),
        source_name=source.get("display_name"),
        abstract=_parse_openalex_abstract(payload.get("abstract_inverted_index")),
        open_access=bool(payload.get("open_access", {}).get("is_oa", True)),
    )


def _parse_openalex_abstract(abstract_index: dict | None) -> str | None:
    if not abstract_index:
        return None
    positions: dict[int, str] = {}
    for token, indexes in abstract_index.items():
        for index in indexes:
            positions[int(index)] = token
    if not positions:
        return None
    return " ".join(token for _, token in sorted(positions.items()))


def _strip_doi_prefix(value: str | None) -> str | None:
    if value is None:
        return None
    return value.removeprefix("https://doi.org/")


def _safe_file_name(title: str, *, suffix: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-")
    return f"{normalized[:80] or 'paper'}{suffix}"


def _pick_best_open_access_location(payload: dict) -> dict:
    ranked_locations = _rank_open_access_locations(payload)
    return ranked_locations[0] if ranked_locations else {}


def _rank_open_access_locations(payload: dict) -> list[dict]:
    locations = [
        payload.get("best_oa_location"),
        payload.get("primary_location"),
        *(payload.get("locations") or []),
    ]
    ranked_locations: list[tuple[int, dict]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for location in locations:
        if not isinstance(location, dict):
            continue
        landing_page_url = location.get("landing_page_url")
        pdf_url = location.get("pdf_url")
        key = (landing_page_url, pdf_url)
        if key in seen:
            continue
        seen.add(key)
        if not landing_page_url and not pdf_url:
            continue
        ranked_locations.append((_location_priority(location), location))
    if not ranked_locations:
        return []
    ranked_locations.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked_locations]


def _location_priority(location: dict) -> int:
    score = 0
    landing_page_url = location.get("landing_page_url")
    pdf_url = location.get("pdf_url")
    if location.get("landing_page_url"):
        score += 2
    if location.get("pdf_url"):
        score += 2
    source = location.get("source") or {}
    if source.get("display_name"):
        score += 1
    score += _location_fetchability_priority(landing_page_url, pdf_url)
    return score


def _location_fetchability_priority(
    landing_page_url: str | None, pdf_url: str | None
) -> int:
    score = 0
    for url in (landing_page_url, pdf_url):
        host = _normalized_host(url)
        if not host:
            continue
        if _is_preferred_open_access_host(host):
            score += 8
        if _is_deprioritized_publisher_host(host):
            score -= 6
    return score


def _build_fetch_targets(candidate: OpenAccessPaperCandidate) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    ordered_urls = [
        (candidate.url, "html"),
        (candidate.pdf_url, "pdf"),
        *((url, "html") for url in candidate.alternate_urls),
        *((url, "pdf") for url in candidate.alternate_pdf_urls),
    ]
    for url, kind in ordered_urls:
        if not url:
            continue
        normalized = url.strip()
        if not normalized:
            continue
        if any(existing_url == normalized for existing_url, _ in targets):
            continue
        targets.append((normalized, kind))
    targets.sort(
        key=lambda item: (
            _fetch_target_priority(item[0], item[1]),
            item[1] == "html",
        ),
        reverse=True,
    )
    return targets


def _fetch_target_priority(url: str, kind: str) -> int:
    host = _normalized_host(url)
    score = 0
    if kind == "pdf":
        score += 1
    if _is_preferred_open_access_host(host):
        score += 10
    if _is_deprioritized_publisher_host(host):
        score -= 8
    return score


def _should_fallback_from_html(html: str) -> bool:
    normalized = re.sub(r"\s+", " ", html).lower()
    blocked_markers = (
        "enable javascript",
        "enable cookies",
        "access denied",
        "captcha",
        "cloudflare",
        "checking your browser",
        "just a moment",
    )
    if any(marker in normalized for marker in blocked_markers):
        return True
    if len(normalized) < 1200:
        return True
    article_markers = ("<article", "<section", "<p", "materials and methods", "results")
    return not any(marker in normalized for marker in article_markers)


def _extract_embedded_fetch_targets(
    html: str, base_url: str
) -> list[tuple[str, str]]:
    patterns = (
        (r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']', "pdf"),
        (r'<meta[^>]+name=["\']fulltext_pdf["\'][^>]+content=["\']([^"\']+)["\']', "pdf"),
        (r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/pdf["\'][^>]+href=["\']([^"\']+)["\']', "pdf"),
        (r'<meta[^>]+name=["\']citation_abstract_html_url["\'][^>]+content=["\']([^"\']+)["\']', "html"),
        (r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', "html"),
        (r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', "html"),
        (r'<a[^>]+href=["\']([^"\']+pdf[^"\']*)["\']', "pdf"),
    )
    discovered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, kind in patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            resolved = urljoin(base_url, match.group(1).strip())
            if not resolved or resolved in seen:
                continue
            seen.add(resolved)
            discovered.append((resolved, kind))
    discovered.sort(
        key=lambda item: (
            _fetch_target_priority(item[0], item[1]),
            item[1] == "html",
        ),
        reverse=True,
    )
    return discovered


def _derive_pmc_fallback_url(url: str) -> str | None:
    """Convert a PubMed abstract URL to the PMC full-text URL when the PMC ID is in the path."""
    match = re.search(r"pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)", url)
    if match:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{match.group(1)}/"
    return None


def _request_headers(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    is_ncbi = "ncbi.nlm.nih.gov" in host or "europepmc.org" in host
    if is_ncbi:
        user_agent = "Silico/1.0 (HPLC method research; contact@silico.bio)"
        accept = "text/html,application/xhtml+xml"
    else:
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        accept = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/pdf;q=0.8,*/*;q=0.7"
        )
    headers = {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if origin:
        headers["Referer"] = origin
    return headers


def _normalized_host(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


def _is_preferred_open_access_host(host: str) -> bool:
    preferred_hosts = (
        "pmc.ncbi.nlm.nih.gov",
        "ncbi.nlm.nih.gov",
        "europepmc.org",
        "journals.plos.org",
        "plos.org",
        "biorxiv.org",
        "medrxiv.org",
    )
    return any(host == preferred or host.endswith(f".{preferred}") for preferred in preferred_hosts)


def _is_deprioritized_publisher_host(host: str) -> bool:
    deprioritized_hosts = (
        "mdpi.com",
        "onlinelibrary.wiley.com",
        "analyticalsciencejournals.onlinelibrary.wiley.com",
        "portlandpress.com",
        "academic.oup.com",
    )
    return any(host == blocked or host.endswith(f".{blocked}") for blocked in deprioritized_hosts)

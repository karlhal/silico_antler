from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

SMILES_LOOKUP_FAILURE_DETAIL = "Name lookup failed. Public databases did not respond."
SMILES_LOOKUP_NOT_FOUND_DETAIL = "Molecule not found."

logger = logging.getLogger("silico.api")


class LookupUnavailableError(RuntimeError):
    """Raised when lookup services fail and no fallback result is available."""


class LookupNotFoundError(RuntimeError):
    """Raised when lookup services respond normally but return no match."""


class UpstreamLookupError(RuntimeError):
    """Raised when an upstream naming service fails unexpectedly."""


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _ensure_lookup_status(status_code: int, source: str) -> None:
    if status_code not in {200, 404}:
        raise UpstreamLookupError(f"{source} returned HTTP {status_code}")


async def resolve_pubchem(smiles: str) -> tuple[str | None, str | None, list[str]]:
    escaped = quote(smiles, safe="")
    candidates: list[str] = []
    timeout = 8.0
    async with httpx.AsyncClient(timeout=timeout) as client:
        property_url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/"
            f"{escaped}/property/Title,IUPACName/JSON"
        )
        property_response = await client.get(property_url)
        if property_response.status_code == 200:
            data = property_response.json()
            properties = data.get("PropertyTable", {}).get("Properties", [])
            if properties:
                entry = properties[0]
                title = entry.get("Title")
                iupac = entry.get("IUPACName")
                candidates = [name for name in [title, iupac] if isinstance(name, str) and name.strip()]
                preferred = _first_non_empty(candidates)
                if preferred:
                    source = "pubchem:title" if preferred == title else "pubchem:iupac"
                    return preferred, source, _dedupe(candidates)
        else:
            _ensure_lookup_status(property_response.status_code, "PubChem property lookup")

        synonyms_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{escaped}/synonyms/JSON"
        synonyms_response = await client.get(synonyms_url)
        if synonyms_response.status_code == 200:
            data = synonyms_response.json()
            info = data.get("InformationList", {}).get("Information", [])
            if info:
                raw_synonyms = info[0].get("Synonym", [])
                if isinstance(raw_synonyms, list):
                    candidates = _dedupe(
                        [item.strip() for item in raw_synonyms if isinstance(item, str) and item.strip()]
                    )
                    if candidates:
                        return candidates[0], "pubchem:synonym", candidates[:10]
        else:
            _ensure_lookup_status(synonyms_response.status_code, "PubChem synonym lookup")

    return None, None, []


async def resolve_cactus(smiles: str) -> tuple[str | None, str | None]:
    escaped = quote(smiles, safe="")
    url = f"https://cactus.nci.nih.gov/chemical/structure/{escaped}/iupac_name"
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(url)
    if response.status_code == 404:
        return None, None
    _ensure_lookup_status(response.status_code, "CACTUS lookup")
    text = response.text.strip()
    if not text:
        return None, None
    return text, "cactus:iupac"


async def resolve_smiles_name_with_fallback(smiles: str) -> tuple[str, str, list[str]]:
    lookup_failures: list[str] = []

    try:
        name, source, candidates = await resolve_pubchem(smiles)
    except Exception as exc:
        logger.warning("PubChem lookup failed for SMILES %s: %s", smiles, exc)
        lookup_failures.append("pubchem")
        name, source, candidates = None, None, []

    if name and source:
        return name, source, candidates

    try:
        cactus_name, cactus_source = await resolve_cactus(smiles)
    except Exception as exc:
        logger.warning("CACTUS lookup failed for SMILES %s: %s", smiles, exc)
        lookup_failures.append("cactus")
        cactus_name, cactus_source = None, None

    if cactus_name and cactus_source:
        return cactus_name, cactus_source, [cactus_name]

    if lookup_failures:
        raise LookupUnavailableError(SMILES_LOOKUP_FAILURE_DETAIL)
    raise LookupNotFoundError(SMILES_LOOKUP_NOT_FOUND_DETAIL)

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol
from urllib.parse import quote

import httpx

from .compound_context_schemas import CompoundContext, CompoundSourceIds


class CompoundContextClientError(RuntimeError):
    pass


class CompoundContextClientSession(Protocol):
    def resolve_compound(
        self,
        *,
        label: str | None = None,
        smiles: str | None = None,
    ) -> CompoundContext: ...


class PubChemCompoundContextClient:
    def __init__(self, *, timeout_sec: int = 8, synonym_limit: int = 8) -> None:
        self._timeout_sec = timeout_sec
        self._synonym_limit = synonym_limit

    @contextmanager
    def open_run(self) -> Iterator[CompoundContextClientSession]:
        if type(self) is not PubChemCompoundContextClient:
            yield self
            return

        with httpx.Client(timeout=self._timeout_sec, follow_redirects=True) as client:
            yield _RunScopedPubChemCompoundContextClient(self, client)

    def resolve_compound(
        self,
        *,
        label: str | None = None,
        smiles: str | None = None,
    ) -> CompoundContext:
        with httpx.Client(timeout=self._timeout_sec, follow_redirects=True) as client:
            return self._resolve_with_client(label=label, smiles=smiles, client=client)

    def _resolve_with_client(
        self,
        *,
        label: str | None,
        smiles: str | None,
        client: httpx.Client,
    ) -> CompoundContext:
        normalized_label = _clean_input(label)
        normalized_smiles = _clean_input(smiles)
        if not normalized_label and not normalized_smiles:
            return CompoundContext(
                input_label=normalized_label,
                input_smiles=normalized_smiles,
                warnings=["No compound name or SMILES was supplied for lookup."],
                confidence="unresolved",
            )

        namespace = "smiles" if normalized_smiles else "name"
        identifier = normalized_smiles or normalized_label or ""
        encoded_identifier = quote(identifier, safe="")
        property_path = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
            f"{namespace}/{encoded_identifier}/property/"
            "Title,MolecularFormula,MolecularWeight,CanonicalSMILES/JSON"
        )

        try:
            property_response = client.get(property_path, headers=_request_headers())
            property_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return CompoundContext(
                    input_label=normalized_label,
                    input_smiles=normalized_smiles,
                    lookup_sources=["pubchem"],
                    warnings=["PubChem did not return a matching compound."],
                    confidence="unresolved",
                )
            raise CompoundContextClientError(f"PubChem property lookup failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise CompoundContextClientError(f"PubChem property lookup failed: {exc}") from exc

        properties = (
            property_response.json()
            .get("PropertyTable", {})
            .get("Properties", [])
        )
        if not properties:
            return CompoundContext(
                input_label=normalized_label,
                input_smiles=normalized_smiles,
                lookup_sources=["pubchem"],
                warnings=["PubChem returned no compound properties."],
                confidence="unresolved",
            )

        primary = properties[0]
        cid = str(primary.get("CID") or "").strip() or None
        synonyms: list[str] = []
        warnings: list[str] = []
        if cid:
            synonyms, synonym_warnings = self._fetch_synonyms(cid, client=client)
            warnings.extend(synonym_warnings)

        resolved_name = _clean_input(primary.get("Title")) or _first_synonym(synonyms)
        confidence = "high" if cid and (normalized_smiles or resolved_name) else "medium"

        return CompoundContext(
            input_label=normalized_label,
            input_smiles=normalized_smiles,
            resolved_name=resolved_name,
            canonical_smiles=_clean_input(primary.get("CanonicalSMILES")),
            source_ids=CompoundSourceIds(pubchem_cid=cid),
            formula=_clean_input(primary.get("MolecularFormula")),
            molecular_weight=_coerce_float(primary.get("MolecularWeight")),
            synonyms=synonyms,
            lookup_sources=["pubchem"],
            warnings=warnings,
            confidence=confidence,
        )

    def _fetch_synonyms(
        self,
        cid: str,
        *,
        client: httpx.Client,
    ) -> tuple[list[str], list[str]]:
        path = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
            f"cid/{quote(cid, safe='')}/synonyms/JSON"
        )
        try:
            response = client.get(path, headers=_request_headers())
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return [], [f"PubChem synonym lookup failed: {exc}"]

        raw_synonyms = (
            response.json()
            .get("InformationList", {})
            .get("Information", [{}])[0]
            .get("Synonym", [])
        )
        synonyms: list[str] = []
        seen: set[str] = set()
        for raw in raw_synonyms:
            synonym = _clean_input(raw)
            if not synonym:
                continue
            key = synonym.lower()
            if key in seen:
                continue
            seen.add(key)
            synonyms.append(synonym)
            if len(synonyms) >= self._synonym_limit:
                break
        warnings = (
            [f"PubChem synonyms truncated to {self._synonym_limit} entries."]
            if len(raw_synonyms) > self._synonym_limit
            else []
        )
        return synonyms, warnings


class _RunScopedPubChemCompoundContextClient:
    def __init__(
        self,
        owner: PubChemCompoundContextClient,
        client: httpx.Client,
    ) -> None:
        self._owner = owner
        self._client = client

    def resolve_compound(
        self,
        *,
        label: str | None = None,
        smiles: str | None = None,
    ) -> CompoundContext:
        return self._owner._resolve_with_client(
            label=label,
            smiles=smiles,
            client=self._client,
        )


def _request_headers() -> dict[str, str]:
    return {"Accept": "application/json", "User-Agent": "silico-method-development/0.1"}


def _clean_input(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split()).strip()
    return cleaned or None


def _coerce_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_synonym(synonyms: list[str]) -> str | None:
    return synonyms[0] if synonyms else None

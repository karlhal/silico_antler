from __future__ import annotations

from typing import Literal

from pydantic import Field

from .retrieval_schemas import RetrievalBaseModel

CompoundContextConfidence = Literal["high", "medium", "low", "unresolved"]


class CompoundSourceIds(RetrievalBaseModel):
    pubchem_cid: str | None = Field(default=None, min_length=1, max_length=80)
    chembl_id: str | None = Field(default=None, min_length=1, max_length=80)


class CompoundContext(RetrievalBaseModel):
    input_label: str | None = Field(default=None, min_length=1, max_length=200)
    input_smiles: str | None = Field(default=None, min_length=1, max_length=400)
    resolved_name: str | None = Field(default=None, min_length=1, max_length=300)
    canonical_smiles: str | None = Field(default=None, min_length=1, max_length=500)
    source_ids: CompoundSourceIds = Field(default_factory=CompoundSourceIds)
    formula: str | None = Field(default=None, min_length=1, max_length=120)
    molecular_weight: float | None = Field(default=None, ge=0.0, le=100000.0)
    synonyms: list[str] = Field(default_factory=list)
    lookup_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: CompoundContextConfidence = "unresolved"


class ExternalEvidenceTrace(RetrievalBaseModel):
    query_terms_used: list[str] = Field(default_factory=list)
    source_clients_attempted: list[str] = Field(default_factory=list)
    source_clients_succeeded: list[str] = Field(default_factory=list)
    source_clients_failed: list[str] = Field(default_factory=list)
    truncation_warnings: list[str] = Field(default_factory=list)
    skipped_reason_counts: dict[str, int] = Field(default_factory=dict)

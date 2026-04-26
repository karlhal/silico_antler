from __future__ import annotations

from contextlib import contextmanager

from app.compound_context import build_recommendation_compound_context
from app.compound_context_schemas import CompoundContext, CompoundSourceIds
from app.recommendation_schemas import MethodRecommendationRequest


class _FakeCompoundContextClient:
    @contextmanager
    def open_run(self):
        yield self

    def resolve_compound(
        self,
        *,
        label: str | None = None,
        smiles: str | None = None,
    ) -> CompoundContext:
        return CompoundContext(
            input_label=label,
            input_smiles=smiles,
            resolved_name="Caffeine",
            canonical_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            source_ids=CompoundSourceIds(pubchem_cid="2519"),
            formula="C8H10N4O2",
            molecular_weight=194.19,
            synonyms=[
                "Caffeine",
                "1,3,7-trimethylxanthine",
                "Guaranine",
                "Methyltheobromine",
            ],
            lookup_sources=["pubchem"],
            warnings=["PubChem synonyms truncated to 4 entries."],
            confidence="high",
        )


def test_compound_context_builds_query_terms_and_trace() -> None:
    request = MethodRecommendationRequest(
        request_text="Recommend an LC-MS method for caffeine in plasma",
        analyte_name="caffeine",
        target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        matrix_hint="human plasma",
        require_mass_spectrometry=True,
        source_mode="open_access",
    )

    with _FakeCompoundContextClient().open_run() as client:
        context = build_recommendation_compound_context(request, client)

    assert context.target is not None
    assert context.target.resolved_name == "Caffeine"
    assert context.target.source_ids.pubchem_cid == "2519"
    assert context.trace.source_clients_attempted == ["pubchem"]
    assert context.trace.source_clients_succeeded == ["pubchem"]
    assert "Caffeine" in context.trace.query_terms_used
    assert "LC-MS/MS" in context.trace.query_terms_used
    assert context.trace.truncation_warnings

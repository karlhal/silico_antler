import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .ai_runtime_settings import load_ai_runtime_settings
from .c12_orchestration_router import router as c12_orchestration_router
from .chemistry import InvalidSmilesError, canonicalize_smiles
from .compound_context_client import PubChemCompoundContextClient
from .gemini_orchestration_client import (
    GeminiClientError,
    GeminiOrchestrationClient,
    GroqOrchestrationClient,
    OpenRouterOrchestrationClient,
    OrchestrationClientError,
    ZaiOrchestrationClient,
    _BaseOrchestrationClient,
    create_orchestration_client,
)
from .provider_pool import ProviderPool, ProviderSlot
from .hplc_extraction_router import router as hplc_extraction_router
from .open_access_client import OpenAccessPaperClient
from .recommendation_runtime import increment_failure_counter, snapshot_failure_counters
from .recommendation_schemas import RecommendationErrorDetail
from .review_record_materialization import sync_promoted_review_records
from .sqlite_review_record_store import SqliteReviewRecordStore
from .recommendation_job_store import RecommendationJobStore
from .review_records_router import router as review_records_router
from .retrieval_schemas import (
    RetrievalMatchedEntity,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
    RetrievalQueryResult,
)
from .retrieval_store import RetrievalStore, SeededRetrievalStore
from .milvus_retrieval_store import MilvusRetrievalStore
from .source_document_registry import InMemorySourceDocumentRegistry
from .source_documents_router import router as source_documents_router
from .recommendations_router import router as recommendations_router
from .limiters import limiter

def _build_llm_client(settings) -> _BaseOrchestrationClient:
    from rich import print as rprint

    if not settings.provider_pool_enabled:
        return create_orchestration_client(settings)

    slots = []
    if settings.zai_api_key:
        slots.append(ProviderSlot(
            client=ZaiOrchestrationClient(settings),
            planner_model="glm-4.6",
            worker_model="glm-4-plus",
            max_concurrency=20,
        ))
    if settings.google_api_key:
        slots.append(ProviderSlot(
            client=GeminiOrchestrationClient(settings),
            planner_model="gemini-2.5-pro",
            worker_model="gemini-2.5-flash",
            max_concurrency=12,
        ))
    if settings.groq_api_key:
        slots.append(ProviderSlot(
            client=GroqOrchestrationClient(settings),
            planner_model="llama-3.3-70b-versatile",
            worker_model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_concurrency=5,
        ))
    if settings.openrouter_api_key:
        slots.append(ProviderSlot(
            client=OpenRouterOrchestrationClient(settings),
            planner_model="google/gemma-4-31b-it:free",
            worker_model="google/gemma-4-31b-it:free",
            max_concurrency=2,
        ))
    if not slots:
        raise OrchestrationClientError("No API keys configured for provider pool")

    total_slots = sum(s.max_concurrency for s in slots)
    rprint(
        f"[green]Provider pool: {len(slots)} providers, {total_slots} total concurrent slots[/green]"
    )
    return ProviderPool(slots)


app = FastAPI(
    title="Silico Method Development Service",
    version="0.1.0",
)

app.state.limiter = limiter
if os.environ.get("TESTING") == "true":
    app.state.limiter.enabled = False
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if os.environ.get("USE_MILVUS", "true").lower() == "true":
    retrieval_store: RetrievalStore = MilvusRetrievalStore()
else:
    retrieval_store: RetrievalStore = SeededRetrievalStore.from_seed_file()
review_record_store = SqliteReviewRecordStore.from_default_path()
sync_promoted_review_records(review_record_store.all_records(), retrieval_store)
ai_runtime_settings = load_ai_runtime_settings()
from rich import print as rprint
rprint(f"[green]LLM provider: {ai_runtime_settings.llm_provider} | planner={ai_runtime_settings.planner_model} | worker={ai_runtime_settings.worker_model}[/green]")
llm_observer_status = "disabled"
llm_client = None
if ai_runtime_settings.enable_llm_orchestration:
    _s = ai_runtime_settings
    if _s.provider_pool_enabled:
        has_any_key = bool(
            _s.zai_api_key or _s.google_api_key or _s.groq_api_key or _s.openrouter_api_key
        )
        provider_has_credentials = has_any_key
    else:
        provider_has_credentials = (
            (_s.llm_provider == "gemini" and _s.google_api_key)
            or (_s.llm_provider == "groq" and _s.groq_api_key)
            or (_s.llm_provider == "zai" and _s.zai_api_key)
            or (_s.llm_provider == "openrouter" and _s.openrouter_api_key)
            or (_s.llm_provider == "openai_compatible" and _s.llm_base_url)
        )
    if provider_has_credentials:
        try:
            llm_client = _build_llm_client(ai_runtime_settings)
            llm_observer_status = "configured"
        except OrchestrationClientError:
            llm_client = None
            llm_observer_status = "unavailable"
    else:
        llm_observer_status = "unavailable"
app.state.retrieval_store = retrieval_store
app.state.retrieval_store_status = "ready"
app.state.source_document_registry = InMemorySourceDocumentRegistry()
app.state.review_record_store = review_record_store
app.state.recommendation_job_store = RecommendationJobStore()
app.state.ai_runtime_settings = ai_runtime_settings
app.state.gemini_client = llm_client
app.state.llm_client = llm_client
app.state.llm_observer_status = llm_observer_status
app.state.open_access_client = OpenAccessPaperClient(
    timeout_sec=ai_runtime_settings.open_access_timeout_sec
)
app.state.compound_context_client = PubChemCompoundContextClient(timeout_sec=8)
app.include_router(source_documents_router)
app.include_router(hplc_extraction_router)
app.include_router(review_records_router)
app.include_router(c12_orchestration_router)
app.include_router(recommendations_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    if not request.url.path.startswith("/recommendation"):
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    request_id = f"recommendation-{uuid4().hex[:16]}"
    increment_failure_counter("request_invalid")
    message = "; ".join(
        item.get("msg", "Invalid request") for item in exc.errors() if isinstance(item, dict)
    )[:1000] or "Invalid recommendation request."
    detail = RecommendationErrorDetail(
        request_id=request_id,
        runtime_status="request_invalid",
        failure_classification="request_invalid",
        failure_stage=None,
        message=message,
        retryable=False,
    )
    return JSONResponse(status_code=422, content={"detail": detail.model_dump()})


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "silico-method-development",
        "status": "ok",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "retrieval_store": app.state.retrieval_store_status,
        "llm_observer": app.state.llm_observer_status,
        "recommendation_runtime": {
            "open_access_timeout_sec": ai_runtime_settings.open_access_timeout_sec,
            "runtime_debug_metadata": ai_runtime_settings.enable_runtime_debug_metadata,
            "failure_counters": snapshot_failure_counters(),
        },
    }


@app.post("/retrieval/query", response_model=RetrievalQueryResponse)
@limiter.limit("5/hour")
def query_retrieval(
    payload: RetrievalQueryRequest, request: Request
) -> RetrievalQueryResponse:
    try:
        target_canonical_smiles = canonicalize_smiles(payload.target_smiles)
        impurity_canonical_smiles = [
            canonicalize_smiles(smiles) for smiles in payload.impurity_smiles
        ]
        matches = request.app.state.retrieval_store.search(
            payload.target_smiles,
            impurity_smiles=payload.impurity_smiles,
            limit=payload.limit,
            min_score=payload.min_score,
        )
    except InvalidSmilesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RetrievalQueryResponse(
        target_smiles=payload.target_smiles.strip(),
        target_canonical_smiles=target_canonical_smiles,
        impurity_smiles=[smiles.strip() for smiles in payload.impurity_smiles],
        ranking_mode=(
            "target_plus_impurities" if impurity_canonical_smiles else "target_only"
        ),
        results=[
            RetrievalQueryResult(
                score=match.score,
                matched_entity=RetrievalMatchedEntity(
                    local_identifier=match.matched_entity.local_identifier,
                    canonical_smiles=match.matched_entity.canonical_smiles,
                    score=match.matched_entity.score,
                ),
                record=match.record,
                match_rationale=match.match_rationale,
                review_summary=match.review_summary,
            )
            for match in matches
        ],
    )

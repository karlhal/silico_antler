from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import (
    allowed_cors_headers,
    allowed_cors_methods,
    allowed_origins,
    show_api_docs,
    trusted_hosts,
)
from .contact_delivery import send_contact_email
from .engine import PRESETS, get_presets, simulate
from .follow_up_chat import answer_follow_up_question
from .schemas import (
    AnalyticsEventRequest,
    AnalyticsEventResponse,
    ContactRequest,
    ContactResponse,
    FollowUpChatRequest,
    FollowUpChatResponse,
    PresetsResponse,
    PublicConfigResponse,
    SmilesNameResolveRequest,
    SmilesNameResolveResponse,
    SimulationRequest,
    SimulationResponse,
)
from .smiles_lookup import (
    LookupNotFoundError,
    LookupUnavailableError,
    SMILES_LOOKUP_FAILURE_DETAIL,
    SMILES_LOOKUP_NOT_FOUND_DETAIL,
    resolve_smiles_name_with_fallback,
)

logger = logging.getLogger("silico.api")
logging.basicConfig(level=logging.INFO)

PILOT_CALL_EMAIL_HREF = "mailto:hello@silico-labs.com?subject=Pilot%20Call%20Request"

ALLOWED_ORIGINS = allowed_origins()
ALLOWED_CORS_METHODS = allowed_cors_methods()
ALLOWED_CORS_HEADERS = allowed_cors_headers()
TRUSTED_HOSTS = trusted_hosts()
SHOW_API_DOCS = show_api_docs()
logger.info("Configured CORS origins: %s", ALLOWED_ORIGINS)

app = FastAPI(
    title="Silico Landing API",
    version="1.0.0",
    docs_url="/docs" if SHOW_API_DOCS else None,
    redoc_url="/redoc" if SHOW_API_DOCS else None,
    openapi_url="/openapi.json" if SHOW_API_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=ALLOWED_CORS_METHODS,
    allow_headers=ALLOWED_CORS_HEADERS,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)


@app.get("/")
def root() -> dict[str, str]:
    response = {
        "service": "silico-api",
        "status": "ok",
        "health": "/api/health",
        "ready": "/api/ready",
    }
    if SHOW_API_DOCS:
        response["docs"] = "/docs"
    return response


@app.get("/api")
def api_root() -> dict[str, str]:
    return {
        "service": "silico-api",
        "status": "ok",
        "health": "/api/health",
        "ready": "/api/ready",
        "presets": "/api/v1/demo/presets",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ready")
def ready() -> dict[str, object]:
    return {
        "status": "ready",
        "presets_loaded": len(PRESETS),
    }


@app.get("/api/v1/config", response_model=PublicConfigResponse)
def public_config() -> PublicConfigResponse:
    analytics_key = os.getenv("ANALYTICS_KEY")
    return PublicConfigResponse(booking_url=PILOT_CALL_EMAIL_HREF, analytics_key=analytics_key)


@app.get("/api/v1/demo/presets", response_model=PresetsResponse)
def demo_presets() -> PresetsResponse:
    return PresetsResponse(presets=get_presets())


@app.post("/api/v1/demo/simulate", response_model=SimulationResponse)
def demo_simulate(payload: SimulationRequest) -> SimulationResponse:
    if payload.preset_id not in PRESETS:
        raise HTTPException(status_code=404, detail="Unknown preset_id")

    result = simulate(
        preset_id=payload.preset_id,
        temperature_c=payload.temperature_c,
        meoh_pct=payload.meoh_pct,
    )
    return SimulationResponse(**result)


@app.post("/api/v1/contact", response_model=ContactResponse)
async def contact(payload: ContactRequest) -> ContactResponse:
    contact_payload = payload.model_dump()
    webhook_url = os.getenv("CONTACT_WEBHOOK_URL")
    contact_email = os.getenv("CONTACT_EMAIL", "").strip()

    logger.info("Contact form submission received for company=%s", payload.company)

    delivered = False

    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                await client.post(webhook_url, json=contact_payload)
            delivered = True
        except Exception as exc:
            logger.warning("Failed to forward contact submission to webhook: %s", exc)

    if contact_email:
        try:
            send_contact_email(payload, contact_email)
            delivered = True
        except ValueError as exc:
            logger.error("Contact email delivery misconfigured: %s", exc)
            raise HTTPException(status_code=503, detail=f"Contact email delivery misconfigured: {exc}") from exc
        except RuntimeError as exc:
            logger.error("Failed to deliver contact email: %s", exc)
            raise HTTPException(status_code=502, detail="Failed to deliver contact email.") from exc

    if not delivered:
        raise HTTPException(status_code=503, detail="Contact delivery is not configured.")

    return ContactResponse(status="ok")


@app.post("/api/v1/analytics/event", response_model=AnalyticsEventResponse)
def analytics_event(payload: AnalyticsEventRequest) -> AnalyticsEventResponse:
    logger.info("Analytics event received name=%s keys=%s", payload.name, sorted(payload.payload.keys()))
    return AnalyticsEventResponse(status="ok")


@app.post("/api/v1/chemistry/smiles/resolve", response_model=SmilesNameResolveResponse, operation_id="resolve_smiles")
async def resolve_smiles(payload: SmilesNameResolveRequest) -> SmilesNameResolveResponse:
    """
    Resolves a SMILES string to a common chemical name and retrieves candidate synonyms.
    """
    smiles = payload.smiles.strip()
    try:
        name, source, candidates = await resolve_smiles_name_with_fallback(smiles)
    except LookupUnavailableError:
        raise HTTPException(status_code=503, detail=SMILES_LOOKUP_FAILURE_DETAIL) from None
    except LookupNotFoundError:
        raise HTTPException(status_code=404, detail=SMILES_LOOKUP_NOT_FOUND_DETAIL) from None

    return SmilesNameResolveResponse(
        smiles=smiles,
        resolved_name=name,
        source=source,
        candidates=candidates,
    )


@app.post(
    "/api/v1/chemistry/smiles/resolve-name",
    response_model=SmilesNameResolveResponse,
    deprecated=True,
    summary="Legacy SMILES resolution endpoint",
)
async def resolve_smiles_name(payload: SmilesNameResolveRequest) -> SmilesNameResolveResponse:
    smiles = payload.smiles.strip()
    try:
        name, source, candidates = await resolve_smiles_name_with_fallback(smiles)
    except LookupUnavailableError:
        raise HTTPException(status_code=503, detail=SMILES_LOOKUP_FAILURE_DETAIL) from None
    except LookupNotFoundError:
        raise HTTPException(status_code=404, detail=SMILES_LOOKUP_NOT_FOUND_DETAIL) from None

    return SmilesNameResolveResponse(
        smiles=smiles,
        resolved_name=name,
        source=source,
        candidates=candidates,
    )


@app.post("/api/v1/agent/follow-up", response_model=FollowUpChatResponse)
async def agent_follow_up(payload: FollowUpChatRequest) -> FollowUpChatResponse:
    return await answer_follow_up_question(payload)

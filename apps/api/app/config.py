from __future__ import annotations

import os

DEFAULT_CORS_METHODS = ["GET", "POST", "OPTIONS"]
DEFAULT_CORS_HEADERS = ["Accept", "Content-Type", "Origin"]
DEFAULT_TRUSTED_HOSTS = ["localhost", "127.0.0.1", "testserver"]


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_production_environment() -> bool:
    for name in ("SILICO_ENV", "APP_ENV", "ENVIRONMENT"):
        raw = os.getenv(name)
        if raw and raw.strip().lower() in {"prod", "production"}:
            return True
    return False


def show_api_docs() -> bool:
    return env_bool("ENABLE_API_DOCS", not is_production_environment())


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def default_origins() -> list[str]:
    defaults = ["http://localhost:5173", "http://127.0.0.1:5173"]
    website_url = os.getenv("WEBSITE_URL", "").strip().rstrip("/")
    if website_url:
        defaults.append(website_url)
        if "://www." in website_url:
            defaults.append(website_url.replace("://www.", "://", 1))
        elif "://" in website_url:
            scheme, host = website_url.split("://", 1)
            defaults.append(f"{scheme}://www.{host}")
    return dedupe(defaults)


def allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return default_origins()

    origins = [entry.strip().rstrip("/") for entry in raw.split(",") if entry.strip()]
    return dedupe(origins) if origins else default_origins()


def allowed_cors_methods() -> list[str]:
    raw = os.getenv("ALLOWED_CORS_METHODS", "").strip()
    if not raw:
        return DEFAULT_CORS_METHODS
    methods = [entry.strip().upper() for entry in raw.split(",") if entry.strip()]
    return dedupe(methods) if methods else DEFAULT_CORS_METHODS


def allowed_cors_headers() -> list[str]:
    raw = os.getenv("ALLOWED_CORS_HEADERS", "").strip()
    if not raw:
        return DEFAULT_CORS_HEADERS
    headers = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return dedupe(headers) if headers else DEFAULT_CORS_HEADERS


def trusted_hosts() -> list[str]:
    raw = os.getenv("TRUSTED_HOSTS", "").strip()
    if not raw:
        return DEFAULT_TRUSTED_HOSTS
    hosts = [entry.strip() for entry in raw.split(",") if entry.strip()]
    return dedupe(hosts) if hosts else DEFAULT_TRUSTED_HOSTS

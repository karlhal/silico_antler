# Silico API Dev Setup

## Option 1: `uv` (recommended)

```bash
cd apps/api
uv sync --group dev
uv run pytest -q
uv run uvicorn app.main:app --reload --port 8000
```

## Option 2: `venv` + pip

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
pytest -q
uvicorn app.main:app --reload --port 8000
```

## Notes
- If `uv` is missing on another machine: `brew install uv` (macOS) or see Astral install docs.
- API health endpoint: `GET /api/health`
- API readiness endpoint: `GET /api/ready`
- Follow-up chat endpoint: `POST /api/v1/agent/follow-up`
- CORS origins are configured via `ALLOWED_ORIGINS` (comma-separated). When unset, localhost + `WEBSITE_URL` defaults are used.
- CORS methods/headers default to `GET,POST,OPTIONS` and `Accept,Content-Type,Origin`; override with `ALLOWED_CORS_METHODS` / `ALLOWED_CORS_HEADERS` only if a deployment truly needs more.
- Requests are accepted only for `TRUSTED_HOSTS` (defaults: `localhost,127.0.0.1`). Set this explicitly for on-prem hostnames before deployment.
- Interactive docs are enabled in development and can be disabled in customer-facing deployments with `ENABLE_API_DOCS=false` (the default in `.env.example` / Docker Compose).
- Optional report-grounded model answers use `OPENAI_API_KEY`; set `OPENAI_FOLLOW_UP_MODEL` to override the default chat model for `/api/v1/agent/follow-up`.
- Contact email delivery uses SMTP env vars (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_SSL`, `SMTP_USE_STARTTLS`) and sends to `CONTACT_EMAIL`.
- Render runtime is pinned with `runtime.txt` (`python-3.12.8`) to avoid Python 3.14 source-build issues for `pydantic-core`.

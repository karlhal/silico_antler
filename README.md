# silico

HPLC method recommendation engine. Retrieves and scores candidate methods from open-access literature and a curated local corpus.

## Repository structure
- `apps/agent`: React + Vite frontend — method recommendation UI.
- `apps/api`: FastAPI backend — SMILES name resolution and follow-up Q&A.
- `services/method-development`: FastAPI core engine — retrieval, extraction, scoring, review workflow.
- `services/surrogate-backend-model`: Gradient physics model and compound prediction data.
- `packages/brand`: Shared design tokens.
- `infra/proxy`: Nginx reverse proxy.

## Running locally

Three processes. Open three terminals.

**1. Core recommendation engine (required) — port 8001**
```bash
cd services/method-development
uv sync --group dev
USE_MILVUS=false uv run uvicorn app.main:app --reload --port 8001
```

**2. SMILES resolution + follow-up API (optional) — port 8000**
```bash
cd apps/api
uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000
```

**3. Frontend — port 4175**
```bash
cd apps/agent
npm install
npm run dev
```

Open `http://localhost:4175`. Vite proxies `/method-dev/*` → port 8001, `/api/*` → port 8000.

If you skip step 2, SMILES name resolution and follow-up chat are unavailable but the core recommendation flow works.

## Docker (all-in-one)
```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080` (or set `APP_PORT`).

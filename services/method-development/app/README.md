# Method Development Application Package

## Purpose
This folder contains the FastAPI backend code for the HPLC method-development service.

## Intent
- Keep `main.py` focused on service wiring and health endpoints.
- Keep retrieval, ingestion, extraction, and validation code in focused modules.
- Preserve a clean service boundary from `apps/api` and `apps/sidecar`.
- Keep source-document registration and parsing in dedicated modules such as `source_document_ingestion.py` and `source_documents_router.py`.
- Keep HPLC text extraction logic in dedicated modules such as `hplc_text_extraction.py` and `hplc_extraction_router.py`.

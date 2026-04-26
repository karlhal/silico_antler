# Repo Structure

The repo is organized as a product monorepo instead of separate repos per platform.

## Apps
- `apps/agent`: Retrieval-and-scoring web app for evidence-backed HPLC method recommendation.
- `apps/marketing`: Public website and marketing funnels.
- `apps/desktop`: Shared Tauri desktop shell for macOS and Windows.
- `apps/sidecar`: Local workstation-only inference service for the desktop app.
- `apps/api`: Hosted backend API.

## Services
- `services/method-development`: Hosted HPLC method-development service for retrieval, literature ingestion, structured extraction, and validation.

## Packages
- `packages/brand`: Design tokens, logos, and shared brand primitives.

## Legacy Runtime
- `apps/sidecar/legacy_runtime`: Legacy inference runtime sources and feature metadata consumed by the sidecar bridge and desktop bundling.

## Release Model
- `apps/agent` currently validates as a standalone web app through its build gate; dedicated release automation is not yet defined in-repo.
- `apps/marketing` deploys continuously.
- `apps/api` versions independently as a backend service.
- `services/method-development` versions independently as a scientific backend service.
- `apps/desktop` releases from one codebase with platform-specific macOS and Windows bundles.
- `apps/sidecar` is versioned with the desktop app when it ships as part of the local product experience.

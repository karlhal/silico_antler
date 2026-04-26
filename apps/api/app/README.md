# API Application Package

## Purpose
This folder contains the FastAPI backend application code for the public API service.

## Intent
- Keep `main.py` focused on app wiring and route composition.
- Keep domain concerns modular (`config`, `schemas`, `smiles_lookup`, `contact_delivery`, `engine`).
- Preserve stable HTTP contracts while allowing internal refactors.

## Notes
- Route behavior should stay backward compatible unless explicitly versioned.
- Shared settings are centralized in `config.py`.

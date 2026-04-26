---
status: completed
owner: codex
created: 2026-04-20
last_verified: 2026-04-20
applies_to: services/method-development apps/agent smart extraction
source_of_truth: docs/agents/execution-plans.md
---

# Smart Extraction Implementation Report

## Summary
We have significantly upgraded the HPLC literature extraction pipeline from a brittle, purely rules-based system to a robust, **hybrid Smart Extraction engine**. This system effectively handles the messy reality of scientific PDFs, including interjected headers, page breaks, and complex Unicode characters.

## Technical Achievements

### 1. Hybrid LLM Fallback
- **Mechanism**: If the rules-based regex parser fails to recover mandatory fields (Mobile Phase A or Flow Rate), the engine now triggers an LLM fallback.
- **Section Targeting**: The system identifies the most likely "Methods" or "Chromatographic conditions" sections to provide high-quality context to the model.
- **LLM Recovery**: Added `extract_hplc_parameters` to the `GeminiOrchestrationClient`. It reconstructs structured HPLC data from noisy PDF text, ignoring interjected headers and artifacts.

### 2. Evidence Vetting & Refinement
- **Concise Quotes**: Implemented `vet_evidence_snippets`. Instead of displaying multi-paragraph raw text blocks that overflow the UI, Gemini now "vets" the evidence, returning only the 1-3 most telling sentences.
- **Length-Preserving Normalization**: Rebuilt the text cleaning layer to be length-preserving. This ensures that indices used for context extraction remain accurate across normalized strings (e.g., converting `·` to `.` without shifting text).

### 3. Pattern Hardening
- **Artifact Resilience**: Updated core regex patterns (`FLOW_RATE`, `TEMPERATURE`, `ELUENT`) to skip over up to 50 characters of non-numeric "noise," allowing them to match even if a PDF header breaks a sentence.
- **Isocratic Support**: Added specific logic for premixed mobile phases (e.g., `60:40 ACN:H2O`).

### 4. UI/UX Polish
- **Visual Rhythm**: Applied targeted rounding (`rounded-md` and `rounded-lg`) to soften the "boxy" feel of the dashboard while maintaining technical precision.
- **Tooltip Refactor**: Rebuilt the `<Tip>` component to be centered, responsive, and styled with a professional popover look.
- **Solvent Detail**: Enhanced candidate cards to display full solvent names, additives, and pH estimates.

### 5. New Default Demo
- The **"Quick Demo"** now defaults to the **Metformin and Sitagliptin** case. This case perfectly demonstrates the system's ability to:
  - Recover complex buffer descriptions via LLM assistance.
  - Scale older literature methods to modern UPLC hardware.
  - Handle dense, artifact-heavy pharmaceutical literature.

## Verification Results
- **Regression**: All 19 extraction tests in `test_hplc_extraction.py` passed.
- **Robustness**: Verified successful recovery on the "Strawberry Antioxidants" paper, which previously failed due to interjected "Sample Treatment" headers.
- **Type Safety**: Backend schemas updated to handle longer text blocks and optional mobile phase components without validation errors.

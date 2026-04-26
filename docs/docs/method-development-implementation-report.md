# HPLC Method Development Service: Implementation Report

## 1. Executive Summary
The Silico Method Development service has been transformed from a static retrieval tool into an active **Experiment Recommender**. The system now accounts for the user's specific laboratory hardware, recalculates method physics automatically, and scales to thousands of documents using a high-performance vector backend.

## 2. Key Architectural Upgrades

### 2.1 Multi-Factor Recommendation Scoring
The scoring logic in `recommendation_engine.py` was refactored to move beyond simple text relevance. It now calculates a weighted score based on four dimensions:
*   **System Match (25%)**: Geometric and chemical compatibility of columns (Chemistry, Dimensions, Particle Size).
*   **Analyte Match (25%)**: Chemical similarity using Morgan Fingerprints and SMILES overlap.
*   **Matrix/Sample Fit (15%)**: Alignment between the sample source (e.g., Plasma vs. Urine) and literature.
*   **Practical Fit (15%)**: Lab-specific constraints including available detectors and solvents.

### 2.2 Physics-Based Method Scaling
A new physics engine was implemented to ensure recommended methods are actually runnable on the user's hardware.
*   **Flow Rate Adjustment**: Scales with the square of the internal diameter ($d_c^2$) to maintain constant linear velocity.
*   **Gradient Compression**: Re-calculates gradient time-points based on the ratio of column lengths ($L_2/L_1$).
*   **Injection Volume Scaling**: Adjusts based on total column volume ($V_c$) to prevent peak broadening or detector saturation.
*   **Intelligent Warnings**: Automatically detects particle size differences and warns about potential backpressure increases.

### 2.3 Scaled Data Backend (Milvus)
To support industrial-scale literature databases, we implemented a `MilvusRetrievalStore` using **Milvus Lite**.
*   **Similarity Metric**: Uses Jaccard/Tanimoto similarity on binary molecular fingerprints.
*   **Performance Result**: Search time was reduced from ~1,000ms to **~3ms** at a corpus size of 5,000 records (a **300x speedup**).

## 3. User Experience Enhancements
The CLI (`run_method_recommendation_cli.py`) was rebuilt to follow a professional, step-by-step workflow:
1.  **Hardware Profile**: Select manufacturers, chemistries, and detectors from keyboard-driven menus (powered by `questionary`).
2.  **Lab Inventory**: A multi-select checklist for available solvents ensures the engine only recommends runnable methods.
3.  **Separation Goals**: Detailed prompting for analyte targets and matrix sources.

## 4. Validation & Results

### 4.1 "Golden Dataset" Performance
The extraction pipeline was validated against a hand-curated dataset of 20+ peer-reviewed methods.
*   **Overall Accuracy**: 95.7% (Matched parameters vs. Ground Truth).
*   **Extraction Robustness**: Successfully handled both structured tables and unstructured experimental text from PDF and HTML sources.

### 4.2 Scaling Test Result
Moving a method from a **Standard Column** ($250 \times 4.6\text{ mm}$) to a **Narrow-Bore Column** ($50 \times 2.1\text{ mm}$):
*   **Literature Flow**: $0.60 \text{ mL/min}$ $\to$ **Recommended Flow**: $0.13 \text{ mL/min}$.
*   **Literature Run Time**: $50 \text{ min}$ $\to$ **Recommended Run Time**: $10 \text{ min}$.
*   **Result**: The physics engine successfully compressed the method by $5\times$ while maintaining the chemical separation profile.

### 4.3 Open-Access Internet Discovery
The engine's ability to retrieve and process live scientific literature was verified through a search for "Paclitaxel in plasma."
*   **Discovery**: Successfully integrated with the **OpenAlex API** to identify full-text open-access candidates.
*   **Result**: The system correctly identified and prioritized a 2010 method from the *Journal of Bioequivalence & Bioavailability*, extracting specific evidence such as the **4.60 min retention time** for the target analyte.
*   **Reliability**: Swapped retrieval logic to **prioritize HTML versions** of papers over PDFs, resulting in faster downloads and higher parsing accuracy.

## 5. Technical Hardening & Robustness
Several improvements were made to ensure the service remains stable when handling diverse external sources:
*   **Increased Capacity**: Expanded `SourceDocumentSection` character limits to **1,000,000 characters** to accommodate long-form academic papers.
*   **Graceful Degradation**: Added error handling to the recommendation loop to skip individual papers that fail to download or parse without crashing the entire search session.
*   **Pydantic Optimization**: Rebuilt core schemas using `model_rebuild()` to resolve complex circular dependencies in the recommendation models.

## 6. Forward Roadmap
*   **Phase 1 (Complete)**: Recommendation MVP, Physics Scaling, Milvus Integration, and Internet Discovery.
*   **Phase 2 (Deferred)**: GNN-based surrogate models for *predicting* novel methods (Deferred to prioritize the reliability of existing literature extraction).

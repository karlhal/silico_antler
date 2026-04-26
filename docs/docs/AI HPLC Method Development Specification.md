# Technical Specification and Engineering Roadmap: Agentic AI Platform for Analytical HPLC Method Development

The development of an autonomous, agent-driven artificial intelligence system designed to eliminate physical trial-and-error in analytical High-Performance Liquid Chromatography (HPLC) method development represents a necessary paradigm shift in pharmaceutical cheminformatics. When novel chemical entities are synthesized, they are invariably present in highly complex mixtures containing uncharacterized impurities, unreacted starting materials, structural isomers, and degradation products. Establishing baseline separation for these mixtures traditionally requires extensive physical experimentation to iteratively optimize the stationary phase (column chemistry), mobile phase composition, gradient profile, and operational temperature. This heuristic process acts as a severe bottleneck in drug discovery and quality control pipelines.

The proposed Software-as-a-Service (SaaS) platform resolves this bottleneck through a sophisticated two-tiered architecture. First, a multimodal agentic pipeline programmatically extracts historically successful chromatographic parameters from unstructured scientific literature, leveraging structural similarity to inform starting conditions. Second, a proprietary machine learning surrogate model simulates the chromatographic retention behavior of the target mixture under varying virtual conditions, ultimately yielding the optimal baseline separation parameters.

This document serves as the exhaustive technical specification and engineering roadmap for the Minimum Viable Product (MVP). The architectural scope is strictly constrained to analytical reversed-phase liquid chromatography (RP-LC) and hydrophilic interaction liquid chromatography (HILIC), with the singular objective of achieving baseline resolution (peak separation) rather than preparative physical yield. Every component of the system, from the vector database index types to the physics-informed neural network configurations, is detailed to provide software engineers and cheminformatics architects with a comprehensive blueprint for implementation.

## Phase 1: The Agentic Literature Extraction Pipeline

The primary data acquisition bottleneck in computational chemistry is the inherently unstructured, multimodal nature of published scientific literature. Chromatographic methodologies are notoriously difficult to parse because the critical parameters are dispersed across disparate formats. Retention times are often embedded in textual paragraphs within the Supplementary Information, gradient profiles are detailed in standalone numeric tables, and the molecular targets themselves are depicted purely as 2D vector graphic images without explicit textual identifiers. Converting this unstructured heterogeneity into a machine-readable, deterministic schema requires an orchestrated, multi-agent Large Language Model (LLM) pipeline capable of spatial visual reasoning, semantic text parsing, and rigorous physical validation.

### State of the Art in Multimodal Chemical Extraction

Historically, chemical parameter extraction relied heavily on rule-based Natural Language Processing (NLP) toolkits or bidirectional encoder representations from transformers (BERT) that were fine-tuned specifically for scientific domains, such as SciBERT or BioBERT.<sup>1</sup> While these legacy architectures were effective for isolated span-extraction tasks, they critically fail when contextual information spans multiple pages or requires integrating complex table headers with inline experimental text. Furthermore, traditional generative pipelines struggle significantly with high rates of hallucination when predicting continuous numerical variables, rendering them fragile and mathematically dangerous for downstream machine learning applications.<sup>1</sup>

Contemporary extraction frameworks leverage Retrieval-Augmented Generation (RAG) and sophisticated prompt engineering across highly expanded context windows. A foundational open-source example in this domain is the "Librarian of Alexandria" (LoA), an extensible pipeline that utilizes decoupled LLMs to separately verify document relevance and extract chemical property data.<sup>1</sup> LoA achieves approximately 80% accuracy for large-scale dataset creation by bypassing the overhead of traditional RAG indexing and instead relying on the massive token limits of modern models combined with strict prompt engineering.<sup>1</sup> However, LoA is primarily optimized for linear text and struggles with the complex spatial reasoning required to decode chemical reaction graphics and multi-variable gradient tables.

To achieve the MVP objectives for HPLC parameter extraction, the architecture must adopt a multimodal, multi-agent paradigm conceptually aligned with the ChemEAGLE (Chemical information Extraction by Agentic Language models) framework.<sup>3</sup> ChemEAGLE utilizes a central frontier multimodal large language model (MLLM), such as GPT-4o, configured with a low temperature setting (e.g., 0.1) to act as a definitive reasoning engine.<sup>3</sup> This engine decomposes the overarching extraction process into a Directed Acyclic Graph (DAG) of specialized sub-tasks.<sup>3</sup> The fundamental superiority of this approach lies in its hierarchical task deconvolution. An orchestrating Planner Agent dynamically delegates specific extraction targets to specialized worker agents, while an Action Observer Agent monitors real-time execution to catch tool failures or parsing mismatches before they cascade through the pipeline.<sup>3</sup> ChemEAGLE has demonstrated an F1 score of 80.8% on complex chemical reaction graphics, vastly outperforming previous state-of-the-art models like OpenChemIE, which scored 35.6% on identical benchmarks.<sup>3</sup>

Table 1 delineates the required agentic topology for the MVP literature pipeline, adapting best-in-class multi-agent frameworks specifically for analytical HPLC parameter extraction.

| Agent Designation | Functional Responsibility | Integrated Tooling & Mechanism |
| --- | --- | --- |
| Planner Agent | Ingests raw PDF/HTML, identifies the location of Experimental Sections and Supplementary Information, and generates a dynamic extraction DAG. | Base MLLM (GPT-4o/Claude 3.5 Sonnet) operating at zero temperature for deterministic planning.<sup>3</sup> |
| Action Observer Agent | Monitors execution workflows in real-time. Halts the DAG if an intermediate output violates expected schemas or if a subordinate tool fails. | Semantic evaluation loops and Pydantic validation scripts.<sup>3</sup> |
| Molecular Recognition Agent | Scans document graphics for 2D molecular structures, converts visual depictions to molecular graph information, and resolves OCR ambiguities. | Image2Graph, Graph2SMILES, MolDetector, MLLM-based correction.<sup>3</sup> |
| R-Group Substitution Agent | Handles explicit product variant structures depicted in tables. Isolates R-group fragments and substitutes them into reactant templates. | SMILESReconstructor, TableParser.<sup>3</sup> |
| Condition Interpretation Agent | Semantically parses continuous prose to isolate column dimensions, particle size, flow rates, and observed retention times (`t_R`). | TesseractOCR with adaptive noise reduction, RxnConInterpreter.<sup>3</sup> |
| Gradient Table Parsing Agent | Detects tabular boundaries, segments complex cells, and reconstructs the piecewise linear gradient steps (Time vs. % Mobile Phase B). | Specialized deep learning table parsers, deterministic regex fallbacks.<sup>3</sup> |

### Entity Resolution: Mapping SMILES to Chromatographic Profiles

The most critical failure mode in chemical NLP is "entity disassociation," where a correctly extracted numerical retention time is erroneously attributed to the wrong molecular structure. In a standard synthetic chemistry publication, an experimental section might describe the general synthesis of "Compound 4a," followed by a densely packed paragraph detailing its purification via RP-LC alongside several intermediates.

To reliably map the Simplified Molecular-Input Line-Entry System (SMILES) strings to specific retention times (`t_R`) and dynamic gradient profiles, the extraction pipeline must employ deterministic reference anchoring. The text extraction agents must first utilize chemical named entity recognition tools, such as MolNER, to tag all local alphanumeric identifiers (e.g., "4a", "intermediate 2", "API") within the document.<sup>3</sup> When the Condition Interpretation Agent locates a cluster of HPLC parameters, it must execute a backward-looking proximity search within the document's syntactic tree to anchor these parameters to the nearest local identifier.<sup>3</sup> If multiple derivative products are generated and explicitly depicted in a structure-based R-group table, the Structure-based R-group Substitution Agent must programmatically generate the discrete SMILES variants for each row by isolating the visual R-group fragments and executing substructure substitution into the base scaffold.<sup>3</sup>

Gradient profiles present a unique structural and semantic challenge. A gradient is mathematically defined as a time-series array describing the dynamic, changing ratio of Mobile Phase A (typically an aqueous buffer) to Mobile Phase B (typically an organic solvent like acetonitrile or methanol). Literature frequently expresses this in messy, non-standardized shorthand, such as "5 to 95% B over 10 min, hold 2 min, return to initial over 1 min." The Gradient Table Parsing Agent must parse this natural language into a mathematically rigid, piecewise linear array required for machine learning: `[[0.0, 5.0], [10.0, 95.0], [12.0, 95.0], [13.0, 5.0]]`.<sup>6</sup> If the text explicitly omits the initial condition (time zero), the agent must infer the standard injection state based on the column re-equilibration parameters or raise a strict exception to the Planner Agent, triggering a semantic re-evaluation of the surrounding textual context.

### Mitigation of Hallucinations via the Validation Agent

Large Language Models are fundamentally probabilistic inference engines and are thus highly prone to hallucinating numerical values. They are particularly susceptible to interpolating physically impossible instrumental parameters when the context window is highly dense, contains overlapping tables, or spans poorly formatted PDF conversions.<sup>1</sup> To bridge the critical gap between stochastic text generation and deterministic physical reality, the system architecture must implement a localized "Validation Agent" that functions as the pipeline's immutable chemical conscience.<sup>7</sup>

The Validation Agent does not rely on LLM reasoning to determine truth; instead, it executes a suite of hard-coded Python routines to enforce symbolic knowledge, chemical feasibility constraints, and thermodynamic physical bounds.<sup>7</sup> The primary physical constraint in any liquid chromatography system is the column backpressure, which is governed by the complex fluid dynamics of the liquid mobile phase passing through the tightly packed, porous stationary phase bed.<sup>10</sup>

If an extraction agent hallucinates a flow rate of 5.0 mL/min on a 2.1 mm internal diameter (ID) analytical column packed with ultra-small 1.7 `\mu`m particles, the Validation Agent must immediately reject the proposed schema. The system validates flow metrics by calculating the theoretical pressure drop (`\Delta P`) using the Kozeny-Carman equation, which accurately models the permeability and flow resistance of packed granular beds<sup>10</sup>:

```math
\Delta P = \frac{250 \cdot L \cdot \eta \cdot F}{d_p^2 \cdot d_c^2}
```

Where:

- `\Delta P` is the pressure drop across the column (typically calculated in psi or bar, depending on the specific constant coefficient applied).<sup>14</sup>
- `L` is the column length (cm).
- `\eta` is the mobile phase viscosity (cP). Viscosity varies dynamically throughout a gradient run, but the Validation Agent can estimate the maximum pressure using the highest-viscosity mobile phase composition (e.g., a 50:50 mix of Methanol and Water exhibits significantly higher viscosity than pure solvents).<sup>11</sup>
- `F` is the volumetric flow rate (mL/min).<sup>14</sup>
- `d_p` is the particle diameter (`\mu`m).<sup>14</sup>
- `d_c` is the column internal diameter (cm).<sup>14</sup>

The Kozeny-Carman equation dictates that backpressure increases inversely proportional to the square of the particle diameter.<sup>10</sup> The Validation Agent computes this theoretical `\Delta P` and automatically checks it against the strict operational limits of standard HPLC and Ultra-High-Performance Liquid Chromatography (UHPLC) systems. Standard legacy HPLC systems typically operate safely strictly under 400 bar, while modern UHPLC systems are engineered to tolerate extreme pressures up to 1,000-1,500 bar (15,000-22,000 psi).<sup>10</sup> If the computed pressure drastically exceeds the mechanical tolerance of commercial pumping systems, the extracted parameters are definitively flagged as physically impossible and discarded.<sup>10</sup>

Furthermore, the Validation Agent meticulously evaluates stationary phase chemistry against mobile phase pH stability limits. Standard silica-based columns undergo rapid dissolution at elevated pH levels due to the aggressive hydrolysis of the underlying silica support particles, resulting in catastrophic column voiding and loss of theoretical plates.<sup>20</sup> If the pipeline extracts a methodology describing an aqueous mobile phase utilizing a basic buffer (e.g., pH &gt; 8.0) paired with a standard unbonded or minimally end-capped silica stationary phase, the Validation Agent flags a severe chemical compatibility violation.<sup>21</sup> Such conditions would result in immediate column degradation. Certain stationary phases, such as ethylene-bridged hybrids or highly cross-linked C18 phases, offer extended stability at high pH and would pass validation.<sup>21</sup> Establishing these deterministic, physics-based guardrails ensures the downstream Surrogate ML model is never poisoned by physically unrealizable or chemically destructive training data.

## Phase 2: The Surrogate Model Architecture

Once the agentic pipeline successfully populates a highly structured vector database of empirical chromatography data, the Surrogate Model must synthesize this historical information to predict optimal baseline separation conditions for a completely novel chemical mixture. The core machine learning objective is the accurate prediction of Retention Time (`t_R`) for each analyte as a highly nonlinear function of the molecular graph, the stationary phase chemistry, and the dynamic gradient profile.<sup>6</sup>

### Feature Engineering and Molecular Descriptors

To accurately model the dispersive, polar, dipole-dipole, and ionic interactions between the analyte and the stationary phase, the algorithm requires mathematically rigorous representations of molecular structure.<sup>26</sup> The traditional computational paradigm relies on one-dimensional vector representations generated via cheminformatics toolkits, most notably RDKit.<sup>6</sup> These representations include calculated physiochemical descriptors and topological binary fingerprints.

For reversed-phase liquid chromatography (RP-LC), the dominant retention mechanism is driven by hydrophobic (dispersive van der Waals) interactions between the non-polar regions of the analyte and the hydrophobic alkyl chains (e.g., C18 or C8) of the stationary phase.<sup>26</sup> Consequently, the most critical molecular descriptor for predicting retention is the calculated partition coefficient (LogP), which directly quantifies the molecule's overall lipophilicity.<sup>6</sup> Secondary, yet vital, descriptors include the Topological Polar Surface Area (TPSA), which strongly correlates with the analyte's propensity to bypass the hydrophobic stationary phase and partition favorably into the polar aqueous mobile phase, and the total number of hydrogen bond donors and acceptors, which dictate secondary retention interactions with any uncapped, acidic silanol groups remaining on the silica support matrix.<sup>26</sup>

A modern alternative to explicit, human-engineered descriptor calculation is the utilization of Graph Neural Networks (GNNs). In a GNN paradigm, the input molecular SMILES string is programmatically converted into a structured mathematical graph where individual atoms function as nodes (`v`) and chemical bonds function as edges (`e`).<sup>27</sup> The GNN leverages sophisticated message-passing algorithms to iteratively aggregate local structural information from neighboring atoms, learning an implicit, high-dimensional embedding space that captures complex, long-range topological relationships without requiring any human intervention or predefined physiochemical rules.<sup>6</sup>

### Architectural Trade-offs for the MVP: GNNs vs. Ensemble Methods

The critical selection between a pure Deep Learning architecture (e.g., GNN) and a traditional Machine Learning ensemble (e.g., Extreme Gradient Boosting - XGBoost, or Random Forest) represents a pivotal inflection point in the MVP engineering roadmap.

Graph Neural Networks, particularly variants like the Directed Message Passing Neural Network (D-MPNN, exemplified by the widely used ChemProp framework), have established state-of-the-art predictive benchmarks in generalized molecular property prediction due to their automated, structure-aware feature extraction capabilities.<sup>6</sup> However, deep GNNs suffer from severe data hunger; they require immense volumes of high-quality, evenly distributed training data to prevent catastrophic overfitting.<sup>31</sup> Furthermore, deep learning architectures natively lack the inherent transparency of tree-based methods, rendering them exceedingly difficult to debug during an MVP phase where data scarcity and data quality are the primary constraints.

Recent rigorous benchmarking studies conducted in 2024 indicate that while GNNs are powerful topological aggregators, their predictive superiority over classical gradient boosting models like XGBoost is largely negligible when the available training dataset is small, or critically, when evaluating out-of-distribution (OOD) chemical scaffolds.<sup>27</sup> In standard drug discovery workflows, target molecules often represent novel intellectual property and therefore occupy OOD chemical space relative to historical literature. In many such instances, a well-tuned XGBoost model utilizing pre-computed RDKit descriptors and Extended-Connectivity Fingerprints (ECFP4) matches or marginally outperforms standalone GNNs.<sup>27</sup> Representational similarity analysis using Centered Kernel Alignment (CKA) demonstrates that GNN embeddings and fingerprint embeddings occupy highly independent latent spaces, suggesting that neither representation wholly subsumes the predictive power of the other.<sup>27</sup>

For the MVP architecture, the optimal approach is a hybrid or "fusion" framework, conceptually identical to the highly successful XGraphBoost methodology.<sup>28</sup> In this advanced paradigm, a pre-trained GNN (or a robust fingerprinting algorithm if MVP computational budgets are strictly constrained) acts purely as an automated feature extractor, generating continuous numerical embedding vectors for the molecule.<sup>27</sup> These embeddings are subsequently concatenated with explicit physical descriptors (LogP, TPSA) calculated by RDKit.<sup>27</sup>

Crucially, this concatenated feature array is then fed into an XGBoost regressor, entirely replacing the traditional feed-forward neural network (FFN) readout layer of the standard GNN.<sup>28</sup> This hybrid approach strategically leverages the superior, non-linear feature interactions and split-finding capabilities mapped by gradient boosting decision trees, while simultaneously capitalizing on the inductive structural biases of the graph representation.<sup>31</sup> The result is a highly robust architecture capable of achieving state-of-the-art performance even in the data-scarce, cold-start environment inherent to an MVP launch.<sup>31</sup>

Table 2 highlights the technical trade-offs driving the architectural decision to adopt an XGBoost-driven hybrid ensemble over a pure deep learning approach for the MVP.

| Architectural Metric | Pure Graph Neural Network (e.g., ChemProp) | Pure XGBoost / Random Forest (RDKit Descriptors) | Hybrid Ensemble (XGraphBoost Methodology) |
| --- | --- | --- | --- |
| Data Efficiency | Poor; requires tens of thousands of samples to learn stable embeddings without overfitting. | High; tree-based models are highly resilient to small, tabular datasets. | High; leverages pre-trained structural embeddings to effectively offset task-specific data scarcity. |
| Feature Engineering Requirements | Zero; entirely automated via end-to-end message passing across the molecular graph. | High; requires explicit domain expertise to select relevant topological and physical descriptors. | Low; automated deep embeddings perfectly complement a small set of basic explicit descriptors. |
| Out-of-Distribution (OOD) Generalization | Moderate to Low; prone to catastrophic failure on novel scaffolds not seen in training. | Moderate; fallback reliance on basic physical properties aids generalization. | High; tree-based regression limits extreme extrapolation errors on deep embeddings. |
| Interpretability | Low; black-box node activations and complex message passing weights. | High; clear, calculable feature importance scoring (e.g., SHAP values) for every tree split. | Moderate; terminal tree splits can still be tracked back to explicit features for debugging. |
| MVP Suitability | Low; excessive computational overhead, difficult to debug, and high cold-start risks. | High; allows for rapid iteration, transparent debugging, and fast training times. | Optimal; provides the perfect balance between advanced topological representation and robust regression. |

### Mathematical Representation of the Gradient Profile

Predicting chromatographic retention under isocratic conditions (where the mobile phase composition remains entirely constant) is mathematically straightforward. However, modern analytical HPLC relies almost exclusively on gradient elution, where the eluent composition (specifically the ratio of the weak solvent, Mobile Phase A, to the strong solvent, Mobile Phase B) changes dynamically over time to resolve compounds with vastly different polarities in a single run.<sup>41</sup> The changing gradient profile cannot be fed into a standard ML model as raw text; it must be rigorously and mathematically parameterized.

In naive deep learning approaches, the gradient is often forced into a fixed-length vector or processed sequentially via a 1D-Transformer.<sup>6</sup> For example, a method might dictate an initial 3% B composition ramping to 37% B over 44 minutes, then jumping to 80% B.<sup>43</sup> Encoding this directly requires flattening the discrete time steps (`t`) and the corresponding slopes or solvent compositions (`\phi`) into a tensor array.<sup>6</sup> However, this raw concatenation forces the algorithm to learn the underlying physics of fluid dynamics and column partitioning implicitly. This requires vast amounts of training data and critically fails to generalize to novel gradient shapes not present in the training set.<sup>6</sup>

Furthermore, different chromatographic modes utilize gradients that move in opposite directions. In standard RP-LC, the gradient starts highly aqueous (low %B) and becomes highly organic (high %B). Conversely, in Hydrophilic Interaction Liquid Chromatography (HILIC), the gradient is effectively "upside-down," starting highly organic (high %B) and increasing the aqueous fraction to elute polar compounds.<sup>44</sup> To maximize model similarity and allow transfer learning between modes, the feature pipeline must invert HILIC labels such that the mathematical encoding matches the shape of RP-LC profiles, treating the initial state as the baseline minimum regardless of true solvent identity.<sup>44</sup>

To bypass the severe limitations of direct gradient encoding for the MVP, the Surrogate Model must adopt a Physics-Informed Neural Network (PINN) architecture, inspired directly by highly successful frameworks such as GRIP (physics-informed neural network for gradient retention time prediction).<sup>6</sup> Instead of attempting to predict the terminal retention time (`R_t`) directly from the raw gradient array, the machine learning module (the XGraphBoost hybrid) is tasked with predicting two empirical, system-independent thermodynamic coefficients derived from the foundational Linear Solvent Strength (LSS) model: `k_0` (the extrapolated retention factor of the analyte in pure weak solvent) and `S` (the solvent strength parameter, dictating the rate of change in retention as solvent strength increases).<sup>6</sup>

The fundamental relationship of the LSS model is expressed as:

```math
\log k = \log k_0 - S \cdot \phi
```

Where `k` is the retention factor at a specific volume fraction of the strong solvent `\phi`.<sup>6</sup>

Once the ML layer outputs `k_0` and `S` strictly for the specific analyte-column pair based on molecular descriptors, the final retention time is calculated analytically using a deterministic, hard-coded "Physics Layer" that integrates the fundamental equation of gradient elution.<sup>6</sup> This physical calculation requires knowing the column holdup time (`t_0`)—the time required for an unretained molecule to pass through the specific column void volume—and the instantaneous volume fraction of the organic modifier, `\phi(t)`, which is easily derived from the piecewise gradient array. This mathematical decoupling is transformative; it allows the MVP to predict highly accurate retention times across infinite variations of complex gradient profiles without requiring the ML model to explicitly "learn" or overfit to the physical shape of the gradient.<sup>6</sup>

## Phase 3: MVP Engineering Specifications and Schema

Translating the theoretical multi-agent data pipeline and the physics-informed machine learning architecture into a production-ready SaaS MVP necessitates a tightly coupled, horizontally scalable tech stack. The system must instantaneously process an incoming user query (a target SMILES and suspected impurities), execute an ultra-fast structural similarity search against the extracted literature database, dynamically simulate theoretical chromatograms across thousands of varying conditions using the surrogate model, and surface the optimal, baseline-separated parameters to the UI.

### Core Technology Stack

1. Language and Compute: Python 3.11+ serves as the foundational, non-negotiable language, leveraging its absolute dominance in both the cheminformatics and machine learning ecosystems.
2. Cheminformatics Backend: RDKit is mandated for all explicit molecular descriptor generation (e.g., LogP, TPSA), Morgan/ECFP4 binary fingerprint calculation, 2D coordinate rendering for the UI, and all structural validation routines.<sup>6</sup>
3. Orchestration Framework: LangGraph will be utilized for agentic workflow orchestration rather than standard sequential LangChain chains. LangGraph provides native architectural support for cyclical directed graphs and state persistence. This is absolutely critical for the MVP, as the extraction pipeline must support cyclical looping behaviors—for instance, if the Validation Agent rejects an extracted flow rate as physically impossible, the graph state must seamlessly loop back to the Condition Interpretation Agent to force a re-evaluation of the raw text context.<sup>46</sup>
4. Vector Database Infrastructure: Milvus is selected as the primary vector search engine. While competitors like Qdrant offer robust Rust-based performance<sup>47</sup>, Milvus uniquely and natively supports the TANIMOTO distance metric, which is specifically engineered for binary vector comparison.<sup>49</sup> Molecular fingerprints (such as ECFP4) are binary bit vectors where the presence or absence of a specific molecular substructure is represented strictly as a 1 or 0.<sup>53</sup> Searching massive databases for structurally similar molecular scaffolds using continuous, floating-point Euclidean distance (L2) is computationally wasteful and chemically inaccurate. Milvus allows the system to execute rapid Approximate Nearest Neighbor (ANN) queries calculating the exact Tanimoto coefficient (intersection over union of bit arrays) between the user's input molecule and the historical literature database.<sup>49</sup> The database will utilize the `BIN_IVF_FLAT` index type (Binary Inverted File with Flat comparison), configuring the `nlist` clustering parameter (e.g., `nlist: 1024`) to partition the vector space into voronoi cells, ensuring sub-millisecond similarity search times across millions of extracted molecules.<sup>50</sup>
5. Machine Learning Inference: The XGBoost library will serve as the core regression layer, optionally supplemented by PyTorch Geometric if pre-trained GNN molecular embeddings are integrated into the feature space for the XGraphBoost architecture.<sup>34</sup>

### Standardized JSON Schema Specification

The Data Structure Agent within the literature extraction pipeline must serialize the multimodal data into a highly rigid, deeply nested format. The schema design should draw heavy inspiration from the Allotrope Simple Model (ASM), the pharmaceutical industry's leading JSON-based standard for standardizing diverse instrument data, specifically aligning with the LC-UV method data model.<sup>56</sup> Aligning the internal proprietary schema with ASM not only ensures robust internal data integrity but provides a native, seamless export pathway for enterprise B2B customers utilizing FAIR (Findable, Accessible, Interoperable, Reusable) data lakes.<sup>62</sup>

The following represents the required JSON Schema draft for the extraction pipeline output:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Agentic HPLC Literature Extraction Schema",
  "description": "Structured representation of analytical HPLC conditions and observed retention mapping derived from unstructured literature.",
  "type": "object",
  "required": ["source_document_id", "molecular_entities", "chromatography_system", "method_parameters"],
  "properties": {
    "source_document_id": {
      "type": "string",
      "description": "DOI or internal vector DB identifier linking to the original publication."
    },
    "molecular_entities": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["local_identifier", "smiles_string", "observed_retention_time_min"],
        "properties": {
          "local_identifier": { "type": "string", "description": "Textual anchor, e.g., 'Compound 4a'" },
          "smiles_string": { "type": "string", "description": "Canonical SMILES generated via Graph2SMILES or text mapping" },
          "observed_retention_time_min": { "type": "number" }
        }
      }
    },
    "chromatography_system": {
      "type": "object",
      "required": ["column_manufacturer", "stationary_phase_chemistry", "column_length_mm", "column_inner_diameter_mm", "particle_size_um"],
      "properties": {
        "column_manufacturer": { "type": "string" },
        "stationary_phase_chemistry": { "type": "string", "enum": [] },
        "column_length_mm": { "type": "number", "minimum": 10, "maximum": 300 },
        "column_inner_diameter_mm": { "type": "number", "minimum": 1.0, "maximum": 4.6 },
        "particle_size_um": { "type": "number", "minimum": 1.3, "maximum": 10.0 }
      }
    },
    "method_parameters": {
      "type": "object",
      "required": [],
      "properties": {
        "mobile_phase_A": {
          "type": "object",
          "properties": {
            "solvent": { "type": "string" },
            "additive": { "type": "string" },
            "ph_estimate": { "type": "number" }
          }
        },
        "mobile_phase_B": {
          "type": "object",
          "properties": {
            "solvent": { "type": "string" }
          }
        },
        "flow_rate_ml_min": { "type": "number", "minimum": 0.1, "maximum": 5.0 },
        "column_temperature_c": { "type": "number", "minimum": 15.0, "maximum": 90.0 },
        "gradient_profile_table": {
          "type": "array",
          "description": "Piecewise linear array:",
          "items": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": [
              { "type": "number" },
              { "type": "number", "minimum": 0, "maximum": 100 }
            ]
          }
        }
      }
    }
  }
}
```

This strict bounding logic (e.g., restricting `column_inner_diameter_mm` to standard analytical dimensions between 1.0 and 4.6, explicitly excluding preparative columns) is pre-configured to assist the Validation Agent in instantly rejecting generative hallucinations. This guarantees that only chemically plausible, mathematically sound matrices enter the vector database.<sup>16</sup>

### System Architecture and Data Flow

The operational execution of the platform from the end-user perspective is designed as a seamless, high-velocity progression from molecular input to actionable machine parameters. The underlying architectural data flow orchestrates the vector database, the physics-informed surrogate model, and the agentic logic in real time.

The pipeline initiates at the User Input layer. The user provides a target SMILES string representing the desired Active Pharmaceutical Ingredient (API) alongside the SMILES strings of any known impurities, synthetic byproducts, or degradation targets.

The backend system immediately translates these SMILES strings into ECFP4 binary fingerprints utilizing the RDKit engine. This resulting query vector is routed directly to the Similarity Search module. The Milvus vector database, loaded with the historical repository of millions of agent-extracted methodologies, executes a highly parallelized `BIN_IVF_FLAT` index search utilizing the TANIMOTO metric.<sup>49</sup> The system returns the top historical methods where the historically separated molecules possess a high Tanimoto similarity to the user's target mixture. This acts as a highly constrained bounding box for the downstream optimization algorithms, ensuring the machine learning model is not blindly guessing column chemistries from scratch, but is rather seeded with empirically proven, structurally relevant scaffolds.

Simultaneously, the platform initiates the Surrogate Simulation loop. The top retrieved methods define the base parameters for the simulation: a specific column geometry, a proven stationary phase (e.g., C18), and initial boundary conditions for the gradient. The user's input SMILES are passed through the automated feature extraction pipeline, combining structural GNN embeddings with physical RDKit descriptors. The XGraphBoost hybrid model processes these features alongside the specific column parameters to predict the Linear Solvent Strength coefficients (`k_0`, `S`) individually for the target API and every designated impurity.<sup>6</sup>

With the fundamental thermodynamic parameters established, the system leverages a Bayesian Optimization algorithm (or a similar heuristic search algorithm) to iteratively mutate the proposed gradient profile.<sup>65</sup> For every mathematical mutation (e.g., steepening the initial gradient ramp from 3% to 40% B instead of 37% B over 10 minutes)<sup>43</sup>, the deterministic Physics Layer computes the exact predicted retention time (`R_t`) for every molecule in the mixture using the LSS equation.<sup>6</sup> A system cost function rigorously evaluates the mathematical distance between the predicted peaks, heavily penalizing overlapping retention times (co-elution) and excessively long overall run durations. Critical hardware factors, such as the specific instrument's dwell volume (delay volume) and extra-column dispersion volume, must be programmatically accounted for during this gradient scaling, as failure to adjust for delay volumes will result in massive retention shifts when transferred to the physical hardware.<sup>66</sup>

Once the Bayesian Optimization algorithm converges on an idealized gradient profile that achieves maximum peak resolution within the shortest allowable time constraint, the data moves to the UI Output layer. The frontend application renders an interactive, accurately simulated chromatogram utilizing modern visualization libraries. The user receives a definitive, deterministic export - comprising a precise column recommendation, flow rate, temperature, and a stepwise gradient table - ready to be programmed directly into their physical HPLC instrumentation.

## Conclusion

The realization of an AI-driven, entirely trial-free HPLC method development platform requires a masterful synthesis of disparate, highly advanced computational disciplines. By leveraging multimodal multi-agent architectures mapped to rigorous thermodynamic physical constraints via a dedicated Validation Agent, the system can reliably domesticate the chaotic, unstructured landscape of chemical literature. Replacing pure black-box deep learning architectures with a physics-informed, hybrid XGraphBoost methodology ensures peak data efficiency and deterministic scaling. Deploying this comprehensive ecosystem atop specialized vector databases like Milvus and ASM-compliant schemas guarantees that the MVP will function not merely as an algorithmic novelty, but as an interoperable, enterprise-grade scientific instrument capable of radically accelerating pharmaceutical development.

## Citerade verk

1. Librarian of Alexandria: An Extensible LLM-based Chemical Data Extraction Pipeline - ChemRxiv, hämtad 2026-04-18, https://chemrxiv.org/doi/pdf/10.26434/chemrxiv-2025-fb8hj
2. Librarian of Alexandria: An Extensible LLM-based Chemical Data ..., hämtad 2026-04-18, https://chemrxiv.org/doi/10.26434/chemrxiv-2025-fb8hj
3. (PDF) A Multi-Agent System for Information Extraction from the ..., hämtad 2026-04-18, https://www.researchgate.net/publication/394081019_A_Multi-Agent_System_for_Information_Extraction_from_the_Chemical_Literature
4. ReactionDataExtractor: A Tool for Automated Extraction of Information from Chemical Reaction Schemes - ResearchGate, hämtad 2026-04-18, https://www.researchgate.net/publication/354623544_ReactionDataExtractor_A_Tool_for_Automated_Extraction_of_Information_from_Chemical_Reaction_Schemes
5. Train, validation, and test curves of Tox21 (classification) and... - ResearchGate, hämtad 2026-04-18, https://www.researchgate.net/figure/Train-validation-and-test-curves-of-Tox21-classification-and-Freesolv-regression_fig3_351874123
6. GRIP: physics-informed neural network for gradient ... - bioRxiv, hämtad 2026-04-18, https://www.biorxiv.org/content/10.1101/2024.11.11.622855v1.full.pdf
7. Orchestrating Symbolic and Sub-Symbolic Reasoning: A Multi-Agent LLM Framework for Complex Scientific Problem-Solving - OpenReview, hämtad 2026-04-18, https://openreview.net/pdf/d06437687d89c10a2abd94b9ec95543564f837b6.pdf
8. Challenges and Opportunities for Validation of AI-Based New Approach Methods - Health and Environmental Sciences Institute, hämtad 2026-04-18, https://hesiglobal.org/wp-content/uploads/2025/10/Hartung-Kleinstreuer-2025-AI-based-NAMs.pdf
9. AutoLabs: Cognitive Multi-Agent Systems with Self-Correction for Autonomous Chemical Experimentation - arXiv, hämtad 2026-04-18, https://arxiv.org/html/2509.25651v1
10. HPLC-MS Column Choices: Particle Size, Pore Volume And Backpressure - Patsnap Eureka, hämtad 2026-04-18, https://eureka.patsnap.com/report-hplc-ms-column-choices-particle-size-pore-volume-and-backpressure
11. Column Pressure Considerations in Analytical HPLC - LCGC International, hämtad 2026-04-18, https://www.chromatographyonline.com/view/column-pressure-considerations-analytical-hplc
12. On the use of the Kozeny-Carman equation to predict the hydraulic conductivity of soils, hämtad 2026-04-18, https://cdnsciencepub.com/doi/10.1139/t03-013
13. Practical High-Performance Liquid Chromatography - ResearchGate, hämtad 2026-04-18, https://www.researchgate.net/profile/Salar-Hafez-Ghoran/post/Shimizu_PDA_SPD_M20A_no_base_line_signal_any_more/attachment/5fc7e8563b21a200015f5371/AS%3A964376412581890%401606936662063/download/Practical+High+Performance+Liquid+Chromatography%3B5th+Edition.pdf
14. Terms and equations used in HPLC explained - Analytics-Shop, hämtad 2026-04-18, https://www.analytics-shop.com/gb/hplc-definition-equations
15. What Pressure to Expect from the Thermo Scientific Accucore HPLC Columns?, hämtad 2026-04-18, https://documents.thermofisher.com/TFS-Assets/CMD/Application-Notes/TN20542-What-Pressure-Accucore-Columns-EN.pdf
16. HPLC Troubleshooting Guide, hämtad 2026-04-18, http://ccc.chem.pitt.edu/wipf/Web/LCMS%20trouble%20shooting.pdf
17. TIP # 114 Pressure Drop Across an HPLC Column. A Simplified Method To Determine It. HPLC HINTS and TIPS for CHROMATOGRAPHERS, hämtad 2026-04-18, https://www.hplctools.com/Tip_114_Pressure_Drop_Across_an_HPLC_Column.htm
18. Using Lamm-Equation Modeling of Sedimentation Velocity Data to Determine the Kinetic and Thermodynamic Properties of Macromolecular Interactions - PMC, hämtad 2026-04-18, https://pmc.ncbi.nlm.nih.gov/articles/PMC3147155/
19. An Investigation into HPLC Data Quality Problems, hämtad 2026-04-18, https://ntrs.nasa.gov/api/citations/20110011735/downloads/20110011735.pdf
20. A Global Approach to HPLC Column Selection Using Reversed Phase and HILIC Modes: What to Try When C18 Doesn't Work | LCGC International, hämtad 2026-04-18, https://www.chromatographyonline.com/view/global-approach-hplc-column-selection-using-reversed-phase-and-hilic-modes-what-try-when-c18-doesnt
21. Evaluation of the Base Stability of Hydrophilic Interaction Chromatography Columns Packed with Silica or Ethylene-Bridged Hybrid Particles - MDPI, hämtad 2026-04-18, https://www.mdpi.com/2297-8739/9/6/146
22. Agilent HPlC Column Selection guide - SOLUTIONS FOR SMALL MOLECULE SEPARATIONS, hämtad 2026-04-18, https://www.agilent.com/Library/selectionguide/Public/5991-0165EN.pdf
23. Stability and Performance of Cyano Bonded Phase HPLC Columns for Reversed-Phase, Normal-Phase and HILIC Applications, hämtad 2026-04-18, https://lcms.cz/labrulez-bucket-strapi-h3hsga3/t410171h_ddba39d365/t410171h.pdf
24. Prediction of Chromatographic Retention Time of a Small Molecule from SMILES Representation Using a Hybrid Transformer-LSTM Model - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.jcim.5c00167
25. Separation Science: The State of the Art: Graph Neural Networks for Improved Retention Time Predictions | LCGC International, hämtad 2026-04-18, https://www.chromatographyonline.com/view/separation-science-the-state-of-the-art-graph-neural-networks-for-improved-retention-time-predictions
26. HPLC Column Selection Guide - Phenomenex, hämtad 2026-04-18, https://www.phenomenex.com/knowledge-center/hplc-knowledge-center/hplc-column-selection-guide
27. Benchmarking GNN Models on Molecular Regression Tasks with CKA-Based Representation Analysis - arXiv.org, hämtad 2026-04-18, https://arxiv.org/html/2602.20573v1
28. ChemXTree: A Feature-Enhanced Graph Neural Network-Neural Decision Tree Framework for ADMET Prediction - PMC, hämtad 2026-04-18, https://pmc.ncbi.nlm.nih.gov/articles/PMC11600499/
29. Advancements in Molecular Property Prediction: A Survey of Single and Multimodal Approaches - arXiv, hämtad 2026-04-18, https://arxiv.org/html/2408.09461v1
30. Performance and robustness of small molecule retention time prediction with molecular graph neural networks in industrial drug discovery campaigns - PMC, hämtad 2026-04-18, https://pmc.ncbi.nlm.nih.gov/articles/PMC11021461/
31. XGraphBoost: Extracting Graph Neural Network-Based Features for a Better Prediction of Molecular Properties | Journal of Chemical Information and Modeling - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.jcim.0c01489
32. HiGNN: A Hierarchical Informative Graph Neural Network for Molecular Property Prediction Equipped with Feature-Wise Attention - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.jcim.2c01099
33. unimatch: universal matching from atom to task for few-shot drug discovery - arXiv, hämtad 2026-04-18, https://arxiv.org/pdf/2502.12453
34. ChemXTree: A Feature-Enhanced Graph Neural Network-Neural Decision Tree Framework for ADMET Prediction | Journal of Chemical Information and Modeling - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.jcim.4c01186
35. Evaluating Machine Learning Models for Molecular Property Prediction: Performance and Robustness on Out-of-Distribution Data - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.jcim.5c00475
36. Evaluating Machine Learning Models for Molecular Property Prediction: Performance and Robustness on Out-of-Distribution Data - PMC, hämtad 2026-04-18, https://pmc.ncbi.nlm.nih.gov/articles/PMC12529777/
37. Graph Neural Networks for Molecular Property Prediction | by Amit Yadav - Medium, hämtad 2026-04-18, https://medium.com/biased-algorithms/graph-neural-networks-for-molecular-property-prediction-ed9b87241890
38. Graph Neural Networks as a Potential Tool in Improving Virtual Screening Programs, hämtad 2026-04-18, https://www.frontiersin.org/journals/chemistry/articles/10.3389/fchem.2021.787194/full
39. ChemXTree:A Tree-enhanced Classification Approach to Small-molecule Drug Discovery, hämtad 2026-04-18, https://www.biorxiv.org/content/10.1101/2023.11.28.568989v1.full-text
40. ChemXTree: A Feature-Enhanced Graph Neural Network-Neural Decision Tree Framework for ADMET Prediction - ResearchGate, hämtad 2026-04-18, https://www.researchgate.net/publication/385555396_ChemXTree_A_Feature-Enhanced_Graph_Neural_Network-Neural_Decision_Tree_Framework_for_ADMET_Prediction
41. Gradient Retention Time Modeling in Ion Chromatography through Ensemble Machine Learning-Powered Quantitative Structure-Retention Relationships | ACS Omega - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acsomega.4c09868
42. Estimation and Uncertainty Quantification of Solvent Strength Parameters in Gradient Elution of Chromatography Using Sequential Monte Carlo Method - MDPI, hämtad 2026-04-18, https://www.mdpi.com/2227-9717/13/1/114
43. A Comprehensive Study of Gradient Conditions for Deep Proteome Discovery in a Complex Protein Matrix - MDPI, hämtad 2026-04-18, https://www.mdpi.com/1422-0067/23/19/11714
44. From Reverse Phase Chromatography to HILIC: Graph Transformers Power Method-Independent Machine Learning of Retention Times | Analytical Chemistry - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.analchem.4c05859
45. GRIP: physics-informed neural network for gradient retention time prediction in liquid chromatography - ResearchGate, hämtad 2026-04-18, https://www.researchgate.net/publication/385753038_GRIP_physics-informed_neural_network_for_gradient_retention_time_prediction_in_liquid_chromatography
46. Automatic Metadata Extraction | Vectorize Docs, hämtad 2026-04-18, https://docs.vectorize.io/build-deploy/data-pipelines/automatic-metadata-extraction/
47. Understanding Vector Search in Qdrant, hämtad 2026-04-18, https://qdrant.tech/documentation/overview/vector-search/
48. What is Vector Similarity? Understanding its Role in AI Applications. - Qdrant, hämtad 2026-04-18, https://qdrant.tech/blog/what-is-vector-similarity/
49. Similarity Metrics Milvus v2.2.x documentation, hämtad 2026-04-18, https://milvus.io/docs/v2.2.x/metric.md
50. Build an Index on Vectors Milvus v2.2.x documentation, hämtad 2026-04-18, https://milvus.io/docs/v2.2.x/build_index.md
51. Milvus Vector Database Overview | PDF - Scribd, hämtad 2026-04-18, https://www.scribd.com/document/658697058/Milvus-Overview
52. Milvus: A Purpose-Built Vector Data Management System - CS@Purdue, hämtad 2026-04-18, https://www.cs.purdue.edu/homes/csjgwang/pubs/SIGMOD21_Milvus.pdf
53. How does molecular similarity search work? - Milvus, hämtad 2026-04-18, https://milvus.io/ai-quick-reference/how-does-molecular-similarity-search-work
54. What is molecular similarity search? - Milvus, hämtad 2026-04-18, https://milvus.io/ai-quick-reference/what-is-molecular-similarity-search
55. Hybrid Quantum Graph Neural Network for Molecular Property Prediction - arXiv, hämtad 2026-04-18, https://arxiv.org/html/2405.05205v1
56. Mass spectrometry data format - Wikipedia, hämtad 2026-04-18, https://en.wikipedia.org/wiki/Mass_spectrometry_data_format
57. TetraScience Accelerates Allotrope Simple Model (ASM) Generation with AI, hämtad 2026-04-18, https://www.tetrascience.com/blog/tetrascience-accelerates-allotrope-simple-model-asm-generation-with-ai
58. Introduction to the Simple Model (ASM) - Allotrope Foundation, hämtad 2026-04-18, https://www.allotrope.org/introduction-to-allotrope-simple-model
59. List of Models (ASM, ADM) | allotropefoundation, hämtad 2026-04-18, https://www.allotrope.org/product-releases
60. Thermo Fisher Scientific, Chromeleon Configuration Guide - Benchling Help Center, hämtad 2026-04-18, https://help.benchling.com/hc/en-us/articles/29545115046925-Thermo-Fisher-Scientific-Chromeleon-Configuration-Guide
61. asm - Allotrope-Public - GitLab, hämtad 2026-04-18, https://gitlab.com/allotrope-public/asm
62. Adamant: a JSON schema-based metadata editor for research data management workflows, hämtad 2026-04-18, https://pmc.ncbi.nlm.nih.gov/articles/PMC9178528/
63. Explore TetraScience Resources, hämtad 2026-04-18, https://www.tetrascience.com/resources
64. An enhanced FAIRization concept to achieve machine actionability of biologics data., hämtad 2026-04-18, https://archiv.ub.uni-heidelberg.de/volltextserver/36104/1/Dissertation_AxelWilbertz_PDFA.pdf
65. Chemometric Strategies for Fully Automated Interpretive Method Development in Liquid Chromatography | Analytical Chemistry - ACS Publications, hämtad 2026-04-18, https://pubs.acs.org/doi/10.1021/acs.analchem.2c03160
66. Myths and Facts: Sampling Frequency, Response Time, and Extra-Column Effects in HPLC, hämtad 2026-04-18, https://jascoinc.com/applications/myths-and-facts-sampling-frequency-response-time-and-extra-column-effects-in-hplc/
67. HPLC Method Development: From Beginner to Expert Part 2 - Agilent, hämtad 2026-04-18, https://www.agilent.com/cs/library/slidepresentation/public/hplc-method-development-part-2-mar282024.pdf
68. Efficient LC Method Transfer Tool for Labs - Phenomenex, hämtad 2026-04-18, https://www.phenomenex.com/tools/lc-transfer

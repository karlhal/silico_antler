// Curated catalogs the user can click to add to inventory.

export const COLUMN_PRESETS = [
  { id: "c18-100-2.1-1.7", label: "C18 100×2.1 mm 1.7µm", category: "Reversed-phase" },
  { id: "c18-150-2.1-1.7", label: "C18 150×2.1 mm 1.7µm", category: "Reversed-phase" },
  { id: "c18-150-4.6-3", label: "C18 150×4.6 mm 3µm", category: "Reversed-phase" },
  { id: "c18-50-2.1-1.7", label: "C18 50×2.1 mm 1.7µm (fast)", category: "Reversed-phase" },
  { id: "c8-150-4.6-5", label: "C8 150×4.6 mm 5µm", category: "Reversed-phase" },
  { id: "phenyl-100-2.1-1.7", label: "Phenyl-Hexyl 100×2.1 mm 1.7µm", category: "Reversed-phase" },
  { id: "ph-100-2.1-1.7", label: "PFP 100×2.1 mm 1.7µm", category: "Reversed-phase" },
  { id: "hilic-150-2.1-3", label: "HILIC 150×2.1 mm 3µm", category: "HILIC" },
  { id: "amide-150-2.1-1.7", label: "BEH Amide 150×2.1 mm 1.7µm", category: "HILIC" },
  { id: "sec-300-7.8", label: "SEC 300×7.8 mm 5µm", category: "Size exclusion" },
  { id: "iex-anion", label: "IEX anion 150×4.0 mm", category: "Ion exchange" },
  { id: "chiral-od-h", label: "Chiralcel OD-H 250×4.6 mm", category: "Chiral" },
];

export const SOLVENT_PRESETS = [
  { id: "water", label: "Water (LC-MS grade)", category: "Aqueous" },
  { id: "fa-water", label: "0.1% formic acid in water", category: "Aqueous" },
  { id: "tfa-water", label: "0.1% TFA in water", category: "Aqueous" },
  { id: "ammf-water", label: "10 mM ammonium formate (pH 3.5)", category: "Aqueous" },
  { id: "ammac-water", label: "10 mM ammonium acetate (pH 6.8)", category: "Aqueous" },
  { id: "phos-water", label: "20 mM phosphate buffer (pH 2.5)", category: "Aqueous" },
  { id: "mecn", label: "Acetonitrile", category: "Organic" },
  { id: "fa-mecn", label: "0.1% formic acid in acetonitrile", category: "Organic" },
  { id: "meoh", label: "Methanol", category: "Organic" },
  { id: "ipa", label: "Isopropanol", category: "Organic" },
  { id: "thf", label: "Tetrahydrofuran", category: "Organic" },
];

export const PUMP_PRESETS = [
  "Agilent 1260 Infinity II",
  "Agilent 1290 Infinity II",
  "Waters Acquity H-Class",
  "Waters Acquity I-Class",
  "Thermo Vanquish Flex",
  "Shimadzu Nexera X3",
];

export const DETECTOR_PRESETS = [
  "DAD (UV/Vis)",
  "VWD (single λ)",
  "FLD (fluorescence)",
  "RID (refractive index)",
  "ELSD",
  "CAD (charged aerosol)",
  "MS — single quad",
  "MS — triple quad (MS/MS)",
  "MS — Q-TOF",
  "MS — Orbitrap",
];

export const MATRIX_PRESETS = [
  "Brewed coffee",
  "Plasma (human)",
  "Urine",
  "Tablet extract",
  "Cell culture media",
  "Drinking water",
  "Soil extract",
  "Fermentation broth",
  "Reaction mixture",
];

export const COMMON_ANALYTES = [
  { name: "Caffeine", logp: -0.07, lambda_max_nm: 273 },
  { name: "Theobromine", logp: -0.78, lambda_max_nm: 272 },
  { name: "Ibuprofen", logp: 3.97, pka: "4.91", lambda_max_nm: 222 },
  { name: "Acetaminophen", logp: 0.46, pka: "9.38", lambda_max_nm: 243 },
  { name: "Aspirin", logp: 1.19, pka: "3.5", lambda_max_nm: 230 },
  { name: "Naproxen", logp: 3.18, pka: "4.15", lambda_max_nm: 230 },
];

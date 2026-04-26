// Shared types for the Chroma HPLC IDE

export interface Inventory {
  pump: string;
  detector: string;
  columns: string[]; // one entry per column line
  solvents: string[];
}

export interface GradientPoint {
  time_min: number;
  percent_b: number;
}

export interface MethodSpec {
  mode: string; // RP, HILIC, IP, etc
  column: { choice: string; reason: string };
  mobile_phase: { a: string; b: string; buffer_notes?: string };
  gradient: GradientPoint[];
  flow_rate_ml_min: number;
  column_temperature_c: number;
  injection_volume_ul: number;
  run_time_min: number;
  detection: { detector: string; wavelength_nm: string; notes?: string };
  sample_prep: string;
  rationale: string;
  warnings: string[];
}

export interface Method extends MethodSpec {
  id: string;
  projectId: string;
  version: number;
  parentId?: string;
  name: string; // e.g. "Method v3"
  createdAt: number;
}

export interface Analyte {
  name: string;
  logp?: number | null;
  pka?: string | null;
  lambda_max_nm?: number | null;
  notes?: string | null;
}

export interface Brief {
  analytes: Analyte[];
  matrix: string;
  goal: string;
}

export interface Project {
  id: string;
  name: string;
  brief: Brief;
  createdAt: number;
  methodIds: string[];
  activeMethodId?: string;
}

export interface PredictedPeak {
  name: string;
  rt_min: number;
  height: number; // 0..1
  width_min: number;
}

export interface PredictedChromatogram {
  total_time_min: number;
  peaks: PredictedPeak[];
}

export interface Run {
  id: string;
  methodId: string;
  projectId: string;
  predicted: PredictedChromatogram;
  notes?: string;
  createdAt: number;
}

export type WorkbenchTab = "brief" | "method" | "gradient" | "chromatogram" | "runs";

export interface ChatEvent {
  id: string;
  role: "user" | "assistant" | "system";
  content: string; // markdown for assistant/user; short label for system events
  kind?: "message" | "tool"; // tool = "Agent did X" line
  pending?: boolean;
  createdAt: number;
  toolName?: string;
  toolArgs?: unknown;
  toolOk?: boolean;
  pendingAction?: {
    type: "verify_recognition" | "approve_plan" | "view_results";
    label: string;
    data?: any;
  };
}

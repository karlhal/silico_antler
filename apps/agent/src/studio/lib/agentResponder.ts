import type { ToolCall } from "@/studio/agent/tools";
import { COMMON_ANALYTES } from "@/studio/lib/presets";
import type { GradientPoint } from "@/studio/types/hplc";

interface AgentSnapshot {
  inventory: {
    pump: string;
    detector: string;
    columns: string[];
    solvents: string[];
  };
  activeProject: {
    id: string;
    name: string;
    brief: {
      analytes: Array<{ name: string; lambda_max_nm?: number | null }>;
      matrix: string;
      goal: string;
    };
    methodIds: string[];
  } | null;
  activeMethod: {
    id: string;
    mode: string;
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
  } | null;
  projects: Array<{ id: string; name: string; methodCount: number }>;
}

interface AgentReply {
  content: string;
  toolCalls: ToolCall[];
}

interface DraftBrief {
  analytes: Array<{ name: string; lambda_max_nm?: number | null }>;
  matrix: string;
  goal: string;
}

const KNOWN_ANALYTE_LOOKUP = COMMON_ANALYTES.reduce<Record<string, (typeof COMMON_ANALYTES)[number]>>(
  (accumulator, analyte) => {
    accumulator[analyte.name.toLowerCase()] = analyte;
    return accumulator;
  },
  {},
);

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase())
    .join(" ");
}

function detectAnalytes(prompt: string) {
  const lower = prompt.toLowerCase();
  const detected = COMMON_ANALYTES.filter((analyte) => lower.includes(analyte.name.toLowerCase())).map(
    (analyte) => ({
      name: analyte.name,
      lambda_max_nm: analyte.lambda_max_nm ?? null,
    }),
  );

  if (detected.length > 0) {
    return detected;
  }

  const forMatch = prompt.match(/for ([a-z0-9,\- /]+?)(?: in | on | with |$)/i);
  if (!forMatch) {
    return [];
  }

  return forMatch[1]
    .split(/,| and /i)
    .map((entry) => titleCase(entry.trim()))
    .filter(Boolean)
    .slice(0, 4)
    .map((name) => ({
      name,
      lambda_max_nm: KNOWN_ANALYTE_LOOKUP[name.toLowerCase()]?.lambda_max_nm ?? null,
    }));
}

function detectMatrix(prompt: string): string {
  const lower = prompt.toLowerCase();
  if (lower.includes("coffee")) return "Brewed coffee";
  if (lower.includes("plasma")) return "Plasma (human)";
  if (lower.includes("urine")) return "Urine";
  if (lower.includes("tablet")) return "Tablet extract";
  if (lower.includes("water")) return "Drinking water";
  if (lower.includes("media")) return "Cell culture media";
  if (lower.includes("broth")) return "Fermentation broth";
  if (lower.includes("reaction")) return "Reaction mixture";
  return "";
}

function detectRuntime(prompt: string): number | null {
  const match = prompt.match(/(\d+(?:\.\d+)?)\s*(?:min|minute)/i);
  return match ? Number(match[1]) : null;
}

function inferGoal(prompt: string): string {
  const runtime = detectRuntime(prompt);
  const requiresMs = /\bms\b|mass spec|ms-friendly|ms friendly/i.test(prompt);
  const goalParts = ["Draft a screening method with a credible first-pass gradient."];
  if (runtime) {
    goalParts.push(`Keep total runtime near ${runtime} minutes.`);
  }
  if (requiresMs) {
    goalParts.push("Maintain MS-compatible mobile phases.");
  }
  return goalParts.join(" ");
}

function inferProjectName(analytes: DraftBrief["analytes"], matrix: string) {
  if (analytes.length === 0) {
    return matrix ? `${matrix} study` : "Method development";
  }

  const analyteLabel =
    analytes.length === 1 ? analytes[0].name : `${analytes[0].name} + ${analytes.length - 1} more`;
  return matrix ? `${analyteLabel} in ${matrix}` : analyteLabel;
}

function buildGradient(runtime: number): GradientPoint[] {
  const roundedRuntime = Math.max(4, Math.round(runtime));
  return [
    { time_min: 0, percent_b: 6 },
    { time_min: Math.max(1.5, roundedRuntime * 0.2), percent_b: 12 },
    { time_min: Math.max(3, roundedRuntime * 0.72), percent_b: 62 },
    { time_min: roundedRuntime, percent_b: 90 },
  ];
}

function preferredColumn(prompt: string, inventoryColumns: string[]) {
  const lower = prompt.toLowerCase();
  const fromInventory = inventoryColumns[0];
  if (lower.includes("hilic")) return "BEH Amide 150×2.1 mm 1.7µm";
  if (lower.includes("phenyl")) return "Phenyl-Hexyl 100×2.1 mm 1.7µm";
  if (lower.includes("c8")) return "C8 150×4.6 mm 5µm";
  if (lower.includes("c18")) return "C18 100×2.1 mm 1.7µm";
  return fromInventory || "C18 100×2.1 mm 1.7µm";
}

function buildMethodSpec(prompt: string, snapshot: AgentSnapshot, draftBrief: DraftBrief) {
  const requiresMs = /\bms\b|mass spec|ms-friendly|ms friendly/i.test(prompt);
  const runtime = detectRuntime(prompt) ?? (requiresMs ? 8 : 12);
  const columnChoice = preferredColumn(prompt, snapshot.inventory.columns);
  const analyteLabel =
    draftBrief.analytes.length > 0
      ? draftBrief.analytes.map((entry) => entry.name).join(", ")
      : "the target analyte set";
  const msFriendlyA = "Water + 0.1% formic acid";
  const msFriendlyB = "Acetonitrile + 0.1% formic acid";
  const standardA = snapshot.inventory.solvents.find((entry) => /water/i.test(entry)) || msFriendlyA;
  const standardB =
    snapshot.inventory.solvents.find((entry) => /acetonitrile|methanol/i.test(entry)) ||
    (requiresMs ? msFriendlyB : "Acetonitrile");
  const detector =
    requiresMs || /ms/i.test(snapshot.inventory.detector)
      ? "MS — triple quad (MS/MS)"
      : snapshot.inventory.detector || "DAD (UV/Vis)";
  const wavelength =
    draftBrief.analytes[0]?.lambda_max_nm != null ? String(draftBrief.analytes[0].lambda_max_nm) : "254";

  return {
    mode: /hilic/i.test(prompt) ? "HILIC" : "RP-LC",
    column: {
      choice: columnChoice,
      reason: `Chosen as a practical first-pass geometry for ${analyteLabel} in ${draftBrief.matrix || "the stated matrix"}.`,
    },
    mobile_phase: {
      a: requiresMs ? msFriendlyA : standardA,
      b: requiresMs ? msFriendlyB : standardB,
      buffer_notes: requiresMs
        ? "Volatile acid additive to keep the method MS-compatible."
        : "Start with a broadly transferable reversed-phase solvent pair.",
    },
    gradient: buildGradient(runtime),
    flow_rate_ml_min: columnChoice.includes("2.1") ? 0.35 : 1,
    column_temperature_c: 35,
    injection_volume_ul: columnChoice.includes("2.1") ? 2 : 5,
    run_time_min: runtime,
    detection: {
      detector,
      wavelength_nm: wavelength,
      notes: requiresMs ? "MS-compatible starting point." : "UV wavelength seeded from the primary analyte when available.",
    },
    sample_prep: draftBrief.matrix
      ? `Start with a light cleanup suitable for ${draftBrief.matrix.toLowerCase()}, then dilute into initial mobile-phase strength.`
      : "Use a simple dilution / centrifugation step before the first scouting run.",
    rationale:
      `This is a conservative scouting method designed to get ${analyteLabel} onto the column quickly, ` +
      "establish retention order, and leave room for later selectivity tuning.",
    warnings: [
      "Treat this as a first-pass screen rather than a validated transfer method.",
      requiresMs
        ? "If ion suppression appears, reduce additive strength before changing the gradient."
        : "If peak shape is weak at the front, adjust starting organic strength before switching chemistry.",
    ],
  };
}

function buildPredictedChromatogram(snapshot: AgentSnapshot) {
  const analytes =
    snapshot.activeProject?.brief.analytes.map((entry) => entry.name) ??
    ["Target analyte", "Impurity A", "Impurity B"];
  const totalTime = snapshot.activeMethod?.run_time_min ?? 10;
  const peaks = analytes.map((name, index) => ({
    name,
    rt_min: Number((1.2 + index * (totalTime / (analytes.length + 1))).toFixed(2)),
    height: Number((0.92 - index * 0.16).toFixed(2)),
    width_min: Number((0.18 + index * 0.03).toFixed(2)),
  }));
  return { total_time_min: totalTime, peaks };
}

function buildInventoryToolCall(prompt: string): ToolCall | null {
  const lower = prompt.toLowerCase();
  const columns: string[] = [];
  const solvents: string[] = [];

  if (lower.includes("c18")) columns.push("C18 100×2.1 mm 1.7µm");
  if (lower.includes("hilic")) columns.push("BEH Amide 150×2.1 mm 1.7µm");
  if (lower.includes("phenyl")) columns.push("Phenyl-Hexyl 100×2.1 mm 1.7µm");
  if (lower.includes("water")) solvents.push("Water (LC-MS grade)");
  if (lower.includes("acetonitrile")) solvents.push("Acetonitrile");
  if (lower.includes("methanol")) solvents.push("Methanol");
  if (lower.includes("formic acid")) solvents.push("0.1% formic acid in water");

  if (columns.length === 0 && solvents.length === 0 && !/inventory|hardware|column|solvent/i.test(prompt)) {
    return null;
  }

  return {
    name: "add_to_inventory",
    args: { columns, solvents },
  };
}

function answerQuestion(prompt: string, snapshot: AgentSnapshot): string {
  const lower = prompt.toLowerCase();

  if (/what can you do|help/i.test(prompt)) {
    return [
      "I can take natural-language instructions and operate the imported studio shell for you.",
      "",
      "- create or update the project brief",
      "- draft a first-pass HPLC method",
      "- tune the active method to be faster or more MS-friendly",
      "- add inventory items like columns and solvents",
      "- generate a predicted chromatogram for the current method",
    ].join("\n");
  }

  if (/what('| i)?s missing|what should i do next|next step/i.test(prompt)) {
    if (!snapshot.activeProject) {
      return "Start by telling me the analyte, matrix, and goal. For example: `Design a method for caffeine in coffee, MS-friendly, under 8 min.`";
    }
    if (!snapshot.activeMethod) {
      return "The project brief is in place. The next useful step is to ask me to draft a method for the active project.";
    }
    return "The brief and method are both present. The next useful step is to predict a chromatogram or ask for a focused method change such as `make it faster` or `switch to an MS-friendly buffer`.";
  }

  if (/why/i.test(prompt) && snapshot.activeMethod) {
    return snapshot.activeMethod.rationale;
  }

  if (/summary|summarize|status/i.test(prompt)) {
    if (!snapshot.activeProject) {
      return "No project is active yet. The imported studio shell is ready for a project brief.";
    }

    const analytes = snapshot.activeProject.brief.analytes.map((entry) => entry.name).join(", ") || "none";
    const methodStatus = snapshot.activeMethod
      ? `Active method: ${snapshot.activeMethod.column.choice}, ${snapshot.activeMethod.run_time_min} min runtime.`
      : "No active method yet.";
    return `Project: ${snapshot.activeProject.name}. Analytes: ${analytes}. Matrix: ${snapshot.activeProject.brief.matrix || "not set"}. ${methodStatus}`;
  }

  return "I can answer workflow questions, build the brief, draft a method, and predict a chromatogram inside this imported studio shell.";
}

export function generateStudioAgentRecognition(prompt: string, snapshot: AgentSnapshot) {
  const analytes = detectAnalytes(prompt);
  const matrix = detectMatrix(prompt);
  const runtime = detectRuntime(prompt);
  const requiresMs = /\bms\b|mass spec|ms-friendly|ms friendly/i.test(prompt);
  
  return {
    analytes,
    matrix,
    runtime,
    requiresMs,
    hardware: snapshot.inventory,
  };
}

export function generateStudioAgentPlan(recognition: any, snapshot: AgentSnapshot) {
  const steps: string[] = [];
  
  if (!snapshot.activeProject) {
    steps.push(`Create a new project named "${inferProjectName(recognition.analytes, recognition.matrix)}"`);
    steps.push(`Configure brief with ${recognition.analytes.length} analytes and goal: "${inferGoal("")}"`);
  } else {
    steps.push("Update the active project brief with new constraints");
  }
  
  steps.push("Draft a first-pass HPLC method matching your hardware");
  
  if (recognition.requiresMs) {
    steps.push("Ensure mobile phases and additives are MS-compatible");
  }
  
  return {
    summary: `I've constructed a research protocol to address your request for ${recognition.analytes.map((a: any) => a.name).join(", ")}.`,
    steps,
  };
}

export function generateStudioAgentReply(prompt: string, snapshot: AgentSnapshot): AgentReply {
  const trimmed = prompt.trim();
  const lower = trimmed.toLowerCase();
  const draftBrief: DraftBrief = {
    analytes:
      detectAnalytes(trimmed).length > 0
        ? detectAnalytes(trimmed)
        : snapshot.activeProject?.brief.analytes ?? [],
    matrix: detectMatrix(trimmed) || snapshot.activeProject?.brief.matrix || "",
    goal: snapshot.activeProject?.brief.goal || inferGoal(trimmed),
  };
  const toolCalls: ToolCall[] = [];

  const inventoryCall = buildInventoryToolCall(trimmed);
  if (inventoryCall) {
    toolCalls.push(inventoryCall);
  }

  const wantsMethod = /draft|design|build|create/i.test(trimmed) && /method/i.test(trimmed);
  const wantsPrediction = /predict|chromatogram|show peaks/i.test(trimmed);
  const wantsFaster = /faster|shorter|speed up/i.test(trimmed);
  const wantsMsFriendly = /\bms\b|mass spec|ms-friendly|ms friendly/i.test(trimmed);
  const questionLike = trimmed.endsWith("?") || /^(what|why|how|should|can|where)\b/i.test(trimmed);

  if (!snapshot.activeProject && (draftBrief.analytes.length > 0 || /project|method|separate|screen/i.test(trimmed))) {
    toolCalls.push({
      name: "create_project",
      args: {
        name: inferProjectName(draftBrief.analytes, draftBrief.matrix),
        analytes: draftBrief.analytes,
        matrix: draftBrief.matrix,
        goal: draftBrief.goal,
      },
    });
  } else if (snapshot.activeProject && (draftBrief.analytes.length > 0 || draftBrief.matrix || /brief|goal|matrix|analyte/i.test(trimmed))) {
    toolCalls.push({
      name: "update_brief",
      args: {
        analytes: draftBrief.analytes.length > 0 ? draftBrief.analytes : undefined,
        matrix: draftBrief.matrix || undefined,
        goal: draftBrief.goal || undefined,
      },
    });
  }

  if (wantsMethod) {
    toolCalls.push({
      name: snapshot.activeMethod ? "update_method" : "create_method",
      args: snapshot.activeMethod
        ? {
            inplace: false,
            ...buildMethodSpec(trimmed, snapshot, draftBrief),
          }
        : buildMethodSpec(trimmed, snapshot, draftBrief),
    });
  } else if (snapshot.activeMethod && (wantsFaster || wantsMsFriendly)) {
    const nextRuntime = wantsFaster
      ? Math.max(4, Math.round(snapshot.activeMethod.run_time_min * 0.72))
      : snapshot.activeMethod.run_time_min;
    toolCalls.push({
      name: "update_method",
      args: {
        inplace: false,
        run_time_min: nextRuntime,
        mobile_phase: wantsMsFriendly
          ? {
              a: "Water + 0.1% formic acid",
              b: "Acetonitrile + 0.1% formic acid",
              buffer_notes: "Switched to a volatile additive system for MS compatibility.",
            }
          : snapshot.activeMethod.mobile_phase,
        detection: wantsMsFriendly
          ? {
              detector: "MS — triple quad (MS/MS)",
              wavelength_nm: snapshot.activeMethod.detection.wavelength_nm,
              notes: "Promoted to an MS-compatible detection setup.",
            }
          : snapshot.activeMethod.detection,
        gradient: buildGradient(nextRuntime),
        rationale: wantsMsFriendly
          ? "Updated to a volatile mobile-phase system so the method remains compatible with MS detection."
          : "Compressed the gradient and shortened runtime to create a faster scouting variant.",
        warnings: [
          "This fork prioritizes speed over deep selectivity optimization.",
          "Verify early elution spacing before treating the faster variant as the new default.",
        ],
      },
    });
  }

  if (wantsPrediction) {
    toolCalls.push({
      name: "predict_chromatogram",
      args: {
        ...buildPredictedChromatogram(snapshot),
        notes: "Predicted from the imported studio shell adapter.",
      },
    });
  }

  if (toolCalls.length === 0 && questionLike) {
    return {
      content: answerQuestion(trimmed, snapshot),
      toolCalls: [],
    };
  }

  if (toolCalls.length === 0) {
    return {
      content:
        "I didn’t apply anything yet. Try a concrete instruction like `Design a method for caffeine in coffee, MS-friendly, under 8 min` or `make the current method faster`.",
      toolCalls: [],
    };
  }

  const actionLabels = toolCalls.map((call) => {
    switch (call.name) {
      case "create_project":
        return "created or refreshed the project brief";
      case "update_brief":
        return "updated the brief";
      case "create_method":
        return "drafted a full method";
      case "update_method":
        return "forked the current method into a revised variant";
      case "predict_chromatogram":
        return "predicted a chromatogram";
      case "add_to_inventory":
        return "updated the lab inventory";
      default:
        return call.name;
    }
  });

  return {
    content: [
      "Applied the request inside the imported studio shell.",
      "",
      ...actionLabels.map((label) => `- ${label}`),
    ].join("\n"),
    toolCalls,
  };
}

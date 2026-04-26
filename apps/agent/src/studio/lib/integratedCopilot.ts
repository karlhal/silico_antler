import type { Dispatch, SetStateAction } from "react";

import type {
  AgentResultOrigin,
  AgentRuntimeMode,
  ClarificationQuestion,
  DiscoverySource,
  DiscoveryTarget,
  Recommendation,
  RecommendationReportMeta,
  ResearchStep,
  SystemSpecs,
} from "@/types";

type SetTarget = Dispatch<SetStateAction<DiscoveryTarget>>;
type SetSystemSpecs = Dispatch<SetStateAction<SystemSpecs>>;
type SetSource = (value: DiscoverySource) => void;

export interface IntegratedCopilotContext {
  target: DiscoveryTarget;
  systemSpecs: SystemSpecs;
  source: DiscoverySource;
  runtimeMode: AgentRuntimeMode | null;
  resultOrigin: AgentResultOrigin | null;
  reportMeta: RecommendationReportMeta | null;
  activeRecommendation: Recommendation | null;
  steps: ResearchStep[];
  pendingClarification: ClarificationQuestion[] | null;
  setTarget: SetTarget;
  setSystemSpecs: SetSystemSpecs;
  setSource: SetSource;
  addImpurity: () => void;
  runDiscovery: () => Promise<void>;
  rerunDiscovery: () => Promise<void>;
}

export interface CopilotMutation {
  field: string;
  value: string;
}

export interface CopilotReply {
  content: string;
  mutations: CopilotMutation[];
}

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase())
    .join(" ");
}

function extractAnalyte(prompt: string): string | null {
  const explicit = prompt.match(/(?:for|separate|analyte)\s+([a-z0-9\- ]+?)(?:\s+in\s+|\s*,|\s+on\s+|$)/i);
  if (explicit?.[1]) {
    return titleCase(explicit[1].trim());
  }

  if (/metformin/i.test(prompt)) return "Metformin";
  if (/caffeine/i.test(prompt)) return "Caffeine";
  if (/ibuprofen/i.test(prompt)) return "Ibuprofen";
  if (/acetaminophen/i.test(prompt)) return "Acetaminophen";
  return null;
}

function extractMatrix(prompt: string): string | null {
  if (/plasma/i.test(prompt)) return "Human Plasma";
  if (/coffee/i.test(prompt)) return "Other";
  if (/\bwater\b/i.test(prompt)) return "Water";
  if (/solvent/i.test(prompt)) return "Solvent";
  return null;
}

function extractCustomMatrix(prompt: string): string | null {
  if (/coffee/i.test(prompt)) return "Brewed coffee";
  return null;
}

function extractRuntime(prompt: string): number | null {
  const match = prompt.match(/(\d+(?:\.\d+)?)\s*(?:min|minutes?)/i);
  return match ? Number(match[1]) : null;
}

function buildSummary(context: IntegratedCopilotContext): string {
  if (!context.activeRecommendation) {
    const busyStep = context.steps.find((step) => step.status === "active");
    if (busyStep) {
      return `Discovery is currently running at the \`${busyStep.label}\` stage.`;
    }
    if (context.pendingClarification?.length) {
      return `The workflow is waiting on ${context.pendingClarification.length} clarification question${context.pendingClarification.length === 1 ? "" : "s"}.`;
    }
    return "No recommendation report is active yet. I can help fill fields or prepare the run draft.";
  }

  const recommendation = context.activeRecommendation;
  const method = recommendation.recommended_method;
  const trust = recommendation.trust;
  return [
    `Top recommendation: ${recommendation.title}.`,
    method?.run_time_min ? `Scaled runtime ${method.run_time_min.toFixed(1)} min.` : null,
    `Trust posture: ${trust.trust_state.replace(/_/g, " ")} / ${trust.validation_status.replace(/_/g, " ")}.`,
    context.resultOrigin ? `Result origin: ${context.resultOrigin.replace(/_/g, " ")}.` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

export async function runIntegratedCopilotPrompt(
  prompt: string,
  context: IntegratedCopilotContext,
): Promise<CopilotReply> {
  const lower = prompt.trim().toLowerCase();
  const mutations: CopilotMutation[] = [];

  if (!lower) {
    return { content: "Enter a prompt to update the workflow draft or ask a question.", mutations };
  }

  if (/^(what|why|how|status|summary|explain)|\?$/.test(lower)) {
    return {
      content: buildSummary(context),
      mutations,
    };
  }

  if (/demo/i.test(lower)) {
    context.setTarget((current) => ({
      ...current,
      requestText: "Quantification of Metformin in human plasma by reversed-phase HPLC for a bioequivalence study",
      analyteName: "Metformin",
      matrix: "Human Plasma",
      customMatrix: "",
      requireMS: false,
      maxRunTimeMin: null,
    }));
    context.setSystemSpecs((current) => ({
      ...current,
      columnManufacturer: "Waters",
      columnName: "Acquity BEH C18",
      columnChemistry: "C18",
      columnLengthMm: 50,
      columnIdMm: 2.1,
      particleSizeUm: 1.7,
      availableSolvents: ["Acetonitrile", "Methanol", "Water"],
      detectorTypes: ["MS/MS"],
    }));
    context.setSource("local_corpus");
    mutations.push(
      { field: "target.requestText", value: "Metformin plasma demo request" },
      { field: "target.analyteName", value: "Metformin" },
      { field: "source", value: "local_corpus" },
      { field: "systemSpecs", value: "Waters BEH C18 / MS-friendly demo hardware" },
    );
    return {
      content: "Loaded a realistic demo draft into the integrated studio shell.",
      mutations,
    };
  }

  const analyte = extractAnalyte(prompt);
  const matrix = extractMatrix(prompt);
  const customMatrix = extractCustomMatrix(prompt);
  const runtime = extractRuntime(prompt);
  const requiresMs = /\bms\b|mass spec|ms-friendly|ms friendly/i.test(lower);
  const wantsOpenAccess = /open access|literature/i.test(lower);
  const wantsCorpus = /local corpus|review-backed|corpus/i.test(lower);

  if (
    /design|draft|fill|set up|populate|use this|screen|build/i.test(lower) ||
    analyte ||
    matrix ||
    runtime ||
    requiresMs
  ) {
    context.setTarget((current) => ({
      ...current,
      requestText: prompt,
      analyteName: analyte ?? current.analyteName,
      matrix: matrix ?? current.matrix,
      customMatrix: customMatrix ?? current.customMatrix,
      requireMS: requiresMs || current.requireMS,
      maxRunTimeMin: runtime ?? current.maxRunTimeMin,
    }));

    if (wantsOpenAccess) {
      context.setSource("open_access");
      mutations.push({ field: "source", value: "open_access" });
    } else if (wantsCorpus) {
      context.setSource("local_corpus");
      mutations.push({ field: "source", value: "local_corpus" });
    }

    if (analyte) {
      mutations.push({ field: "target.analyteName", value: analyte });
    }
    if (matrix) {
      mutations.push({
        field: "target.matrix",
        value: customMatrix ? `${matrix} (${customMatrix})` : matrix,
      });
    }
    if (runtime != null) {
      mutations.push({ field: "target.maxRunTimeMin", value: `${runtime}` });
    }
    if (requiresMs) {
      mutations.push({ field: "target.requireMS", value: "true" });
      context.setSystemSpecs((current) => ({
        ...current,
        detectorTypes: current.detectorTypes.includes("MS/MS") ? current.detectorTypes : ["MS/MS", ...current.detectorTypes].slice(0, 3),
        availableSolvents: current.availableSolvents.length
          ? Array.from(new Set([...current.availableSolvents, "Water", "Acetonitrile"]))
          : ["Water", "Acetonitrile"],
      }));
      mutations.push({ field: "systemSpecs.detectorTypes", value: "MS/MS" });
    }

    mutations.push({ field: "target.requestText", value: prompt });
    return {
      content:
        mutations.length > 0
          ? "Updated the live Silico draft from your prompt. Review the brief and run settings in the center workspace before launching discovery."
          : "I parsed the prompt but nothing new was applied to the draft.",
      mutations,
    };
  }

  if (/add impurity/i.test(lower)) {
    context.addImpurity();
    mutations.push({ field: "target.impurities", value: "Added blank secondary analyte row" });
    return {
      content: "Added a secondary analyte row to the live draft so you can fill the structure or resolve it next.",
      mutations,
    };
  }

  if (/run discovery|run this|start run|launch/i.test(lower)) {
    if (context.activeRecommendation) {
      await context.rerunDiscovery();
      return {
        content: "Triggered a rerun using the current integrated studio draft.",
        mutations,
      };
    }

    await context.runDiscovery();
    return {
      content: "Triggered discovery from the integrated studio shell.",
      mutations,
    };
  }

  return {
    content:
      "I can fill the real Silico draft, switch source mode, add secondary analytes, load a demo draft, or start discovery. Try: `Design a method for caffeine in coffee, MS-friendly, under 8 minutes`.",
    mutations,
  };
}

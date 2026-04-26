import { useWorkspace } from "@/studio/store/workspace";
import type { Brief, GradientPoint, MethodSpec, PredictedChromatogram } from "@/studio/types/hplc";

export const AGENT_TOOLS = [
  {
    type: "function",
    function: {
      name: "create_project",
      description:
        "Create a new project (a separation problem with analytes, matrix, and goal). Returns projectId.",
      parameters: {
        type: "object",
        properties: {
          name: { type: "string" },
          analytes: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                logp: { type: "number" },
                pka: { type: "string" },
                lambda_max_nm: { type: "number" },
                notes: { type: "string" },
              },
              required: ["name"],
            },
          },
          matrix: { type: "string" },
          goal: { type: "string" },
        },
        required: ["name"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "update_brief",
      description:
        "Update the project brief (analytes / matrix / goal) on the active project.",
      parameters: {
        type: "object",
        properties: {
          analytes: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                logp: { type: "number" },
                pka: { type: "string" },
                lambda_max_nm: { type: "number" },
                notes: { type: "string" },
              },
              required: ["name"],
            },
          },
          matrix: { type: "string" },
          goal: { type: "string" },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_method",
      description: "Create a full HPLC method on the active project.",
      parameters: {
        type: "object",
        properties: {
          mode: { type: "string" },
          column: {
            type: "object",
            properties: { choice: { type: "string" }, reason: { type: "string" } },
            required: ["choice", "reason"],
          },
          mobile_phase: {
            type: "object",
            properties: {
              a: { type: "string" },
              b: { type: "string" },
              buffer_notes: { type: "string" },
            },
            required: ["a", "b"],
          },
          gradient: {
            type: "array",
            items: {
              type: "object",
              properties: { time_min: { type: "number" }, percent_b: { type: "number" } },
              required: ["time_min", "percent_b"],
            },
          },
          flow_rate_ml_min: { type: "number" },
          column_temperature_c: { type: "number" },
          injection_volume_ul: { type: "number" },
          run_time_min: { type: "number" },
          detection: {
            type: "object",
            properties: {
              detector: { type: "string" },
              wavelength_nm: { type: "string" },
              notes: { type: "string" },
            },
            required: ["detector", "wavelength_nm"],
          },
          sample_prep: { type: "string" },
          rationale: { type: "string" },
          warnings: { type: "array", items: { type: "string" } },
        },
        required: [
          "mode","column","mobile_phase","gradient","flow_rate_ml_min",
          "column_temperature_c","injection_volume_ul","run_time_min",
          "detection","sample_prep","rationale","warnings",
        ],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "update_method",
      description:
        "Patch any field(s) on the active method (column, mobile phase, flow, temp, detection, gradient, etc). Forks unless inplace=true.",
      parameters: {
        type: "object",
        properties: {
          inplace: { type: "boolean" },
          mode: { type: "string" },
          column: {
            type: "object",
            properties: { choice: { type: "string" }, reason: { type: "string" } },
          },
          mobile_phase: {
            type: "object",
            properties: {
              a: { type: "string" },
              b: { type: "string" },
              buffer_notes: { type: "string" },
            },
          },
          gradient: {
            type: "array",
            items: {
              type: "object",
              properties: { time_min: { type: "number" }, percent_b: { type: "number" } },
              required: ["time_min", "percent_b"],
            },
          },
          flow_rate_ml_min: { type: "number" },
          column_temperature_c: { type: "number" },
          injection_volume_ul: { type: "number" },
          run_time_min: { type: "number" },
          detection: {
            type: "object",
            properties: {
              detector: { type: "string" },
              wavelength_nm: { type: "string" },
              notes: { type: "string" },
            },
          },
          sample_prep: { type: "string" },
          rationale: { type: "string" },
          warnings: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "predict_chromatogram",
      description: "Predict a chromatogram for the active method. Creates a Run.",
      parameters: {
        type: "object",
        properties: {
          total_time_min: { type: "number" },
          peaks: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                rt_min: { type: "number" },
                height: { type: "number" },
                width_min: { type: "number" },
              },
              required: ["name", "rt_min", "height", "width_min"],
            },
          },
          notes: { type: "string" },
        },
        required: ["total_time_min", "peaks"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "set_inventory",
      description: "Replace lab hardware inventory fields. Use add_to_inventory for additive ops.",
      parameters: {
        type: "object",
        properties: {
          pump: { type: "string" },
          detector: { type: "string" },
          columns: { type: "array", items: { type: "string" } },
          solvents: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "add_to_inventory",
      description: "Add columns and/or solvents to the existing inventory without replacing it.",
      parameters: {
        type: "object",
        properties: {
          columns: { type: "array", items: { type: "string" } },
          solvents: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
];

export interface ToolCall {
  name: string;
  args: any;
}

export interface ToolResult {
  ok: boolean;
  label: string;
  result?: any;
  error?: string;
}

export function runToolCall(call: ToolCall): ToolResult {
  const ws = useWorkspace.getState();
  try {
    switch (call.name) {
      case "create_project": {
        const id = ws.createProject(call.args.name ?? "Untitled project", {
          analytes: call.args.analytes ?? [],
          matrix: call.args.matrix ?? "",
          goal: call.args.goal ?? "",
        });
        useWorkspace.setState({ lastAgentAction: `Created project · ${call.args.name}` });
        return { ok: true, label: `Created project · ${call.args.name}`, result: { projectId: id } };
      }
      case "update_brief": {
        const projectId = ws.activeProjectId;
        if (!projectId) return { ok: false, label: "update_brief failed", error: "No active project" };
        const patch: Partial<Brief> = {};
        if (call.args.analytes !== undefined) patch.analytes = call.args.analytes;
        if (call.args.matrix !== undefined) patch.matrix = call.args.matrix;
        if (call.args.goal !== undefined) patch.goal = call.args.goal;
        ws.updateBrief(projectId, patch);
        useWorkspace.setState({ lastAgentAction: "Updated brief" });
        return { ok: true, label: "Updated brief", result: { ok: true } };
      }
      case "create_method": {
        const projectId = ws.activeProjectId;
        if (!projectId) return { ok: false, label: "create_method failed", error: "No active project" };
        const spec: MethodSpec = {
          mode: call.args.mode,
          column: call.args.column,
          mobile_phase: call.args.mobile_phase,
          gradient: call.args.gradient,
          flow_rate_ml_min: call.args.flow_rate_ml_min,
          column_temperature_c: call.args.column_temperature_c,
          injection_volume_ul: call.args.injection_volume_ul,
          run_time_min: call.args.run_time_min,
          detection: call.args.detection,
          sample_prep: call.args.sample_prep,
          rationale: call.args.rationale,
          warnings: call.args.warnings ?? [],
        };
        const id = ws.createMethod(projectId, spec);
        const v = useWorkspace.getState().methods[id]?.version;
        useWorkspace.setState({ lastAgentAction: `Created Method v${v}` });
        return { ok: true, label: `Created Method v${v}`, result: { methodId: id } };
      }
      case "update_method": {
        const methodId = ws.activeProjectId ? ws.projects[ws.activeProjectId]?.activeMethodId : undefined;
        if (!methodId) return { ok: false, label: "update_method failed", error: "No active method" };
        const { inplace, ...rest } = call.args;
        const newId = ws.updateMethod(methodId, rest as Partial<MethodSpec>, !inplace);
        if (newId !== methodId) {
          const v = useWorkspace.getState().methods[newId]?.version;
          ws.setActiveMethod(useWorkspace.getState().methods[newId].projectId, newId);
          useWorkspace.setState({ lastAgentAction: `Forked → Method v${v}` });
          return { ok: true, label: `Forked → Method v${v}`, result: { methodId: newId } };
        }
        useWorkspace.setState({ lastAgentAction: "Updated method" });
        return { ok: true, label: "Updated method", result: { methodId } };
      }
      case "predict_chromatogram": {
        const methodId = ws.activeProjectId ? ws.projects[ws.activeProjectId]?.activeMethodId : undefined;
        if (!methodId) return { ok: false, label: "predict failed", error: "No active method" };
        const predicted: PredictedChromatogram = {
          total_time_min: call.args.total_time_min,
          peaks: call.args.peaks,
        };
        const runId = ws.createRun(methodId, predicted, call.args.notes);
        useWorkspace.setState({ lastAgentAction: `Predicted chromatogram (${predicted.peaks.length} peaks)` });
        return {
          ok: true,
          label: `Predicted chromatogram · ${predicted.peaks.length} peaks`,
          result: { runId },
        };
      }
      case "set_inventory": {
        const patch: any = {};
        if (call.args.pump !== undefined) patch.pump = call.args.pump;
        if (call.args.detector !== undefined) patch.detector = call.args.detector;
        if (call.args.columns !== undefined) patch.columns = call.args.columns;
        if (call.args.solvents !== undefined) patch.solvents = call.args.solvents;
        ws.setInventory(patch);
        useWorkspace.setState({ lastAgentAction: "Updated inventory" });
        return { ok: true, label: "Updated inventory", result: { ok: true } };
      }
      case "add_to_inventory": {
        const cols: string[] = call.args.columns ?? [];
        const sols: string[] = call.args.solvents ?? [];
        cols.forEach((c) => ws.addColumn(c));
        sols.forEach((s) => ws.addSolvent(s));
        const label = `Added ${cols.length ? `${cols.length} column(s)` : ""}${cols.length && sols.length ? ", " : ""}${sols.length ? `${sols.length} solvent(s)` : ""}`;
        useWorkspace.setState({ lastAgentAction: label });
        return { ok: true, label, result: { ok: true } };
      }
      default:
        return { ok: false, label: `Unknown tool ${call.name}`, error: "unknown tool" };
    }
  } catch (e) {
    return { ok: false, label: `${call.name} failed`, error: (e as Error).message };
  }
}

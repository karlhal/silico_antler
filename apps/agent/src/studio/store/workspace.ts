import { create } from "zustand";
import { persist } from "zustand/middleware";
import { nanoid } from "nanoid";
import type {
  Brief,
  ChatEvent,
  Inventory,
  Method,
  MethodSpec,
  PredictedChromatogram,
  Project,
  Run,
} from "@/studio/types/hplc";

export type SidebarView = "projects" | "hardware";

interface WorkspaceState {
  inventory: Inventory;
  projects: Record<string, Project>;
  methods: Record<string, Method>;
  runs: Record<string, Run>;

  activeProjectId?: string;
  sidebarView: SidebarView;
  copilotOpen: boolean;
  projectsOpen: boolean;
  hardwareOpen: boolean;
  lastAgentAction?: string;
  pendingPrompt?: string;

  chat: ChatEvent[];

  // setters
  setInventory: (patch: Partial<Inventory>) => void;
  addColumn: (label: string) => void;
  removeColumn: (label: string) => void;
  addSolvent: (label: string) => void;
  removeSolvent: (label: string) => void;
  setActiveProject: (id?: string) => void;
  setActiveMethod: (projectId: string, methodId: string) => void;
  setSidebarView: (v: SidebarView) => void;
  toggleCopilot: () => void;
  toggleProjects: () => void;
  setHardwareOpen: (open: boolean) => void;
  setPendingPrompt: (p?: string) => void;

  // chat
  appendChat: (e: Omit<ChatEvent, "id" | "createdAt">) => string;
  patchChat: (id: string, patch: Partial<ChatEvent>) => void;
  removeChat: (id: string) => void;

  // domain ops (also called by tool runner)
  createProject: (name: string, brief?: Partial<Brief>) => string;
  updateBrief: (projectId: string, brief: Partial<Brief>) => void;
  renameProject: (projectId: string, name: string) => void;
  createMethod: (projectId: string, spec: MethodSpec, parentId?: string) => string;
  updateMethod: (methodId: string, spec: Partial<MethodSpec>, fork?: boolean) => string;
  createRun: (methodId: string, predicted: PredictedChromatogram, notes?: string) => string;
  deleteProject: (id: string) => void;
}

const EMPTY_INVENTORY: Inventory = {
  pump: "",
  detector: "",
  columns: [],
  solvents: [],
};

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      inventory: EMPTY_INVENTORY,
      projects: {},
      methods: {},
      runs: {},
      sidebarView: "projects",
      copilotOpen: true,
      projectsOpen: true,
      hardwareOpen: false,
      chat: [],

      setInventory: (patch) =>
        set((s) => ({ inventory: { ...s.inventory, ...patch } })),

      addColumn: (label) =>
        set((s) =>
          s.inventory.columns.includes(label)
            ? {}
            : { inventory: { ...s.inventory, columns: [...s.inventory.columns, label] } }
        ),
      removeColumn: (label) =>
        set((s) => ({
          inventory: { ...s.inventory, columns: s.inventory.columns.filter((c) => c !== label) },
        })),
      addSolvent: (label) =>
        set((s) =>
          s.inventory.solvents.includes(label)
            ? {}
            : { inventory: { ...s.inventory, solvents: [...s.inventory.solvents, label] } }
        ),
      removeSolvent: (label) =>
        set((s) => ({
          inventory: { ...s.inventory, solvents: s.inventory.solvents.filter((c) => c !== label) },
        })),

      setActiveProject: (id) => set({ activeProjectId: id, sidebarView: "projects" }),

      setActiveMethod: (projectId, methodId) =>
        set((s) => {
          const p = s.projects[projectId];
          if (!p) return {};
          return {
            projects: {
              ...s.projects,
              [projectId]: { ...p, activeMethodId: methodId },
            },
            activeProjectId: projectId,
          };
        }),

      setSidebarView: (v) => set({ sidebarView: v }),
      toggleCopilot: () => set((s) => ({ copilotOpen: !s.copilotOpen })),
      toggleProjects: () => set((s) => ({ projectsOpen: !s.projectsOpen })),
      setHardwareOpen: (open) => set({ hardwareOpen: open }),
      setPendingPrompt: (p) => set({ pendingPrompt: p }),

      appendChat: (e) => {
        const id = nanoid();
        set((s) => ({
          chat: [...s.chat, { id, createdAt: Date.now(), kind: "message", ...e }],
        }));
        return id;
      },
      patchChat: (id, patch) =>
        set((s) => ({
          chat: s.chat.map((c) => (c.id === id ? { ...c, ...patch } : c)),
        })),
      removeChat: (id) =>
        set((s) => ({ chat: s.chat.filter((c) => c.id !== id) })),

      createProject: (name, brief) => {
        const id = nanoid();
        const project: Project = {
          id,
          name,
          createdAt: Date.now(),
          methodIds: [],
          brief: {
            analytes: brief?.analytes ?? [],
            matrix: brief?.matrix ?? "",
            goal: brief?.goal ?? "",
          },
        };
        set((s) => ({
          projects: { ...s.projects, [id]: project },
          activeProjectId: id,
          sidebarView: "projects",
        }));
        return id;
      },

      updateBrief: (projectId, brief) =>
        set((s) => {
          const p = s.projects[projectId];
          if (!p) return {};
          return {
            projects: {
              ...s.projects,
              [projectId]: { ...p, brief: { ...p.brief, ...brief } },
            },
          };
        }),

      renameProject: (projectId, name) =>
        set((s) => {
          const p = s.projects[projectId];
          if (!p) return {};
          return {
            projects: { ...s.projects, [projectId]: { ...p, name } },
          };
        }),

      createMethod: (projectId, spec, parentId) => {
        const id = nanoid();
        const project = get().projects[projectId];
        if (!project) return id;
        const versionsForProject = project.methodIds
          .map((mid) => get().methods[mid]?.version ?? 0)
          .reduce((a, b) => Math.max(a, b), 0);
        const version = versionsForProject + 1;
        const method: Method = {
          ...spec,
          id,
          projectId,
          version,
          parentId,
          name: `Method v${version}`,
          createdAt: Date.now(),
        };
        set((s) => ({
          methods: { ...s.methods, [id]: method },
          projects: {
            ...s.projects,
            [projectId]: {
              ...s.projects[projectId],
              methodIds: [...s.projects[projectId].methodIds, id],
              activeMethodId: id,
            },
          },
          activeProjectId: projectId,
        }));
        return id;
      },

      updateMethod: (methodId, spec, fork) => {
        const existing = get().methods[methodId];
        if (!existing) return methodId;
        if (fork) {
          return get().createMethod(
            existing.projectId,
            { ...existing, ...spec } as MethodSpec,
            existing.id
          );
        }
        set((s) => ({
          methods: {
            ...s.methods,
            [methodId]: { ...existing, ...spec },
          },
        }));
        return methodId;
      },

      createRun: (methodId, predicted, notes) => {
        const id = nanoid();
        const m = get().methods[methodId];
        if (!m) return id;
        const run: Run = {
          id,
          methodId,
          projectId: m.projectId,
          predicted,
          notes,
          createdAt: Date.now(),
        };
        set((s) => ({ runs: { ...s.runs, [id]: run } }));
        return id;
      },

      deleteProject: (id) =>
        set((s) => {
          const { [id]: _, ...projects } = s.projects;
          const methods = { ...s.methods };
          const runs = { ...s.runs };
          Object.values(s.methods).forEach((m) => {
            if (m.projectId === id) delete methods[m.id];
          });
          Object.values(s.runs).forEach((r) => {
            if (r.projectId === id) delete runs[r.id];
          });
          return {
            projects,
            methods,
            runs,
            activeProjectId:
              s.activeProjectId === id ? undefined : s.activeProjectId,
          };
        }),
    }),
    {
      name: "chroma.workspace.v1",
      partialize: (s) => ({
        inventory: s.inventory,
        projects: s.projects,
        methods: s.methods,
        runs: s.runs,
        activeProjectId: s.activeProjectId,
        chat: s.chat,
      }),
    }
  )
);

// Build a compact snapshot the agent uses for grounding.
export function buildAgentSnapshot() {
  const s = useWorkspace.getState();
  const activeProject = s.activeProjectId ? s.projects[s.activeProjectId] : undefined;
  const activeMethod =
    activeProject?.activeMethodId ? s.methods[activeProject.activeMethodId] : undefined;
  return {
    inventory: s.inventory,
    activeProject: activeProject
      ? {
          id: activeProject.id,
          name: activeProject.name,
          brief: activeProject.brief,
          methodIds: activeProject.methodIds,
        }
      : null,
    activeMethod: activeMethod ?? null,
    projects: Object.values(s.projects).map((p) => ({
      id: p.id,
      name: p.name,
      methodCount: p.methodIds.length,
    })),
  };
}

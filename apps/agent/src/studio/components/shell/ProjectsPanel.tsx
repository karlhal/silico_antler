import { useWorkspace } from "@/studio/store/workspace";
import { Button } from "@/studio/components/ui/button";
import { TestTube, Trash, FolderPlus, Atom } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export const ProjectsPanel = () => {
  const projects = useWorkspace((s) => s.projects);
  const methods = useWorkspace((s) => s.methods);
  const activeProjectId = useWorkspace((s) => s.activeProjectId);
  const setActiveProject = useWorkspace((s) => s.setActiveProject);
  const setActiveMethod = useWorkspace((s) => s.setActiveMethod);
  const createProject = useWorkspace((s) => s.createProject);
  const deleteProject = useWorkspace((s) => s.deleteProject);
  const inventory = useWorkspace((s) => s.inventory);
  const setHardwareOpen = useWorkspace((s) => s.setHardwareOpen);

  const projectList = Object.values(projects).sort((a, b) => b.createdAt - a.createdAt);
  const inventoryCount =
    inventory.columns.length + inventory.solvents.length + (inventory.pump ? 1 : 0) + (inventory.detector ? 1 : 0);

  return (
    <div className="h-full flex flex-col text-[13px]">
      <div className="px-3 h-12 shrink-0 flex items-center justify-between border-b border-sidebar-border">
        <span className="section-label">Projects</span>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0 rounded hover:bg-sidebar-accent"
          onClick={() => createProject(`Project ${projectList.length + 1}`)}
          aria-label="New project"
        >
          <FolderPlus className="size-3.5" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        {projectList.length === 0 && (
          <div className="px-3 py-6 text-[12px] text-muted-foreground text-center leading-relaxed">
            No projects yet.
            <br />
            Ask the copilot or click <FolderPlus className="size-3 inline -mt-0.5" />.
          </div>
        )}
        <div className="space-y-0.5">
          {projectList.map((p) => {
            const active = p.id === activeProjectId;
            const ms = p.methodIds.map((mid) => methods[mid]).filter(Boolean);
            return (
              <div key={p.id}>
                <button
                  onClick={() => setActiveProject(p.id)}
                  className={cn(
                    "w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-md group hover:bg-sidebar-accent transition-colors",
                    active && "bg-sidebar-accent text-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full shrink-0",
                      active ? "bg-clay" : "bg-muted-foreground/30"
                    )}
                  />
                  <span className="truncate flex-1 text-[13px]">{p.name}</span>
                  <Trash
                    className="size-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Delete ${p.name}?`)) deleteProject(p.id);
                    }}
                  />
                </button>
                {active && ms.length > 0 && (
                  <div className="ml-3.5 border-l border-sidebar-border pl-2 mt-0.5 mb-1 space-y-0.5">
                    {ms
                      .sort((a, b) => b.version - a.version)
                      .map((m) => {
                        const isActiveMethod = p.activeMethodId === m.id;
                        return (
                          <button
                            key={m.id}
                            onClick={() => setActiveMethod(p.id, m.id)}
                            className={cn(
                              "w-full text-left flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-sidebar-accent text-[12px] font-mono transition-colors",
                              isActiveMethod ? "text-foreground bg-sidebar-accent/60" : "text-muted-foreground"
                            )}
                          >
                            <TestTube className="size-3" />
                            {m.name}
                          </button>
                        );
                      })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Hardware switcher at bottom */}
      <button
        onClick={() => setHardwareOpen(true)}
        className="shrink-0 border-t border-sidebar-border px-3 py-2.5 flex items-center gap-2 hover:bg-sidebar-accent text-left transition-colors"
      >
        <Atom className="size-3.5 text-muted-foreground" />
        <span className="text-[12.5px] flex-1">Hardware & solvents</span>
        <span className="text-[11px] text-muted-foreground font-mono tnum">{inventoryCount}</span>
      </button>
    </div>
  );
};

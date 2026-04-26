import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/studio/components/ui/command";
import { useWorkspace } from "@/studio/store/workspace";
import { FolderOpen, Plus, TestTube, SidebarSimple, Atom } from "@phosphor-icons/react";

export const CommandPalette = ({ open, onOpenChange }: { open: boolean; onOpenChange: (b: boolean) => void }) => {
  const projects = useWorkspace((s) => s.projects);
  const methods = useWorkspace((s) => s.methods);
  const setActiveProject = useWorkspace((s) => s.setActiveProject);
  const setActiveMethod = useWorkspace((s) => s.setActiveMethod);
  const setHardwareOpen = useWorkspace((s) => s.setHardwareOpen);
  const createProject = useWorkspace((s) => s.createProject);
  const toggleCopilot = useWorkspace((s) => s.toggleCopilot);

  const close = () => onOpenChange(false);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="MagnifyingGlass projects, methods, or actions…" />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        <CommandGroup heading="Actions">
          <CommandItem
            onSelect={() => {
              const id = createProject(`Project ${Object.keys(projects).length + 1}`);
              setActiveProject(id);
              close();
            }}
          >
            <Plus className="size-4 mr-2" /> New project
          </CommandItem>
          <CommandItem onSelect={() => { setHardwareOpen(true); close(); }}>
            <Atom className="size-4 mr-2" /> Open hardware & solvents
          </CommandItem>
          <CommandItem onSelect={() => { toggleCopilot(); close(); }}>
            <SidebarSimple className="size-4 mr-2" /> Toggle copilot panel
          </CommandItem>
        </CommandGroup>
        {Object.values(projects).length > 0 && (
          <CommandGroup heading="Projects">
            {Object.values(projects).map((p) => (
              <CommandItem key={p.id} onSelect={() => { setActiveProject(p.id); close(); }}>
                <FolderOpen className="size-4 mr-2" /> {p.name}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {Object.values(methods).length > 0 && (
          <CommandGroup heading="Methods">
            {Object.values(methods).map((m) => {
              const p = projects[m.projectId];
              return (
                <CommandItem
                  key={m.id}
                  onSelect={() => {
                    setActiveMethod(m.projectId, m.id);
                    close();
                  }}
                >
                  <TestTube className="size-4 mr-2" />
                  <span className="font-mono">{m.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{p?.name}</span>
                </CommandItem>
              );
            })}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
};

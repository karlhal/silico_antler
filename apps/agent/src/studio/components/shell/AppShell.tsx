import { useEffect, useState } from "react";
import { Sidebar } from "./Sidebar";
import { Workbench } from "./Workbench";
import { CopilotPanel } from "./CopilotPanel";
import { Breadcrumb } from "./Breadcrumb";
import { CommandPalette } from "./CommandPalette";
import { Button } from "@/studio/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/studio/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/studio/components/ui/alert-dialog";
import {
  SignOut,
  ArrowLeft,
  Sparkle,
  SidebarSimple,
  MagnifyingGlass,
  User as UserIcon,
  Moon,
  Sun,
} from "@phosphor-icons/react";
import { useWorkspace } from "@/studio/store/workspace";
import { useAuth } from "@/studio/hooks/useAuth";
import { useTheme } from "@/studio/hooks/useTheme";
import { useResizableWidth } from "@/studio/hooks/useResizableWidth";
import { navigateAgentAppRoute } from "@/lib/appNavigation";
import { isLegacyStudioEnabled } from "@/lib/agentRuntime";

export const AppShell = () => {
  const legacyStudioEnabled = isLegacyStudioEnabled();
  const copilotOpen = useWorkspace((s) => s.copilotOpen);
  const toggleCopilot = useWorkspace((s) => s.toggleCopilot);
  const projectsOpen = useWorkspace((s) => s.projectsOpen);
  const toggleProjects = useWorkspace((s) => s.toggleProjects);
  const lastAgentAction = useWorkspace((s) => s.lastAgentAction);
  const activeProjectId = useWorkspace((s) => s.activeProjectId);
  const projects = useWorkspace((s) => s.projects);
  const methods = useWorkspace((s) => s.methods);
  const createProject = useWorkspace((s) => s.createProject);
  const setActiveProject = useWorkspace((s) => s.setActiveProject);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const { user, signOut } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();
  const projectsCol = useResizableWidth({
    storageKey: "chroma-projects-w",
    defaultWidth: 240,
    min: 200,
    max: 380,
    side: "left",
  });
  const copilotCol = useResizableWidth({
    storageKey: "chroma-copilot-w",
    defaultWidth: 380,
    min: 300,
    max: 560,
    side: "right",
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // First-run: auto-create a starter project so the workbench isn't empty.
  useEffect(() => {
    if (!user) return;
    if (Object.keys(projects).length > 0) return;
    const id = createProject("Getting started", {
      goal: "Tell the copilot what you want to separate. Try: 'caffeine in coffee on a C18, MS-friendly'.",
      matrix: "",
      analytes: [],
    });
    setActiveProject(id);
  }, [user, projects, createProject, setActiveProject]);

  const initials = (user?.email ?? "?").slice(0, 2).toUpperCase();

  const activeProject = activeProjectId ? projects[activeProjectId] : undefined;
  const activeMethod = activeProject?.activeMethodId ? methods[activeProject.activeMethodId] : undefined;

  return (
    <div className="h-screen flex flex-col bg-surface-2 text-foreground">
      {/* Top bar */}
      <header className="h-12 shrink-0 flex items-center px-4 gap-3 border-b border-border bg-background">
        <div className="flex items-center gap-2">
          <div className="size-6 rounded bg-primary text-primary-foreground grid place-items-center font-display text-[12px] leading-none">
            S
          </div>
          <span className="font-display text-[15px] tracking-tight">Silico</span>
          <span className="text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground ml-1">Imported Studio</span>
        </div>
        <div className="h-4 w-px bg-border" />
        <Breadcrumb project={activeProject} method={activeMethod} />
        <div className="ml-auto flex items-center gap-1.5">
          {legacyStudioEnabled ? (
            <Button
              variant="outline"
              size="sm"
              className="hidden h-7 rounded md:inline-flex text-[11px]"
              onClick={() => navigateAgentAppRoute("/studio")}
            >
              <Sparkle className="mr-1.5 size-3.5" />
              Integrated
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            className="hidden h-7 rounded md:inline-flex text-[11px]"
            onClick={() => navigateAgentAppRoute("/")}
          >
            <ArrowLeft className="mr-1.5 size-3.5" />
            Workflow
          </Button>
          <button
            onClick={() => setPaletteOpen(true)}
            className="h-7 pl-2 pr-1.5 inline-flex items-center gap-2 rounded border border-border bg-surface hover:bg-surface-2 text-[12px] text-muted-foreground transition-colors"
          >
            <MagnifyingGlass className="size-3.5" />
            <span>Search</span>
            <span className="kbd ml-2">⌘K</span>
          </button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 rounded"
            onClick={toggleProjects}
            aria-label={projectsOpen ? "Hide projects" : "Show projects"}
            title={projectsOpen ? "Hide projects" : "Show projects"}
          >
            <SidebarSimple className={`size-4 ${projectsOpen ? "" : "opacity-50"}`} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 rounded"
            onClick={toggleCopilot}
            aria-label={copilotOpen ? "Hide copilot" : "Show copilot"}
            title={copilotOpen ? "Hide copilot" : "Show copilot"}
          >
            <SidebarSimple className={`size-4 scale-x-[-1] ${copilotOpen ? "" : "opacity-50"}`} />
          </Button>
          {user && (
            <>
              <div className="h-4 w-px bg-border mx-0.5" />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="size-7 rounded-full bg-surface-2 border border-border hover:border-border-strong text-[10.5px] font-medium text-foreground/80 grid place-items-center transition-colors"
                    aria-label="Account menu"
                    title={user.email ?? "Account"}
                  >
                    {initials}
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex items-center gap-2">
                      <UserIcon className="size-3.5 text-muted-foreground" />
                      <span className="text-[12px] truncate" title={user.email ?? ""}>
                        {user.email}
                      </span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.preventDefault();
                      toggleTheme();
                    }}
                    className="text-[12.5px] gap-2 justify-between"
                  >
                    <span className="flex items-center gap-2">
                      {theme === "dark" ? <Moon className="size-3.5" /> : <Sun className="size-3.5" />}
                      Appearance
                    </span>
                    <span className="text-[11px] text-muted-foreground capitalize">{theme}</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => setSignOutOpen(true)}
                    className="text-[12.5px] gap-2 text-destructive focus:text-destructive"
                  >
                    <SignOut className="size-3.5" /> Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </header>

      <AlertDialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out?</AlertDialogTitle>
            <AlertDialogDescription>
              Your projects and methods stay saved. You can sign back in any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => signOut()}>
              Sign out
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Main area: 3-column layout, side panels claim their own column */}
      <div className="flex-1 min-h-0 flex bg-surface-2">
        {/* Left column — Projects */}
        {projectsOpen && (
          <aside
            className="shrink-0 border-r border-border bg-surface flex flex-col relative"
            style={{ width: projectsCol.width }}
          >
            <div className="flex-1 min-h-0 overflow-hidden">
              <Sidebar />
            </div>
            <div
              onMouseDown={projectsCol.onMouseDown}
              onDoubleClick={projectsCol.reset}
              className="absolute top-0 bottom-0 -right-1 w-2 z-10 cursor-col-resize group"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize projects panel"
              title="Drag to resize · double-click to reset"
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-transparent group-hover:bg-border-strong transition-colors" />
            </div>
          </aside>
        )}

        {/* Center — canvas workbench */}
        <div className="flex-1 min-w-0 relative">
          <Workbench />
        </div>

        {/* Right column — Copilot */}
        {copilotOpen && (
          <aside
            className="shrink-0 border-l border-border bg-surface flex flex-col relative"
            style={{ width: copilotCol.width }}
          >
            <div
              onMouseDown={copilotCol.onMouseDown}
              onDoubleClick={copilotCol.reset}
              className="absolute top-0 bottom-0 -left-1 w-2 z-10 cursor-col-resize group"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize copilot panel"
              title="Drag to resize · double-click to reset"
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-transparent group-hover:bg-border-strong transition-colors" />
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <CopilotPanel />
            </div>
          </aside>
        )}
      </div>

      {/* Status line */}
      <footer className="h-6 shrink-0 border-t border-border bg-background px-4 flex items-center text-[11px] text-muted-foreground gap-3">
        <span className="font-mono tnum">
          {activeProject ? activeProject.name : "no project"}
          {activeMethod ? ` · ${activeMethod.name}` : ""}
        </span>
        <div className="ml-auto truncate">
          {lastAgentAction ? <span>↳ {lastAgentAction}</span> : <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-success" /> ready</span>}
        </div>
      </footer>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
};

import { useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  MagnifyingGlass,
  User as UserIcon,
  ArrowLeft,
  Moon,
  Sun,
  SignOut,
  SidebarSimple,
  Sparkle,
  ArrowUp,
  CircleNotch,
  Wrench,
  CaretRight,
  Play,
  ArrowClockwise,
  Cpu,
  FileText,
} from "@phosphor-icons/react";

import { useAgentWorkflow } from "@/hooks/useAgentWorkflow";
import { downloadAnalysisExport } from "@/lib/analysisExport";
import type { AgentRuntimeBootState } from "@/lib/agentRuntime";
import type {
  AgentResultOrigin,
  AgentRuntimeMode,
  ClarificationQuestion,
  DiscoverySource,
  DiscoveryTarget,
  Recommendation,
  RecommendationReportMeta,
  SystemSpecs,
} from "@/types";
import { cn } from "@/lib/utils";
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
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/studio/components/ui/command";
import { Badge } from "@/studio/components/ui/badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/studio/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/studio/components/ui/collapsible";
import { Input } from "@/studio/components/ui/input";
import { Separator } from "@/studio/components/ui/separator";
import { useAuth } from "@/studio/hooks/useAuth";
import { useResizableWidth } from "@/studio/hooks/useResizableWidth";
import { useTheme } from "@/studio/hooks/useTheme";
import {
  runIntegratedCopilotPrompt,
  type CopilotMutation,
} from "@/studio/lib/integratedCopilot";
import { navigateAgentAppRoute } from "@/lib/appNavigation";
import { isLegacyStudioEnabled } from "@/lib/agentRuntime";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  pending?: boolean;
  mutations?: CopilotMutation[];
  artifact?: "thinking" | "clarification";
}

type WorkspaceTab = "draft" | "hardware" | "reports";

function createChatId() {
  return `studio-chat-${Math.random().toString(36).slice(2, 10)}`;
}

function formatSourceLabel(value: DiscoverySource) {
  return value === "local_corpus" ? "Local corpus" : "Open access";
}

function formatRuntimeMode(value: AgentRuntimeMode | null) {
  if (!value) return "Draft";
  if (value === "demo_safe") return "Demo-safe";
  return value === "cached" ? "Cached" : "Live";
}

function formatResultOrigin(value: AgentResultOrigin | null) {
  if (!value) return "No report";
  return value.replace(/_/g, " ");
}

function formatRuntimeSummary(target: DiscoveryTarget) {
  const matrix =
    target.matrix === "Other"
      ? target.customMatrix || "Other matrix"
      : target.matrix;
  return [
    target.analyteName || "No analyte set",
    matrix || "No matrix",
    target.maxRunTimeMin ? `${target.maxRunTimeMin} min cap` : "No runtime cap",
    target.requireMS ? "MS required" : "Detector flexible",
  ].join(" · ");
}

function formatSystemSummary(systemSpecs: SystemSpecs) {
  const column = [
    systemSpecs.columnManufacturer,
    systemSpecs.columnName || systemSpecs.columnChemistry,
  ]
    .filter(Boolean)
    .join(" ");
  const solvents =
    systemSpecs.availableSolvents.slice(0, 3).join(", ") || "No solvents";
  const detectors = systemSpecs.detectorTypes.join(", ") || "No detector";
  return `${column || "No column"} · ${solvents} · ${detectors}`;
}

function extractRecommendationTitle(
  activeRecommendation: Recommendation | null,
) {
  if (!activeRecommendation) {
    return "No recommendation yet";
  }

  const method = activeRecommendation.recommended_method;
  return [
    activeRecommendation.title,
    method?.run_time_min ? `${method.run_time_min.toFixed(1)} min` : null,
    activeRecommendation.trust.trust_state.replace(/_/g, " "),
  ]
    .filter(Boolean)
    .join(" · ");
}

function StudioBadge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "accent" | "blue";
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "h-6 rounded-full px-2.5 text-[11px] font-medium",
        tone === "default" && "bg-background/92 text-muted-foreground",
        tone === "accent" && "border-clay/20 bg-clay/10 text-foreground",
        tone === "blue" &&
          "border-[color:var(--color-silico-blue)]/20 bg-[color:var(--color-silico-blue)]/10 text-foreground",
      )}
    >
      {children}
    </Badge>
  );
}

export function IntegratedStudioShell({
  runtimeBootState,
}: {
  runtimeBootState: AgentRuntimeBootState;
}) {
  const legacyStudioEnabled = isLegacyStudioEnabled();
  const workflow = useAgentWorkflow({
    runtimeConfig: runtimeBootState.runtimeConfig,
    startupHealth: runtimeBootState.startupHealth,
  });
  const { user, signOut } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("draft");
  const [leftRailOpen, setLeftRailOpen] = useState(true);
  const [rightRailOpen, setRightRailOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const chatTextAreaRef = useRef<HTMLTextAreaElement>(null);
  const thinkingArtifactRef = useRef(false);
  const clarificationArtifactRef = useRef<string | null>(null);
  const leftCol = useResizableWidth({
    storageKey: "silico-studio-left-w",
    defaultWidth: 188,
    min: 156,
    max: 280,
    side: "left",
  });
  const rightCol = useResizableWidth({
    storageKey: "silico-studio-right-w",
    defaultWidth: 390,
    min: 320,
    max: 580,
    side: "right",
  });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    chatScrollRef.current?.scrollTo({
      top: chatScrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [
    chat,
    workflow.pendingClarification,
    workflow.steps,
    workflow.activeRecommendation,
    workflow.reportMeta?.runtime?.summary,
  ]);

  useEffect(() => {
    const element = chatTextAreaRef.current;
    if (!element) return;
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [chatInput]);

  useEffect(() => {
    if (workflow.activeRecommendation && workspaceTab === "draft") {
      setWorkspaceTab("reports");
    }
  }, [workflow.activeRecommendation, workspaceTab]);

  useEffect(() => {
    const hasActiveSteps = workflow.steps.some(
      (step) => step.status !== "pending",
    );
    if (!hasActiveSteps) {
      thinkingArtifactRef.current = false;
      return;
    }

    if (thinkingArtifactRef.current) {
      return;
    }

    thinkingArtifactRef.current = true;
    setChat((current) => [
      ...current,
      {
        id: createChatId(),
        role: "assistant",
        content: "",
        artifact: "thinking",
      },
    ]);
  }, [workflow.steps]);

  useEffect(() => {
    const clarification = workflow.pendingClarification;
    if (!clarification?.length) {
      clarificationArtifactRef.current = null;
      return;
    }

    const key = clarification.map((question) => question.id).join("|");
    if (clarificationArtifactRef.current === key) {
      return;
    }

    clarificationArtifactRef.current = key;
    setChat((current) => [
      ...current,
      {
        id: createChatId(),
        role: "assistant",
        content: "",
        artifact: "clarification",
      },
    ]);
  }, [workflow.pendingClarification]);

  const sendCopilotPrompt = async (prompt: string) => {
    if (!prompt.trim() || chatLoading) {
      return;
    }

    const userEntry: ChatMessage = {
      id: createChatId(),
      role: "user",
      content: prompt,
    };
    const pendingId = createChatId();

    setChat((current) => [
      ...current,
      userEntry,
      { id: pendingId, role: "assistant", content: "", pending: true },
    ]);
    setChatInput("");
    setChatLoading(true);

    try {
      const reply = await runIntegratedCopilotPrompt(prompt, {
        target: workflow.target,
        systemSpecs: workflow.systemSpecs,
        source: workflow.source,
        runtimeMode: workflow.runtimeMode,
        resultOrigin: workflow.resultOrigin,
        reportMeta: workflow.reportMeta,
        activeRecommendation: workflow.activeRecommendation,
        steps: workflow.steps,
        pendingClarification: workflow.pendingClarification,
        setTarget: workflow.setTarget,
        setSystemSpecs: workflow.setSystemSpecs,
        setSource: workflow.setSource,
        addImpurity: workflow.addImpurity,
        runDiscovery: workflow.runDiscovery,
        rerunDiscovery: workflow.rerunDiscovery,
      });

      setChat((current) =>
        current.map((entry) =>
          entry.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: reply.content,
                mutations: reply.mutations,
              }
            : entry,
        ),
      );
    } catch (error) {
      setChat((current) =>
        current.map((entry) =>
          entry.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content:
                  error instanceof Error && error.message
                    ? error.message
                    : "Apriori hit an unexpected error.",
              }
            : entry,
        ),
      );
    } finally {
      setChatLoading(false);
    }
  };

  const submitClarificationsFromPanel = async (
    answers: Record<string, string>,
  ) => {
    const answerSummary = Object.values(answers)
      .map((value) => value.trim())
      .filter(Boolean)
      .join(" · ");

    setChat((current) => [
      ...current,
      {
        id: createChatId(),
        role: "tool",
        content: answerSummary
          ? `Submitted clarification: ${answerSummary}`
          : "Submitted clarification answers",
      },
    ]);

    await workflow.submitClarification(answers);
  };

  const dismissClarificationsFromPanel = async () => {
    setChat((current) => [
      ...current,
      {
        id: createChatId(),
        role: "tool",
        content: "Continued without clarification answers",
      },
    ]);

    await workflow.dismissClarification();
  };

  const commandItems = useMemo(
    () => [
      {
        label: "Run discovery",
        action: () => void workflow.runDiscovery(),
      },
      {
        label: "Rerun discovery",
        action: () => void workflow.rerunDiscovery(),
      },
      {
        label: "Start new run",
        action: () => setResetOpen(true),
      },
    ],
    [workflow],
  );

  return (
    <div className="studio-shell h-screen flex flex-col text-foreground">
      <header className="h-12 shrink-0 flex items-center px-4 gap-3 border-b border-transparent bg-background/90 backdrop-blur">
        <div className="flex items-center gap-2">
          <div className="size-6 rounded-sm bg-primary text-primary-foreground grid place-items-center font-display text-[12px] leading-none shadow-sm">
            A
          </div>
          <span className="font-display text-[15px] tracking-tight">
            Apriori
          </span>
        </div>
        <Separator orientation="vertical" className="h-4 bg-border/80" />
        <div className="text-[12.5px] text-muted-foreground truncate">
          {workflow.target.requestText || "Ready for a new method request"}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="hidden h-7 rounded md:inline-flex text-[11px]"
            onClick={() => setResetOpen(true)}
          >
            New run
          </Button>
          {legacyStudioEnabled ? (
            <Button
              variant="outline"
              size="sm"
              className="hidden h-7 rounded md:inline-flex text-[11px]"
              onClick={() => navigateAgentAppRoute("/studio/classic")}
            >
              <Sparkle className="mr-1.5 size-3.5" />
              Classic
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
            onClick={() => setLeftRailOpen((current) => !current)}
            aria-label={leftRailOpen ? "Hide left rail" : "Show left rail"}
            title={leftRailOpen ? "Hide left rail" : "Show left rail"}
          >
            <SidebarSimple
              className={`size-4 ${leftRailOpen ? "" : "opacity-50"}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 rounded"
            onClick={() => setRightRailOpen((current) => !current)}
            aria-label={
              rightRailOpen ? "Hide Apriori panel" : "Show Apriori panel"
            }
            title={rightRailOpen ? "Hide Apriori panel" : "Show Apriori panel"}
          >
            <SidebarSimple
              className={`size-4 scale-x-[-1] ${rightRailOpen ? "" : "opacity-50"}`}
            />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="size-7 rounded-full bg-surface-2 border border-border hover:border-border-strong text-[10.5px] font-medium text-foreground/80 grid place-items-center transition-colors"
                aria-label="Account menu"
                title={user?.email ?? "Account"}
              >
                {(user?.email ?? "?").slice(0, 2).toUpperCase()}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex items-center gap-2">
                  <UserIcon className="size-3.5 text-muted-foreground" />
                  <span className="text-[12px] truncate">{user?.email}</span>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={(event) => {
                  event.preventDefault();
                  toggleTheme();
                }}
                className="text-[12.5px] gap-2 justify-between"
              >
                <span className="flex items-center gap-2">
                  {theme === "dark" ? (
                    <Moon className="size-3.5" />
                  ) : (
                    <Sun className="size-3.5" />
                  )}
                  Appearance
                </span>
                <span className="text-[11px] text-muted-foreground capitalize">
                  {theme}
                </span>
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
        </div>
      </header>

      <AlertDialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out?</AlertDialogTitle>
            <AlertDialogDescription>
              This only signs you out of the integrated studio preview.
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

      <AlertDialog open={resetOpen} onOpenChange={setResetOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Start a new run?</AlertDialogTitle>
            <AlertDialogDescription>
              This clears the current request, reports, and clarification state
              so you can enter a fresh method brief.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                workflow.resetSession();
                setChat([]);
                setChatInput("");
                setWorkspaceTab("draft");
              }}
            >
              Start new run
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="flex-1 min-h-0 flex">
        {leftRailOpen ? (
          <aside
            className="studio-panel shrink-0 rounded-r-xl rounded-l-none bg-sidebar-background/92 backdrop-blur flex flex-col relative my-3 ml-0"
            style={{ width: leftCol.width }}
          >
            <IntegratedSidebar
              historyOpen={historyOpen}
              setHistoryOpen={setHistoryOpen}
              recentRuns={workflow.recentRuns}
              activeRunRequestHash={workflow.activeRunRequestHash}
              onLoadRecentRun={workflow.loadRecentRun}
              onOpenHardware={() => setWorkspaceTab("hardware")}
            />
            <div
              onMouseDown={leftCol.onMouseDown}
              onDoubleClick={leftCol.reset}
              className="absolute top-0 bottom-0 -right-1 w-2 z-10 cursor-col-resize group"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize left panel"
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-transparent group-hover:bg-border-strong transition-colors" />
            </div>
          </aside>
        ) : null}

        <div className="flex-1 min-w-0 relative">
          <IntegratedWorkbench
            workspaceTab={workspaceTab}
            setWorkspaceTab={setWorkspaceTab}
            target={workflow.target}
            systemSpecs={workflow.systemSpecs}
            setSystemSpecs={workflow.setSystemSpecs}
            source={workflow.source}
            recommendations={workflow.recommendations}
            activeRecommendation={workflow.activeRecommendation}
            setActiveRecommendationId={workflow.setActiveRecommendationId}
            runtimeMode={workflow.runtimeMode}
            resultOrigin={workflow.resultOrigin}
            reportMeta={workflow.reportMeta}
            runtimeSummary={workflow.reportMeta?.runtime?.summary || null}
          />
        </div>

        {rightRailOpen ? (
          <aside
            className="studio-panel shrink-0 rounded-l-xl rounded-r-none bg-sidebar-background/92 backdrop-blur flex flex-col relative my-3 mr-0"
            style={{ width: rightCol.width }}
          >
            <div
              onMouseDown={rightCol.onMouseDown}
              onDoubleClick={rightCol.reset}
              className="absolute top-0 bottom-0 -left-1 w-2 z-10 cursor-col-resize group"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize right panel"
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-transparent group-hover:bg-border-strong transition-colors" />
            </div>
            <IntegratedCopilotPanel
              chat={chat}
              input={chatInput}
              setInput={setChatInput}
              loading={chatLoading}
              onSend={(prompt) => void sendCopilotPrompt(prompt)}
              scrollRef={chatScrollRef}
              textAreaRef={chatTextAreaRef}
              target={workflow.target}
              systemSpecs={workflow.systemSpecs}
              source={workflow.source}
              setSource={workflow.setSource}
              runtimeMode={workflow.runtimeMode}
              resultOrigin={workflow.resultOrigin}
              reportMeta={workflow.reportMeta}
              steps={workflow.steps}
              activeRecommendation={workflow.activeRecommendation}
              pendingClarification={workflow.pendingClarification}
              clarificationSubmit={submitClarificationsFromPanel}
              clarificationDismiss={dismissClarificationsFromPanel}
              workspaceTab={workspaceTab}
              onOpenReports={() => setWorkspaceTab("reports")}
            />
          </aside>
        ) : null}
      </div>

      <footer className="h-6 shrink-0 border-t border-border/80 bg-background/90 px-4 flex items-center text-[11px] text-muted-foreground gap-3 backdrop-blur">
        <span className="font-mono">
          {formatRuntimeMode(workflow.runtimeMode)} ·{" "}
          {formatSourceLabel(workflow.source)}
        </span>
        <div className="ml-auto truncate">
          {workflow.activeRecommendation
            ? extractRecommendationTitle(workflow.activeRecommendation)
            : "ready"}
        </div>
      </footer>

      <IntegratedCommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        actions={[
          ...commandItems,
          {
            label: "Open draft tab",
            action: () => setWorkspaceTab("draft"),
          },
          {
            label: "Open hardware tab",
            action: () => setWorkspaceTab("hardware"),
          },
          {
            label: "Open reports tab",
            action: () => setWorkspaceTab("reports"),
          },
          ...(legacyStudioEnabled
            ? [
                {
                  label: "Open classic shell",
                  action: () => navigateAgentAppRoute("/studio/classic"),
                },
              ]
            : []),
        ]}
        recentRuns={workflow.recentRuns}
        onLoadRecentRun={workflow.loadRecentRun}
      />
    </div>
  );
}

function IntegratedSidebar(props: {
  historyOpen: boolean;
  setHistoryOpen: (open: boolean) => void;
  recentRuns: Array<{
    requestHash: string;
    createdAtLabel: string;
    title: string;
    subtitle: string;
    candidateCount: number;
  }>;
  activeRunRequestHash: string | null;
  onLoadRecentRun: (requestHash: string) => void;
  onOpenHardware: () => void;
}) {
  return (
    <div className="h-full flex flex-col text-[13px]">
      <div
        className={cn(
          "px-2 py-2",
          props.historyOpen
            ? "shrink-0"
            : "flex-1 flex flex-col justify-center",
        )}
      >
        <div className="space-y-1.5">
          <Button
            type="button"
            variant="ghost"
            className="h-9 w-full justify-start rounded-md px-2.5 text-[12px] font-normal hover:bg-sidebar-accent/70"
            onClick={props.onOpenHardware}
          >
            <Cpu className="size-3.5" />
            Hardware
          </Button>
          <Collapsible
            open={props.historyOpen}
            onOpenChange={props.setHistoryOpen}
          >
            <CollapsibleTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                className="h-9 w-full justify-between rounded-md px-2.5 text-[12px] font-normal hover:bg-sidebar-accent/70"
              >
                <span className="flex items-center gap-2">
                  <ArrowClockwise className="size-3.5" />
                  History
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {props.historyOpen ? "−" : "+"}
                </span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="max-h-[calc(100vh-9rem)] overflow-y-auto pt-1.5">
              <Separator className="mb-1.5 bg-border/70" />
              <div className="space-y-1">
                {props.recentRuns.length === 0 ? (
                  <div className="px-2.5 py-3 text-[11px] text-muted-foreground leading-relaxed">
                    No cached runs yet.
                  </div>
                ) : (
                  props.recentRuns.map((run) => (
                    <button
                      key={run.requestHash}
                      onClick={() => props.onLoadRecentRun(run.requestHash)}
                      className={cn(
                        "w-full rounded-md px-2.5 py-2 text-left transition-colors",
                        props.activeRunRequestHash === run.requestHash
                          ? "bg-sidebar-accent text-foreground"
                          : "hover:bg-sidebar-accent/70",
                      )}
                    >
                      <div className="text-[11.5px] font-medium line-clamp-2">
                        {run.title}
                      </div>
                      <div className="mt-1 text-[10px] text-muted-foreground">
                        {run.createdAtLabel} · {run.candidateCount}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      </div>
      <div className="flex-1" />
    </div>
  );
}

function IntegratedWorkbench(props: {
  workspaceTab: WorkspaceTab;
  setWorkspaceTab: (tab: WorkspaceTab) => void;
  target: DiscoveryTarget;
  systemSpecs: SystemSpecs;
  setSystemSpecs: Dispatch<SetStateAction<SystemSpecs>>;
  source: DiscoverySource;
  recommendations: Recommendation[];
  activeRecommendation: Recommendation | null;
  setActiveRecommendationId: (id: string | null) => void;
  runtimeMode: AgentRuntimeMode | null;
  resultOrigin: AgentResultOrigin | null;
  reportMeta: RecommendationReportMeta | null;
  runtimeSummary: string | null;
}) {
  const hasReport = props.recommendations.length > 0;
  const isEmptyWorkbench =
    !props.target.requestText.trim() &&
    !props.target.analyteName.trim() &&
    !hasReport;
  const [hardwareSection, setHardwareSection] = useState<
    "columns" | "solvents" | "instrument"
  >("columns");

  return (
    <div className="@container h-full overflow-y-auto bg-surface-2">
      <div className="min-h-full">
        <div
          className={cn(
            "pt-12 pb-20 space-y-10",
            props.workspaceTab === "hardware"
              ? "w-full px-4 @[720px]:px-6"
              : "max-w-[1180px] mx-auto px-6 @[720px]:px-10",
          )}
        >
          {props.workspaceTab !== "hardware" &&
          !(props.workspaceTab === "draft" && isEmptyWorkbench) ? (
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0">
                <h1 className="font-display text-[34px] tracking-tight leading-[1.05]">
                  {props.workspaceTab === "reports"
                    ? "Reports"
                    : props.target.requestText || "Prepared brief"}
                </h1>
              </div>
              {props.workspaceTab !== "draft" ? (
                <Badge
                  variant="outline"
                  className="h-8 shrink-0 rounded-full px-3 text-[12px] text-muted-foreground"
                >
                  {props.workspaceTab === "reports"
                    ? "Reports explorer"
                    : `${formatRuntimeMode(props.runtimeMode)} · ${formatSourceLabel(props.source)}`}
                </Badge>
              ) : null}
            </div>
          ) : null}

          {props.workspaceTab === "draft" ? (
            isEmptyWorkbench ? (
              <div className="min-h-[640px]" aria-label="Empty workbench">
                <div className="flex h-full items-end justify-between gap-6">
                  <div className="max-w-sm">
                    <p className="text-[14px] leading-relaxed text-muted-foreground">
                      Start in Apriori by entering a method request with the
                      analyte, sample matrix, runtime target, and any detector
                      constraints.
                    </p>
                  </div>
                  <StudioBadge tone="accent">
                    Enter a method request
                  </StudioBadge>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 @[920px]:grid-cols-[1.1fr_0.9fr] gap-x-12 gap-y-10">
                <section className="space-y-8">
                  <EditorSection title="Brief">
                    <Card className="border border-border bg-background/92">
                      <CardContent className="px-4 py-4">
                        <p className="text-[14px] leading-relaxed whitespace-pre-wrap">
                          {props.target.requestText}
                        </p>
                      </CardContent>
                    </Card>
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-3">
                          <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                            Analyte
                          </div>
                          <div className="mt-2 text-[13px]">
                            {props.target.analyteName || "Not specified yet"}
                          </div>
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-3">
                          <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                            Matrix
                          </div>
                          <div className="mt-2 text-[13px]">
                            {props.target.matrix === "Other"
                              ? props.target.customMatrix || "Custom matrix"
                              : props.target.matrix || "Not specified yet"}
                          </div>
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-3">
                          <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                            Runtime cap
                          </div>
                          <div className="mt-2 text-[13px]">
                            {props.target.maxRunTimeMin
                              ? `${props.target.maxRunTimeMin} min`
                              : "No cap"}
                          </div>
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-3">
                          <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                            Detection
                          </div>
                          <div className="mt-2 text-[13px]">
                            {props.target.requireMS
                              ? "MS required"
                              : "Detector flexible"}
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </EditorSection>
                </section>

                <section className="space-y-8">
                  <EditorSection title="Workflow state">
                    <div className="space-y-2 text-[13px]">
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-2">
                          {formatRuntimeSummary(props.target)}
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-2">
                          Runtime mode: {formatRuntimeMode(props.runtimeMode)} ·
                          Origin: {formatResultOrigin(props.resultOrigin)}
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-2">
                          {props.reportMeta?.runtime?.summary ||
                            "No runtime summary yet."}
                        </CardContent>
                      </Card>
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardContent className="px-3 py-2">
                          Source mode: {formatSourceLabel(props.source)}
                          {props.reportMeta
                            ? ` · ${props.reportMeta.discovered_paper_count} discovered / ${props.reportMeta.considered_candidate_count} considered`
                            : ""}
                        </CardContent>
                      </Card>
                    </div>
                  </EditorSection>
                  {hasReport ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => props.setWorkspaceTab("reports")}
                    >
                      <FileText className="size-3.5" /> Open reports
                    </Button>
                  ) : null}
                </section>
              </div>
            )
          ) : null}

          {props.workspaceTab === "hardware" ? (
            <div className="studio-panel min-h-[calc(100vh-10rem)] w-full rounded-xl overflow-hidden">
              <div className="shrink-0 px-6 pt-6 pb-4 border-b border-border flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <h2 className="font-display text-[20px] tracking-[-0.02em] leading-tight">
                    Hardware & solvents
                  </h2>
                  <p className="text-[12.5px] text-muted-foreground mt-1.5 leading-relaxed">
                    Configure the columns, solvents, and instrument available in
                    your lab.
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8"
                  onClick={() => props.setWorkspaceTab("draft")}
                >
                  Exit
                </Button>
              </div>

              <div className="shrink-0 flex items-center px-6 gap-0.5 py-2 border-b border-border bg-surface">
                {(["columns", "solvents", "instrument"] as const).map(
                  (section) => (
                    <button
                      key={section}
                      onClick={() => setHardwareSection(section)}
                      className={cn(
                        "px-3 h-7 rounded-md text-[12.5px] font-medium capitalize transition-colors",
                        hardwareSection === section
                          ? "bg-background text-foreground border border-border"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface-2",
                      )}
                    >
                      {section}
                    </button>
                  ),
                )}
              </div>

              <div className="px-6 py-5 space-y-5 text-[13px]">
                {hardwareSection === "columns" ? (
                  <>
                    <section>
                      <div className="text-[12px] font-medium text-foreground/75 mb-2">
                        Column setup
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <Input
                          value={props.systemSpecs.columnManufacturer}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              columnManufacturer: event.target.value,
                            }))
                          }
                          placeholder="Column manufacturer"
                        />
                        <Input
                          value={props.systemSpecs.columnName}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              columnName: event.target.value,
                            }))
                          }
                          placeholder="Column name"
                        />
                        <Input
                          value={props.systemSpecs.columnChemistry}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              columnChemistry: event.target.value,
                            }))
                          }
                          placeholder="Column chemistry"
                        />
                        <Input
                          value={props.systemSpecs.columnLengthMm ?? ""}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              columnLengthMm: event.target.value
                                ? Number(event.target.value)
                                : null,
                            }))
                          }
                          placeholder="Column length (mm)"
                        />
                        <Input
                          value={props.systemSpecs.columnIdMm ?? ""}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              columnIdMm: event.target.value
                                ? Number(event.target.value)
                                : null,
                            }))
                          }
                          placeholder="Inner diameter (mm)"
                        />
                        <Input
                          value={props.systemSpecs.particleSizeUm ?? ""}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              particleSizeUm: event.target.value
                                ? Number(event.target.value)
                                : null,
                            }))
                          }
                          placeholder="Particle size (µm)"
                        />
                      </div>
                    </section>
                    <section className="rounded-xl border border-border bg-surface px-4 py-4">
                      <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                        Current column
                      </div>
                      <p className="mt-2 text-[13px] leading-relaxed">
                        {[
                          props.systemSpecs.columnManufacturer,
                          props.systemSpecs.columnName ||
                            props.systemSpecs.columnChemistry,
                        ]
                          .filter(Boolean)
                          .join(" ") || "No column configured"}
                      </p>
                    </section>
                  </>
                ) : null}

                {hardwareSection === "solvents" ? (
                  <>
                    <section>
                      <div className="text-[12px] font-medium text-foreground/75 mb-2">
                        Solvent inventory
                      </div>
                      <Input
                        value={props.systemSpecs.availableSolvents.join(", ")}
                        onChange={(event) =>
                          props.setSystemSpecs((current) => ({
                            ...current,
                            availableSolvents: event.target.value
                              .split(",")
                              .map((item) => item.trim())
                              .filter(Boolean),
                          }))
                        }
                        placeholder="Water, Acetonitrile, Methanol"
                      />
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        Separate solvents with commas.
                      </p>
                    </section>
                    <section className="rounded-xl border border-border bg-surface px-4 py-4">
                      <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                        Available solvents
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {props.systemSpecs.availableSolvents.length ? (
                          props.systemSpecs.availableSolvents.map((solvent) => (
                            <span
                              key={solvent}
                              className="inline-flex items-center rounded-md border border-border bg-background px-2.5 py-1 text-[12px] text-foreground/85"
                            >
                              {solvent}
                            </span>
                          ))
                        ) : (
                          <span className="text-[12px] text-muted-foreground">
                            No solvents listed yet.
                          </span>
                        )}
                      </div>
                    </section>
                  </>
                ) : null}

                {hardwareSection === "instrument" ? (
                  <>
                    <section>
                      <div className="text-[12px] font-medium text-foreground/75 mb-2">
                        Instrument constraints
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <Input
                          value={props.systemSpecs.detectorTypes.join(", ")}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              detectorTypes: event.target.value
                                .split(",")
                                .map((item) => item.trim())
                                .filter(Boolean),
                            }))
                          }
                          placeholder="Detector types"
                        />
                        <Input
                          value={props.systemSpecs.instrumentModes.join(", ")}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              instrumentModes: event.target.value
                                .split(",")
                                .map((item) => item.trim())
                                .filter(Boolean),
                            }))
                          }
                          placeholder="Instrument modes"
                        />
                        <Input
                          value={props.systemSpecs.maxPressureBar ?? ""}
                          onChange={(event) =>
                            props.setSystemSpecs((current) => ({
                              ...current,
                              maxPressureBar: event.target.value
                                ? Number(event.target.value)
                                : null,
                            }))
                          }
                          placeholder="Max pressure (bar)"
                        />
                      </div>
                    </section>
                    <section className="rounded-xl border border-border bg-surface px-4 py-4">
                      <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                        Summary
                      </div>
                      <p className="mt-2 text-[13px] leading-relaxed">
                        {formatSystemSummary(props.systemSpecs)}
                      </p>
                    </section>
                  </>
                ) : null}
              </div>
            </div>
          ) : null}

          {props.workspaceTab === "reports" ? (
            <IntegratedReportsWorkspace
              target={props.target}
              systemSpecs={props.systemSpecs}
              source={props.source}
              recommendations={props.recommendations}
              activeRecommendation={props.activeRecommendation}
              onSelectRecommendation={props.setActiveRecommendationId}
              reportMeta={props.reportMeta}
              resultOrigin={props.resultOrigin}
              runtimeSummary={props.runtimeSummary}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function EditorSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 space-y-2">
        <span className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
          {title}
        </span>
        <Separator className="bg-border/70" />
      </div>
      <div>{children}</div>
    </section>
  );
}

function IntegratedCopilotPanel(props: {
  chat: ChatMessage[];
  input: string;
  setInput: (value: string) => void;
  loading: boolean;
  onSend: (prompt: string) => void;
  scrollRef: React.RefObject<HTMLDivElement>;
  textAreaRef: React.RefObject<HTMLTextAreaElement>;
  target: DiscoveryTarget;
  systemSpecs: SystemSpecs;
  source: DiscoverySource;
  setSource: (value: DiscoverySource) => void;
  runtimeMode: AgentRuntimeMode | null;
  resultOrigin: AgentResultOrigin | null;
  reportMeta: RecommendationReportMeta | null;
  steps: Array<{ id: string; label: string; status: string; detail?: string }>;
  activeRecommendation: Recommendation | null;
  pendingClarification: ClarificationQuestion[] | null;
  clarificationSubmit: (answers: Record<string, string>) => Promise<void>;
  clarificationDismiss: () => Promise<void>;
  workspaceTab: WorkspaceTab;
  onOpenReports: () => void;
}) {
  const [clarificationAnswers, setClarificationAnswers] = useState<
    Record<string, string>
  >({});

  useEffect(() => {
    setClarificationAnswers({});
  }, [props.pendingClarification]);

  const starterSuggestions = props.activeRecommendation
    ? [
        "Explain why the open report is the strongest starting method.",
        "Compare the top reports and tell me what would change on my hardware.",
        "What would you refine next to improve confidence?",
      ]
    : [
        "Design a method for caffeine in coffee, MS-friendly, under 8 minutes",
        "Review all metformin plasma methods and recommend the strongest report",
        "What is missing before you can run discovery?",
      ];

  const startedThinking = props.steps.some((step) => step.status !== "pending");
  const activeSteps = props.steps.filter((step) => step.status !== "pending");

  return (
    <div className="h-full flex flex-col bg-surface">
      <div className="h-12 shrink-0 px-4 flex items-center gap-2 border-b border-border">
        <Sparkle className="size-3.5 text-clay" />
        <span className="font-display text-[13px]">Apriori</span>
      </div>

      <div ref={props.scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
        <div className="space-y-4">
          <Card size="sm" className="border border-border bg-background/92">
            <CardHeader className="pb-0">
              <CardTitle className="text-[12px] font-medium">
                Method request
              </CardTitle>
              <CardDescription className="text-[11px] leading-relaxed">
                {props.target.analyteName || "No analyte yet"} ·{" "}
                {props.target.matrix === "Other"
                  ? props.target.customMatrix || "Custom matrix"
                  : props.target.matrix}{" "}
                · {formatSourceLabel(props.source)} ·{" "}
                {props.systemSpecs.detectorTypes.join(", ") || "No detector"}
              </CardDescription>
              {props.activeRecommendation &&
              props.workspaceTab !== "reports" ? (
                <CardAction>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-[11px]"
                    onClick={props.onOpenReports}
                  >
                    Open report
                  </Button>
                </CardAction>
              ) : null}
            </CardHeader>
            <CardContent className="pt-3">
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {props.target.requestText ||
                  "Enter a method request below. Include the analyte, matrix, runtime target, and detector requirements."}
              </p>
            </CardContent>
          </Card>
        </div>

        {props.chat.length === 0 ? (
          <div className="h-full flex flex-col justify-end pb-2 space-y-4 animate-fade-in">
            <div>
              <p className="font-display text-[22px] leading-tight text-foreground/90">
                Start a method request
              </p>
              <p className="text-[13px] text-muted-foreground mt-1.5 leading-relaxed">
                Describe the analyte, matrix, runtime target, and detection
                constraints. Apriori will turn that into the working method
                brief and run state.
              </p>
            </div>
            <div className="space-y-1">
              {starterSuggestions.map((suggestion) => (
                <Button
                  key={suggestion}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => props.onSend(suggestion)}
                  className="h-auto w-full justify-start rounded-lg px-3 py-3 text-left text-[13px] whitespace-normal leading-relaxed"
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="space-y-5">
          {props.chat.map((entry) =>
            entry.role === "tool" ? (
              <div key={entry.id} className="pl-9 animate-fade-in">
                <div className="group flex items-start gap-2 text-[12px] font-mono w-full text-left text-muted-foreground">
                  <Wrench className="size-3 shrink-0 text-clay mt-1" />
                  <div>
                    <div>{entry.content}</div>
                    {entry.mutations?.length ? (
                      <div className="mt-1.5 space-y-1">
                        {entry.mutations.map((mutation, index) => (
                          <div
                            key={`${entry.id}-${index}`}
                            className="text-[11px] text-foreground/70"
                          >
                            {mutation.field}: {mutation.value}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : entry.artifact === "thinking" ? (
              startedThinking ||
              props.reportMeta?.runtime?.summary ||
              props.activeRecommendation ? (
                <div key={entry.id} className="animate-fade-up">
                  <div className="flex gap-2.5">
                    <div className="size-6 shrink-0 rounded bg-clay/10 border border-clay/20 grid place-items-center mt-0.5">
                      <Sparkle className="size-3 text-clay" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <Card
                        size="sm"
                        className="border border-border bg-background/92"
                      >
                        <CardHeader className="pb-0">
                          <CardTitle className="text-[12px] font-medium">
                            Thinking
                          </CardTitle>
                          <CardDescription className="text-[11px]">
                            {formatRuntimeMode(props.runtimeMode)} ·{" "}
                            {formatResultOrigin(props.resultOrigin)}
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2 pt-3">
                          {activeSteps.map((step) => (
                            <Card
                              key={step.id}
                              size="sm"
                              className="border border-border bg-surface/90"
                            >
                              <CardContent className="px-3 py-2">
                                <div className="flex items-center justify-between gap-3">
                                  <span className="text-[12px]">
                                    {step.label}
                                  </span>
                                  <span className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                                    {step.status}
                                  </span>
                                </div>
                                {step.detail ? (
                                  <p className="mt-1 text-[11px] text-muted-foreground">
                                    {step.detail}
                                  </p>
                                ) : null}
                              </CardContent>
                            </Card>
                          ))}
                          {props.reportMeta?.runtime?.summary ? (
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              {props.reportMeta.runtime.summary}
                            </p>
                          ) : null}
                          {props.activeRecommendation ? (
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              Active report:{" "}
                              {extractRecommendationTitle(
                                props.activeRecommendation,
                              )}
                            </p>
                          ) : null}
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                </div>
              ) : null
            ) : entry.artifact === "clarification" ? (
              props.pendingClarification?.length ? (
                <div key={entry.id} className="animate-fade-up">
                  <div className="flex gap-2.5">
                    <div className="size-6 shrink-0 rounded bg-clay/10 border border-clay/20 grid place-items-center mt-0.5">
                      <CaretRight className="size-3 text-clay" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <Card
                        size="sm"
                        className="border border-clay/25 bg-clay/5"
                      >
                        <CardHeader className="pb-0">
                          <CardTitle className="text-[12px] font-medium">
                            Clarification needed
                          </CardTitle>
                          <CardDescription className="text-[11px] leading-relaxed">
                            The run paused for missing context. Answer here and
                            Apriori will continue.
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3 pt-3">
                          {props.pendingClarification.map((question) => (
                            <div key={question.id} className="space-y-1.5">
                              <label className="text-[12px] font-medium">
                                {question.question}
                              </label>
                              <Input
                                value={clarificationAnswers[question.id] ?? ""}
                                onChange={(event) =>
                                  setClarificationAnswers((current) => ({
                                    ...current,
                                    [question.id]: event.target.value,
                                  }))
                                }
                                placeholder={question.placeholder}
                              />
                            </div>
                          ))}
                          <div className="flex gap-2 pt-1">
                            <Button
                              size="sm"
                              onClick={() =>
                                void props.clarificationSubmit(
                                  clarificationAnswers,
                                )
                              }
                            >
                              Continue run
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void props.clarificationDismiss()}
                            >
                              Skip for now
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                </div>
              ) : null
            ) : (
              <div key={entry.id} className="animate-fade-up">
                {entry.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="max-w-[88%] rounded-md bg-surface-2 border border-border px-3 py-1.5 text-[13.5px] leading-relaxed whitespace-pre-wrap">
                      {entry.content}
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2.5">
                    <div className="size-6 shrink-0 rounded bg-clay/10 border border-clay/20 grid place-items-center mt-0.5">
                      <Sparkle className="size-3 text-clay" />
                    </div>
                    <div className="flex-1 min-w-0 pt-0.5">
                      {entry.pending ? (
                        <div className="flex items-center gap-1.5 py-1 text-muted-foreground">
                          <span className="size-1.5 rounded-full bg-muted-foreground animate-pulse-dot" />
                          <span
                            className="size-1.5 rounded-full bg-muted-foreground animate-pulse-dot"
                            style={{ animationDelay: "0.2s" }}
                          />
                          <span
                            className="size-1.5 rounded-full bg-muted-foreground animate-pulse-dot"
                            style={{ animationDelay: "0.4s" }}
                          />
                        </div>
                      ) : (
                        <div className="prose-chat whitespace-pre-wrap">
                          {entry.content}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ),
          )}
        </div>
      </div>

      <div className="px-3 pb-3 pt-3 border-t border-border space-y-2">
        {props.chat.length > 0 ? (
          <div className="flex flex-wrap gap-1 animate-fade-in">
            {starterSuggestions.slice(0, 3).map((suggestion) => (
              <Button
                key={suggestion}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => props.onSend(suggestion)}
                disabled={props.loading}
                className="rounded-full px-2.5 text-[11.5px] text-muted-foreground"
              >
                {suggestion}
              </Button>
            ))}
          </div>
        ) : null}

        <div className="studio-panel rounded-xl focus-within:border-border-strong transition-all">
          <textarea
            ref={props.textAreaRef}
            value={props.input}
            onChange={(event) => props.setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                props.onSend(props.input);
              }
            }}
            placeholder="Enter a method request, or ask Apriori to refine the current one…"
            rows={1}
            className="w-full resize-none bg-transparent px-3 pt-2.5 pb-1 text-[13.5px] leading-relaxed focus:outline-none placeholder:text-muted-foreground"
          />
          <div className="flex items-center justify-between px-2 pb-1.5">
            <div className="flex items-center gap-2 pl-1.5 text-[10.5px] text-muted-foreground">
              <span>Enter to send</span>
              <span>·</span>
              <span>Method request updates apply to the live run state</span>
            </div>
            <div className="flex items-center gap-2">
              <SourceModeToggle
                compact
                source={props.source}
                setSource={props.setSource}
              />
              <Button
                size="sm"
                className="h-7 w-7 p-0 rounded"
                disabled={props.loading || !props.input.trim()}
                onClick={() => props.onSend(props.input)}
                aria-label="Send"
              >
                {props.loading ? (
                  <CircleNotch className="size-3.5 animate-spin" />
                ) : (
                  <ArrowUp className="size-3.5" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function IntegratedCommandPalette(props: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  actions: Array<{ label: string; action: () => void }>;
  recentRuns: Array<{ requestHash: string; title: string }>;
  onLoadRecentRun: (requestHash: string) => void;
}) {
  return (
    <CommandDialog open={props.open} onOpenChange={props.onOpenChange}>
      <CommandInput placeholder="Search actions or recent runs…" />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        <CommandGroup heading="Actions">
          {props.actions.map((action) => (
            <CommandItem
              key={action.label}
              onSelect={() => {
                action.action();
                props.onOpenChange(false);
              }}
            >
              <Play className="size-4 mr-2" /> {action.label}
            </CommandItem>
          ))}
        </CommandGroup>
        {props.recentRuns.length ? (
          <CommandGroup heading="Recent runs">
            {props.recentRuns.map((run) => (
              <CommandItem
                key={run.requestHash}
                onSelect={() => {
                  props.onLoadRecentRun(run.requestHash);
                  props.onOpenChange(false);
                }}
              >
                <MagnifyingGlass className="size-4 mr-2" />
                <span className="truncate">{run.title}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}
      </CommandList>
    </CommandDialog>
  );
}

function SourceModeToggle({
  compact = false,
  source,
  setSource,
}: {
  compact?: boolean;
  source: DiscoverySource;
  setSource: (value: DiscoverySource) => void;
}) {
  const isOpenAccess = source === "open_access";

  return (
    <button
      type="button"
      onClick={() => setSource(isOpenAccess ? "local_corpus" : "open_access")}
      aria-label={`Switch source mode. Currently ${isOpenAccess ? "Open access" : "Local corpus"}`}
      className={cn(
        "relative inline-flex items-center overflow-hidden rounded-full border transition-colors",
        compact
          ? "h-7 min-w-[112px] pl-1 pr-2"
          : "h-8 min-w-[136px] pl-1 pr-2.5",
        isOpenAccess
          ? "border-[#2f6df6]/30 bg-[#2f6df6] text-white"
          : "border-border bg-muted text-foreground",
      )}
    >
      <span
        className={cn(
          "absolute left-1 rounded-full bg-white/95 shadow-sm transition-transform",
          compact ? "size-4" : "size-5",
          isOpenAccess
            ? compact
              ? "translate-x-[86px]"
              : "translate-x-[107px]"
            : "translate-x-0",
        )}
      />
      <span
        className={cn(
          "relative z-10 ml-6 font-medium whitespace-nowrap",
          compact ? "text-[10px]" : "text-[11px]",
          isOpenAccess ? "text-white" : "text-foreground",
        )}
      >
        {isOpenAccess ? "Open access" : "Local corpus"}
      </span>
    </button>
  );
}

function IntegratedReportsWorkspace({
  target,
  systemSpecs,
  source,
  recommendations,
  activeRecommendation,
  onSelectRecommendation,
  reportMeta,
  resultOrigin,
  runtimeSummary,
}: {
  target: DiscoveryTarget;
  systemSpecs: SystemSpecs;
  source: DiscoverySource;
  recommendations: Recommendation[];
  activeRecommendation: Recommendation | null;
  onSelectRecommendation: (id: string | null) => void;
  reportMeta: RecommendationReportMeta | null;
  resultOrigin: AgentResultOrigin | null;
  runtimeSummary: string | null;
}) {
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = () => {
    if (!activeRecommendation) {
      setExportMessage(null);
      setExportError("Select a report before exporting the analysis package.");
      return;
    }

    try {
      const filename = downloadAnalysisExport({
        target,
        systemSpecs,
        sourceMode: reportMeta?.source_mode || source,
        searchQuery: reportMeta?.search_query_used?.trim() || null,
        reportMeta,
        recommendations,
        selectedRecommendationId: activeRecommendation.paper_id,
        resultOrigin,
        hasStaleReport: false,
      });

      setExportError(null);
      setExportMessage(`Exported analysis package: ${filename}`);
    } catch (error) {
      setExportMessage(null);
      setExportError(
        error instanceof Error && error.message
          ? error.message
          : "Unable to create the export artifact.",
      );
    }
  };

  return (
    <section className="space-y-4">
      <EditorSection title="Reports">
        {exportMessage ? (
          <Card
            size="sm"
            className="border border-emerald-300/60 bg-emerald-50/80 dark:border-emerald-500/35 dark:bg-emerald-500/10"
          >
            <CardContent className="px-4 py-3 text-[12px] text-emerald-900 dark:text-emerald-100">
              {exportMessage}
            </CardContent>
          </Card>
        ) : null}
        {exportError ? (
          <Card
            size="sm"
            className="border border-rose-300/60 bg-rose-50/80 dark:border-rose-500/35 dark:bg-rose-500/10"
          >
            <CardContent className="px-4 py-3 text-[12px] text-rose-900 dark:text-rose-100">
              {exportError}
            </CardContent>
          </Card>
        ) : null}
        {recommendations.length === 0 ? (
          <Card
            size="sm"
            className="border border-dashed border-border bg-background/92"
          >
            <CardContent className="px-4 py-8 text-center text-[13px] text-muted-foreground">
              No recommendation report yet. Run discovery and the reports list
              will populate here.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {recommendations.map((recommendation, index) => {
              const isOpen =
                activeRecommendation?.paper_id === recommendation.paper_id;

              return (
                <Collapsible
                  key={recommendation.paper_id}
                  open={isOpen}
                  onOpenChange={(open) =>
                    onSelectRecommendation(
                      open ? recommendation.paper_id : null,
                    )
                  }
                >
                  <Card
                    className={cn(
                      "overflow-hidden border bg-background/92 transition-colors",
                      isOpen
                        ? "border-primary/30 bg-background"
                        : "border-border",
                    )}
                  >
                    <CollapsibleTrigger asChild>
                      <button
                        type="button"
                        className="w-full text-left"
                        aria-label={`${isOpen ? "Collapse" : "Open"} report ${index + 1}`}
                      >
                        <CardHeader className="gap-4">
                          <div className="flex min-w-0 items-start gap-3">
                            <div className="pt-0.5">
                              <CaretRight
                                className={cn(
                                  "size-3.5 text-muted-foreground transition-transform duration-200",
                                  isOpen && "rotate-90",
                                )}
                              />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="text-[12px] text-muted-foreground">
                                Report {index + 1}
                              </div>
                              <CardTitle className="mt-1 text-[14px] font-medium leading-snug">
                                {recommendation.title}
                              </CardTitle>
                              <CardDescription className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                                {recommendation.rationale}
                              </CardDescription>
                            </div>
                          </div>
                          <CardAction className="items-start">
                            <div className="flex flex-wrap justify-end gap-1.5">
                              <StudioBadge tone="blue">
                                {recommendation.score.total_score.toFixed(2)}
                              </StudioBadge>
                              <StudioBadge>
                                {recommendation.trust.trust_state.replace(
                                  /_/g,
                                  " ",
                                )}
                              </StudioBadge>
                            </div>
                          </CardAction>
                        </CardHeader>
                      </button>
                    </CollapsibleTrigger>

                    <CollapsibleContent>
                      <CardContent className="space-y-5 border-t border-border/70 px-6 py-5">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex flex-wrap gap-2">
                            <StudioBadge tone="blue">
                              {recommendation.trust.trust_state.replace(
                                /_/g,
                                " ",
                              )}
                            </StudioBadge>
                            <StudioBadge>
                              {recommendation.trust.validation_status.replace(
                                /_/g,
                                " ",
                              )}
                            </StudioBadge>
                            <StudioBadge>
                              score{" "}
                              {recommendation.score.total_score.toFixed(2)}
                            </StudioBadge>
                          </div>
                          {isOpen ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-[11px]"
                              onClick={handleExport}
                            >
                              <FileText className="mr-1.5 size-3.5" />
                              Export package
                            </Button>
                          ) : null}
                        </div>

                        <div className="grid grid-cols-1 @[840px]:grid-cols-2 gap-5">
                          <Card
                            size="sm"
                            className="border border-border bg-surface/90"
                          >
                            <CardHeader className="pb-0">
                              <CardTitle className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                                Method summary
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-3">
                              {recommendation.recommended_method ? (
                                <div className="space-y-2 text-[13px]">
                                  <div>
                                    Runtime:{" "}
                                    {recommendation.recommended_method.run_time_min?.toFixed(
                                      1,
                                    ) ?? "n/a"}{" "}
                                    min
                                  </div>
                                  <div>
                                    Flow:{" "}
                                    {recommendation.recommended_method.flow_rate_ml_min?.toFixed(
                                      2,
                                    ) ?? "n/a"}{" "}
                                    mL/min
                                  </div>
                                  <div>
                                    Injection:{" "}
                                    {recommendation.recommended_method.injection_volume_ul?.toFixed(
                                      1,
                                    ) ?? "n/a"}{" "}
                                    µL
                                  </div>
                                </div>
                              ) : (
                                <p className="text-[13px] text-muted-foreground">
                                  No scaled method payload was returned for this
                                  report.
                                </p>
                              )}
                            </CardContent>
                          </Card>
                          <Card
                            size="sm"
                            className="border border-border bg-surface/90"
                          >
                            <CardHeader className="pb-0">
                              <CardTitle className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                                Decision trace
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-3">
                              <p className="text-[13px] leading-relaxed text-muted-foreground">
                                {recommendation.decision_trace
                                  ?.dominant_differentiator ||
                                  recommendation.decision_trace
                                    ?.screening_summary ||
                                  "No decision trace summary available."}
                              </p>
                            </CardContent>
                          </Card>
                          <Card
                            size="sm"
                            className="border border-border bg-surface/90"
                          >
                            <CardHeader className="pb-0">
                              <CardTitle className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                                Runtime summary
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-3">
                              <p className="text-[13px] leading-relaxed text-muted-foreground">
                                {runtimeSummary ||
                                  "No runtime summary available for this report."}
                              </p>
                            </CardContent>
                          </Card>
                        </div>

                        <Card className="border border-border bg-surface/90">
                          <CardHeader className="pb-0">
                            <CardTitle className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                              Gradient profile
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="pt-4">
                            <GradientProfileChart
                              recommendation={recommendation}
                            />
                          </CardContent>
                        </Card>

                        <Card className="border border-border bg-surface/90">
                          <CardHeader className="pb-0">
                            <CardTitle className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                              Evidence snippets
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-3 pt-3">
                            {recommendation.evidence_snippets.length ? (
                              recommendation.evidence_snippets
                                .slice(0, 4)
                                .map((snippet, snippetIndex) => (
                                  <Card
                                    key={`${snippet.text}-${snippetIndex}`}
                                    size="sm"
                                    className="border border-border bg-background"
                                  >
                                    <CardContent className="px-3 py-3">
                                      <p className="text-[13px] leading-relaxed">
                                        {snippet.text}
                                      </p>
                                      <p className="mt-2 text-[11px] text-muted-foreground">
                                        {snippet.section_label || "Evidence"}{" "}
                                        {snippet.page_number
                                          ? `· p. ${snippet.page_number}`
                                          : ""}
                                      </p>
                                    </CardContent>
                                  </Card>
                                ))
                            ) : (
                              <p className="text-[13px] text-muted-foreground">
                                No evidence snippets were returned for this
                                report.
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      </CardContent>
                    </CollapsibleContent>
                  </Card>
                </Collapsible>
              );
            })}
          </div>
        )}
      </EditorSection>
    </section>
  );
}

function GradientProfileChart({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  const gradient = recommendation.recommended_method?.gradient_profile ?? [];

  if (gradient.length === 0) {
    return (
      <p className="text-[13px] text-muted-foreground">
        No gradient profile available for this report.
      </p>
    );
  }

  const width = 720;
  const height = 240;
  const padding = 24;
  const maxTime = Math.max(...gradient.map((point) => point.time_min), 1);
  const points = gradient.map((point) => {
    const x = padding + (point.time_min / maxTime) * (width - padding * 2);
    const y =
      height - padding - (point.percent_b / 100) * (height - padding * 2);
    return `${x},${y}`;
  });

  return (
    <div className="space-y-4">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full rounded-md border border-border bg-surface"
      >
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="currentColor"
          opacity="0.18"
        />
        <line
          x1={padding}
          y1={padding}
          x2={padding}
          y2={height - padding}
          stroke="currentColor"
          opacity="0.18"
        />
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          points={points.join(" ")}
          opacity="0.9"
        />
        {gradient.map((point) => {
          const x =
            padding + (point.time_min / maxTime) * (width - padding * 2);
          const y =
            height - padding - (point.percent_b / 100) * (height - padding * 2);
          return (
            <circle
              key={`${point.time_min}-${point.percent_b}`}
              cx={x}
              cy={y}
              r="4"
              fill="currentColor"
            />
          );
        })}
      </svg>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {gradient.map((point) => (
          <div
            key={`${point.time_min}-${point.percent_b}`}
            className="rounded-md border border-border bg-surface px-3 py-2"
          >
            <div className="text-[11px] text-muted-foreground">
              t = {point.time_min.toFixed(1)} min
            </div>
            <div className="mt-1 text-[13px] font-medium">
              {point.percent_b.toFixed(1)}% B
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

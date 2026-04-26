import { useEffect, useRef, useState } from "react";
import { useWorkspace, buildAgentSnapshot } from "@/studio/store/workspace";
import { runToolCall } from "@/studio/agent/tools";
import { generateStudioAgentReply, generateStudioAgentRecognition, generateStudioAgentPlan } from "@/studio/lib/agentResponder";
import { Button } from "@/studio/components/ui/button";
import { ArrowUp, CircleNotch, Sparkle, CaretRight, Wrench, WarningCircle, CheckCircle, ListChecks } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { ChatEvent } from "@/studio/types/hplc";

const SUGGESTIONS = [
  "Design a method for caffeine in coffee, MS-friendly, under 8 min",
  "Make the current method faster",
  "Update the hardware with a C18 column and acetonitrile",
  "Predict a chromatogram for the active method",
];

export const CopilotPanel = () => {
  const chat = useWorkspace((s) => s.chat);
  const appendChat = useWorkspace((s) => s.appendChat);
  const patchChat = useWorkspace((s) => s.patchChat);
  const removeChat = useWorkspace((s) => s.removeChat);
  const pendingPrompt = useWorkspace((s) => s.pendingPrompt);
  const setPendingPrompt = useWorkspace((s) => s.setPendingPrompt);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat]);

  useEffect(() => {
    const element = textAreaRef.current;
    if (!element) {
      return;
    }
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [input]);

  const send = async (text: string) => {
    if (!text.trim() || loading) {
      return;
    }

    appendChat({ role: "user", content: text, kind: "message" });
    const pendingId = appendChat({ role: "assistant", content: "", kind: "message", pending: true });
    setInput("");
    setLoading(true);

    await new Promise((resolve) => window.setTimeout(resolve, 350));

    try {
      const snapshot = buildAgentSnapshot();
      
      // Stage 1: Recognition & Verification
      const recognition = generateStudioAgentRecognition(text, snapshot);
      const analytesLabel = recognition.analytes.length > 0 
        ? recognition.analytes.map((a: any) => a.name).join(", ") 
        : "no specific analytes";
      
      const content = `I've analyzed your request. I detected ${analytesLabel} in ${recognition.matrix || "the current matrix"}. \n\nPlease verify these details and your hardware configuration before I build the research protocol.`;

      patchChat(pendingId, { 
        content, 
        pending: false,
        pendingAction: {
          type: "verify_recognition",
          label: "Verify & Build Plan",
          data: { recognition, originalPrompt: text }
        }
      });
    } catch (error) {
      removeChat(pendingId);
      appendChat({
        role: "assistant",
        content:
          error instanceof Error && error.message
            ? error.message
            : "The local studio adapter hit an unexpected error.",
        kind: "message",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (eventId: string, type: string, data: any) => {
    setLoading(true);
    const pendingId = appendChat({ role: "assistant", content: "", kind: "message", pending: true });
    
    await new Promise((resolve) => window.setTimeout(resolve, 450));

    try {
      const snapshot = buildAgentSnapshot();

      if (type === "verify_recognition") {
        // Stage 2: Planning & Approval
        const plan = generateStudioAgentPlan(data.recognition, snapshot);
        const content = `${plan.summary}\n\n**Research Protocol:**\n${plan.steps.map(s => `- ${s}`).join("\n")}\n\nReview the steps and approve them to begin the discovery run.`;

        patchChat(pendingId, {
          content,
          pending: false,
          pendingAction: {
            type: "approve_plan",
            label: "Approve & Execute",
            data: { ...data, plan }
          }
        });
      } else if (type === "approve_plan") {
        // Stage 3: Execution
        const reply = generateStudioAgentReply(data.originalPrompt, snapshot);

        for (const call of reply.toolCalls) {
          const result = runToolCall(call);
          appendChat({
            role: "system",
            content: result.ok ? result.label : `${result.label}${result.error ? ` — ${result.error}` : ""}`,
            kind: "tool",
            toolName: call.name,
            toolArgs: call.args,
            toolOk: result.ok,
          });
        }

        patchChat(pendingId, { 
          content: `${reply.content}\n\nDiscovery run complete. All extracted parameters have been mapped to your hardware.`, 
          pending: false 
        });
      }
      
      // Clear the action from the previous message
      patchChat(eventId, { pendingAction: undefined });
    } catch (error) {
      removeChat(pendingId);
      appendChat({
        role: "assistant",
        content: "An error occurred during execution.",
        kind: "message",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (pendingPrompt && !loading) {
      const value = pendingPrompt;
      setPendingPrompt(undefined);
      void send(value);
    }
  }, [loading, pendingPrompt, setPendingPrompt]);

  return (
    <div className="h-full flex flex-col bg-surface">
      <div className="h-12 shrink-0 px-4 flex items-center gap-2 border-b border-border">
        <Sparkle className="size-3.5 text-clay" />
        <span className="font-display text-[13px]">Copilot</span>
        <span className="text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground ml-1">
          Local studio adapter
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
        {chat.length === 0 && (
          <div className="h-full flex flex-col justify-end pb-2 space-y-4 animate-fade-in">
            <div>
              <p className="font-serif text-[22px] leading-tight text-foreground/90">
                Imported shell, local brain
              </p>
              <p className="text-[13px] text-muted-foreground mt-1.5 leading-relaxed">
                This keeps the Lovable interaction model intact while replacing the original backend with a local adapter.
              </p>
              <p className="text-[11.5px] text-muted-foreground/80 mt-2">
                The goal is to preserve the real shell behavior first, then wire it into Silico’s production workflow.
              </p>
            </div>

            <div className="space-y-1">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => void send(suggestion)}
                  className="w-full text-left text-[13px] px-3 py-2 rounded border border-border bg-background hover:bg-surface-2 hover:border-border-strong transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-5">
          {chat.map((entry) => {
            if (entry.kind === "tool") {
              return <ToolRow key={entry.id} event={entry} />;
            }

            const isUser = entry.role === "user";
            return (
              <div key={entry.id} className="animate-fade-up">
                {isUser ? (
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
                        <div className="flex items-center gap-1.5 text-muted-foreground py-1">
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
                        <div className="space-y-3">
                          <div className="prose-chat whitespace-pre-wrap">{entry.content}</div>
                          {entry.pendingAction && (
                            <div className="pt-1">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-md text-[11.5px] font-medium border-clay/30 bg-clay/5 hover:bg-clay/10 text-clay"
                                onClick={() => handleAction(entry.id, entry.pendingAction!.type, entry.pendingAction!.data)}
                                disabled={loading}
                              >
                                {entry.pendingAction.type === "verify_recognition" ? (
                                  <CheckCircle className="mr-2 size-3.5" />
                                ) : (
                                  <ListChecks className="mr-2 size-3.5" />
                                )}
                                {entry.pendingAction.label}
                              </Button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="px-3 pb-3 pt-3 border-t border-border space-y-2">
        {chat.length > 0 ? (
          <div className="flex flex-wrap gap-1 animate-fade-in">
            {SUGGESTIONS.slice(0, 3).map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => void send(suggestion)}
                disabled={loading}
                className="text-[11.5px] px-2 py-1 rounded-full border border-border bg-background hover:bg-surface-2 hover:border-border-strong text-muted-foreground hover:text-foreground transition-all disabled:opacity-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
        ) : null}

        <div className="rounded-md border border-border bg-background focus-within:border-border-strong focus-within:shadow-soft transition-all">
          <textarea
            ref={textAreaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
            placeholder="Ask the imported shell to build the brief, draft a method, or tune the active method…"
            rows={1}
            className="w-full resize-none bg-transparent px-3 pt-2.5 pb-1 text-[13.5px] leading-relaxed focus:outline-none placeholder:text-muted-foreground"
          />
          <div className="flex items-center justify-between px-2 pb-1.5">
            <div className="flex items-center gap-2 pl-1.5 text-[10.5px] text-muted-foreground">
              <span>Enter to send</span>
              <span>·</span>
              <span>Shift+Enter for newline</span>
            </div>
            <Button
              size="sm"
              className="h-7 w-7 p-0 rounded"
              disabled={loading || !input.trim()}
              onClick={() => void send(input)}
              aria-label="Send"
            >
              {loading ? <CircleNotch className="size-3.5 animate-spin" /> : <ArrowUp className="size-3.5" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ToolRow = ({ event }: { event: ChatEvent }) => {
  const [open, setOpen] = useState(false);
  const hasArgs = event.toolArgs !== undefined && event.toolArgs !== null;
  const failed = event.toolOk === false;

  return (
    <div className="pl-9 animate-fade-in">
      <button
        type="button"
        onClick={() => hasArgs && setOpen((current) => !current)}
        className={cn(
          "group flex items-center gap-2 text-[12px] font-mono w-full text-left",
          failed ? "text-destructive" : "text-muted-foreground",
          hasArgs && "hover:text-foreground transition-colors",
        )}
        aria-expanded={open}
      >
        {hasArgs ? (
          <CaretRight className={cn("size-3 shrink-0 transition-transform", open && "rotate-90")} />
        ) : failed ? (
          <WarningCircle className="size-3 shrink-0 text-destructive" />
        ) : (
          <Wrench className="size-3 shrink-0 text-clay" />
        )}
        {event.toolName ? <span className="text-clay/80 shrink-0">{event.toolName}</span> : null}
        <span className="truncate">{event.content}</span>
      </button>
      {open && hasArgs ? (
        <pre className="mt-1.5 ml-5 max-h-64 overflow-auto rounded border border-border bg-surface-2 px-2.5 py-1.5 text-[11px] font-mono text-foreground/80 whitespace-pre-wrap break-words">
          {JSON.stringify(event.toolArgs, null, 2)}
        </pre>
      ) : null}
    </div>
  );
};

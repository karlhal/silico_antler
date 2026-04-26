import "./studio.css";

import type { AgentRuntimeBootState } from "@/lib/agentRuntime";
import { useAuth } from "@/studio/hooks/useAuth";
import { StudioAuthPage } from "@/studio/StudioAuthPage";
import { IntegratedStudioShell } from "@/studio/IntegratedStudioShell";
import { AppShell } from "@/studio/components/shell/AppShell";

export function StudioApp({
  runtimeBootState,
  mode,
}: {
  runtimeBootState: AgentRuntimeBootState;
  mode: "integrated" | "classic";
}) {
  const { user } = useAuth();

  if (!user) {
    return <StudioAuthPage onAuthenticated={() => window.dispatchEvent(new Event("popstate"))} />;
  }

  if (mode === "classic") {
    return <AppShell />;
  }

  return <IntegratedStudioShell runtimeBootState={runtimeBootState} />;
}

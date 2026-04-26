import type { Method, Project } from "@/studio/types/hplc";

export const Breadcrumb = ({ project, method }: { project?: Project; method?: Method }) => {
  if (!project) {
    return <span className="text-[12.5px] text-muted-foreground">No project selected</span>;
  }
  return (
    <nav className="flex items-center gap-2 text-[12.5px]">
      <span className="text-foreground font-medium truncate max-w-[240px]">{project.name}</span>
      {method && (
        <>
          <span className="text-muted-foreground/50">/</span>
          <span className="font-mono text-[11.5px] text-muted-foreground tnum">{method.name}</span>
        </>
      )}
    </nav>
  );
};

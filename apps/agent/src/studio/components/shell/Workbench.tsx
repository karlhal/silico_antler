import { useWorkspace } from "@/studio/store/workspace";
import { Button } from "@/studio/components/ui/button";
import { GitBranch, CaretDown, Warning, Plus, Trash, Sparkle, Question } from "@phosphor-icons/react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/studio/components/ui/dropdown-menu";
import { Input } from "@/studio/components/ui/input";
import type { GradientPoint, Method, Project } from "@/studio/types/hplc";
import { useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { COMMON_ANALYTES, MATRIX_PRESETS } from "@/studio/lib/presets";
import { HardwareView } from "./HardwarePanel";
import { ChartFrame, ChartLegend } from "./ChartFrame";

export const Workbench = () => {
  const activeProjectId = useWorkspace((s) => s.activeProjectId);
  const projects = useWorkspace((s) => s.projects);
  const methods = useWorkspace((s) => s.methods);
  const setActiveMethod = useWorkspace((s) => s.setActiveMethod);
  const updateMethod = useWorkspace((s) => s.updateMethod);
  const hardwareOpen = useWorkspace((s) => s.hardwareOpen);
  const setHardwareOpen = useWorkspace((s) => s.setHardwareOpen);
  const setPendingPrompt = useWorkspace((s) => s.setPendingPrompt);
  const copilotOpen = useWorkspace((s) => s.copilotOpen);
  const project = activeProjectId ? projects[activeProjectId] : undefined;
  const method = project?.activeMethodId ? methods[project.activeMethodId] : undefined;
  const projectMethods = project ? project.methodIds.map((id) => methods[id]).filter(Boolean) : [];

  if (hardwareOpen) {
    return <HardwareView onClose={() => setHardwareOpen(false)} />;
  }


  if (!project) {
    return (
      <div className="h-full grid place-items-center p-10">
        <div className="max-w-md text-center space-y-4 animate-fade-up">
          <div className="size-10 rounded border border-clay/30 bg-clay/5 grid place-items-center mx-auto">
            <Sparkle className="size-4 text-clay" />
          </div>
          <h2 className="font-serif text-[26px] leading-tight tracking-tight">
            What are we separating today?
          </h2>
          <p className="text-[13.5px] text-muted-foreground leading-relaxed">
            Tell the imported Silico studio about your analytes, matrix, and goal in the copilot.
            It will set up a project, draft a method, and predict the chromatogram.
          </p>
          <p className="text-[12px] text-muted-foreground">
            Try: <span className="chip-mono">caffeine in coffee on a C18, MS-friendly</span>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="@container h-full overflow-y-auto bg-surface-2">
      <div className="min-h-full">
        <div className="max-w-[1100px] mx-auto px-6 @[720px]:px-10 pt-12 pb-20">
          {/* Project header — editorial, no chrome */}
          <div className="flex items-start gap-4 mb-12">
            <div className="flex-1 min-w-0">
              <input
                value={project.name}
                onChange={(e) =>
                  useWorkspace.setState((s) => ({
                    projects: { ...s.projects, [project.id]: { ...s.projects[project.id], name: e.target.value } },
                  }))
                }
                className="font-display text-[34px] tracking-tight leading-[1.1] w-full bg-transparent focus:outline-none -ml-1 px-1 rounded hover:bg-surface focus:bg-surface transition-colors"
              />
              <div className="flex items-center gap-2 text-[12px] text-muted-foreground mt-2">
                {project.brief.matrix && <span>{project.brief.matrix}</span>}
                {project.brief.matrix && project.brief.analytes.length > 0 && <span>·</span>}
                {project.brief.analytes.length > 0 && (
                  <span>{project.brief.analytes.length} analyte{project.brief.analytes.length === 1 ? "" : "s"}</span>
                )}
                {projectMethods.length > 0 && (
                  <>
                    <span>·</span>
                    <span>{projectMethods.length} method version{projectMethods.length === 1 ? "" : "s"}</span>
                  </>
                )}
              </div>
            </div>
            {method && (
              <div className="flex items-center gap-1.5 pt-2">
                {projectMethods.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="h-7 text-[12.5px] gap-1 rounded">
                        {method.name}
                        <CaretDown className="size-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {projectMethods
                        .sort((a, b) => b.version - a.version)
                        .map((m) => (
                          <DropdownMenuItem key={m.id} onClick={() => setActiveMethod(project.id, m.id)} className="text-[12.5px]">
                            {m.name}
                          </DropdownMenuItem>
                        ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-[12px] gap-1.5 rounded"
                  onClick={() =>
                    setPendingPrompt(
                      `Explain the choices in the active method (${method.name}) in exactly 3 short bullets: column, mobile phase + gradient, and detection. Reference concrete numbers. No preamble.`
                    )
                  }
                >
                  <Question className="size-3" /> Why this method?
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-[12px] gap-1.5 rounded"
                  onClick={() => {
                    const newId = updateMethod(method.id, {}, true);
                    setActiveMethod(project.id, newId);
                  }}
                >
                  <GitBranch className="size-3" /> Fork
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-12">
            <div className="grid grid-cols-1 @[640px]:grid-cols-[1.6fr_1fr] gap-x-12 gap-y-8">
              <BriefCard project={project} />
              <AnalyteCard project={project} />
            </div>

            {!method ? (
              <NoMethodCard />
            ) : (
              <>
                <MethodConditionsCard method={method} />

                <div className="grid grid-cols-1 @[820px]:grid-cols-2 gap-x-10 gap-y-8">
                  <GradientCard method={method} />
                  <ChromatogramCard method={method} />
                </div>

                {(method.rationale || method.warnings.length > 0 || method.sample_prep) && (
                  <div className="grid grid-cols-1 @[640px]:grid-cols-2 gap-x-12 gap-y-8">
                    {method.sample_prep && <NoteCard title="Sample prep" body={method.sample_prep} />}
                    {method.rationale && <NoteCard title="Rationale" body={method.rationale} />}
                    {method.warnings.length > 0 && <WarningsCard warnings={method.warnings} />}
                  </div>
                )}

                <RunsCard projectId={project.id} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ---------------- Section primitive (replaces boxed Card chrome) ---------------- */

const Card = ({ title, action, children, className }: { title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) => (
  <section className={cn("group/section", className)}>
    {(title || action) && (
      <div className="flex items-baseline justify-between gap-3 mb-3 pb-2 border-b border-border/60">
        {title && (
          <div className="flex items-baseline gap-2.5">
            <span className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
              {title}
            </span>
          </div>
        )}
        {action}
      </div>
    )}
    <div>{children}</div>
  </section>
);

const NoMethodCard = () => (
  <div className="border-y border-border/60 py-12 text-center">
    <div className="font-display text-[20px]">No method yet</div>
    <p className="text-[13px] text-muted-foreground mt-2">
      Ask the copilot: <span className="chip-mono">draft a method for this brief</span>
    </p>
  </div>
);

const BriefCard = ({ project }: { project: Project }) => {
  const updateBrief = useWorkspace((s) => s.updateBrief);
  return (
    <Card title="Brief">
      <div className="space-y-4">
        <FormField
          label="Goal"
          hint="What does success look like? Be specific about resolution, runtime, and detection."
        >
          <textarea
            value={project.brief.goal}
            onChange={(e) => updateBrief(project.id, { goal: e.target.value })}
            placeholder="e.g. baseline-resolve caffeine and theobromine in <8 min, MS-friendly"
            rows={3}
            className="w-full text-[13px] leading-relaxed rounded-md border border-input bg-background px-3 py-2 resize-y focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/70"
          />
        </FormField>
        <FormField label="Sample matrix" hint="The medium your analytes are dissolved in.">
          <div className="flex gap-1.5 items-center">
            <Input
              value={project.brief.matrix}
              onChange={(e) => updateBrief(project.id, { matrix: e.target.value })}
              placeholder="brewed coffee, plasma, tablet extract…"
              className="h-9 text-[13px]"
              list="matrix-presets"
            />
            <datalist id="matrix-presets">
              {MATRIX_PRESETS.map((m) => <option key={m} value={m} />)}
            </datalist>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-9 px-2.5 text-xs gap-1 shrink-0">
                  Presets <CaretDown className="size-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-64 overflow-y-auto">
                {MATRIX_PRESETS.map((m) => (
                  <DropdownMenuItem key={m} onClick={() => updateBrief(project.id, { matrix: m })} className="text-[12.5px]">
                    {m}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </FormField>
      </div>
    </Card>
  );
};

const AnalyteCard = ({ project }: { project: Project }) => {
  const updateBrief = useWorkspace((s) => s.updateBrief);
  const setAnalytes = (analytes: typeof project.brief.analytes) => updateBrief(project.id, { analytes });
  const count = project.brief.analytes.length;

  return (
    <Card
      title="Analytes"
      action={
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-7 text-[12px] gap-1 px-2">
              <Plus className="size-3" /> Add
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuItem onClick={() => setAnalytes([...project.brief.analytes, { name: "" }])} className="text-[12.5px]">
              <Plus className="size-3 mr-1.5" /> Empty row
            </DropdownMenuItem>
            <div className="text-[11px] text-muted-foreground font-medium px-2 pt-2 pb-1">Common</div>
            {COMMON_ANALYTES.map((a) => (
              <DropdownMenuItem
                key={a.name}
                onClick={() => setAnalytes([...project.brief.analytes, a])}
                className="text-[12.5px]"
              >
                {a.name}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      }
    >
      {count === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface-2/40 px-4 py-6 text-center">
          <p className="text-[12.5px] text-muted-foreground">No analytes yet.</p>
          <p className="text-[11.5px] text-muted-foreground/80 mt-1">
            Click <span className="font-medium text-foreground">Add</span> or describe them in the copilot.
          </p>
        </div>
      ) : (
        <div>
          <div className="grid grid-cols-[1fr_88px_24px] items-center gap-x-2 px-1.5 pb-1.5 mb-1 border-b border-border">
            <span className="text-[11px] font-medium text-muted-foreground">Name</span>
            <span className="text-[11px] font-medium text-muted-foreground text-right">λmax (nm)</span>
            <span />
          </div>
          <div className="space-y-1">
            {project.brief.analytes.map((a, i) => (
              <div key={i} className="grid grid-cols-[1fr_88px_24px] items-center gap-x-2 group">
                <input
                  value={a.name}
                  onChange={(e) => {
                    const next = [...project.brief.analytes];
                    next[i] = { ...a, name: e.target.value };
                    setAnalytes(next);
                  }}
                  className="h-8 px-2.5 text-[13px] rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/60"
                  placeholder="Analyte name"
                />
                <div className="relative">
                  <input
                    inputMode="numeric"
                    value={a.lambda_max_nm?.toString() ?? ""}
                    onChange={(e) => {
                      const next = [...project.brief.analytes];
                      next[i] = { ...a, lambda_max_nm: e.target.value ? Number(e.target.value) : null };
                      setAnalytes(next);
                    }}
                    className="h-8 w-full pl-2 pr-7 text-[13px] tnum text-right rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/60"
                    placeholder="—"
                  />
                  <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10.5px] text-muted-foreground">nm</span>
                </div>
                <button
                  onClick={() => setAnalytes(project.brief.analytes.filter((_, j) => j !== i))}
                  className="size-6 grid place-items-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/5 opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label="Remove"
                >
                  <Trash className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
          <p className="mt-2.5 text-[11px] text-muted-foreground">
            {count} {count === 1 ? "analyte" : "analytes"} · ask the copilot to enrich pKa & logP
          </p>
        </div>
      )}
    </Card>
  );
};

const FormField = ({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) => (
  <div className="space-y-1.5">
    <div className="flex items-baseline justify-between gap-2">
      <label className="text-[12px] font-medium text-foreground">{label}</label>
      {hint && <span className="text-[11px] text-muted-foreground/80 truncate">{hint}</span>}
    </div>
    {children}
  </div>
);

const MethodConditionsCard = ({ method }: { method: Method }) => {
  const updateMethod = useWorkspace((s) => s.updateMethod);
  const inventory = useWorkspace((s) => s.inventory);
  const patch = (p: Partial<Method>) => updateMethod(method.id, p as any, false);

  return (
    <Card title="Method conditions">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat label="Mode" value={method.mode} onChange={(v) => patch({ mode: v })} />
        <Stat label="Flow" value={String(method.flow_rate_ml_min)} unit="mL/min" mono onChange={(v) => patch({ flow_rate_ml_min: Number(v) })} />
        <Stat label="Temp" value={String(method.column_temperature_c)} unit="°C" mono onChange={(v) => patch({ column_temperature_c: Number(v) })} />
        <Stat label="Injection" value={String(method.injection_volume_ul)} unit="µL" mono onChange={(v) => patch({ injection_volume_ul: Number(v) })} />
        <Stat label="Run time" value={String(method.run_time_min)} unit="min" mono onChange={(v) => patch({ run_time_min: Number(v) })} />
        <Stat label="λ" value={method.detection.wavelength_nm} unit="nm" mono onChange={(v) => patch({ detection: { ...method.detection, wavelength_nm: v } })} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 pt-3 border-t border-border">
        <SelectField
          label="Column"
          value={method.column.choice}
          options={inventory.columns}
          onChange={(v) => patch({ column: { ...method.column, choice: v } })}
        />
        <SelectField
          label="Mobile A"
          value={method.mobile_phase.a}
          options={inventory.solvents}
          onChange={(v) => patch({ mobile_phase: { ...method.mobile_phase, a: v } })}
        />
        <SelectField
          label="Mobile B"
          value={method.mobile_phase.b}
          options={inventory.solvents}
          onChange={(v) => patch({ mobile_phase: { ...method.mobile_phase, b: v } })}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        <SelectField
          label="Detector"
          value={method.detection.detector}
          options={inventory.detector ? [inventory.detector, "DAD (UV/Vis)", "MS — single quad", "MS — triple quad (MS/MS)"] : ["DAD (UV/Vis)", "MS — single quad"]}
          onChange={(v) => patch({ detection: { ...method.detection, detector: v } })}
        />
        <Field label="Buffer notes">
          <Input
            value={method.mobile_phase.buffer_notes ?? ""}
            onChange={(e) => patch({ mobile_phase: { ...method.mobile_phase, buffer_notes: e.target.value } })}
            className="h-8 text-sm"
            placeholder="e.g. 10 mM ammonium formate, pH 3.5"
          />
        </Field>
      </div>
    </Card>
  );
};

const Stat = ({
  label,
  value,
  unit,
  mono,
  onChange,
}: {
  label: string;
  value: string;
  unit?: string;
  mono?: boolean;
  onChange?: (v: string) => void;
}) => (
  <div className="space-y-1">
    <div className="text-[11px] text-muted-foreground font-medium">{label}</div>
    <div className="flex items-baseline gap-1">
      <input
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className={cn(
          "min-w-0 flex-1 h-7 px-1.5 text-[13px] rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring",
          mono && "tnum"
        )}
      />
      {unit && <span className="text-[10.5px] text-muted-foreground tnum">{unit}</span>}
    </div>
  </div>
);

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="space-y-1">
    <div className="text-[11px] text-muted-foreground font-medium">{label}</div>
    {children}
  </div>
);

const SelectField = ({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) => (
  <Field label={label}>
    <div className="flex gap-1">
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="h-8 text-[13px]" />
      {options.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 px-2 text-xs" aria-label={`Pick ${label}`}>
              <CaretDown className="size-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto w-64">
            {options.map((o) => (
              <DropdownMenuItem key={o} onClick={() => onChange(o)} className="text-xs font-mono">
                {o}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  </Field>
);

/* ---------------- Gradient ---------------- */

const GradientCard = ({ method }: { method: Method }) => {
  const updateMethod = useWorkspace((s) => s.updateMethod);
  const sorted = [...method.gradient].sort((a, b) => a.time_min - b.time_min);
  const setG = (g: GradientPoint[]) => updateMethod(method.id, { gradient: g }, false);

  return (
    <Card
      title="Gradient · %B vs time"
      action={
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-[11px] gap-1 px-1.5"
          onClick={() =>
            setG([
              ...sorted,
              {
                time_min: (sorted.at(-1)?.time_min ?? 0) + 1,
                percent_b: sorted.at(-1)?.percent_b ?? 50,
              },
            ])
          }
        >
          <Plus className="size-3" /> Point
        </Button>
      }
    >
      <GradientChart points={sorted} onChange={setG} />
      <div className="mt-3 border border-border rounded-md overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_28px] text-[11px] text-muted-foreground font-medium bg-surface-2 border-b border-border">
          <div className="px-2.5 py-1">Time (min)</div>
          <div className="px-2.5 py-1">% B</div>
          <div />
        </div>
        {sorted.map((p, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_28px] border-b border-border last:border-b-0 text-xs font-mono">
            <input
              type="number"
              step="0.1"
              value={p.time_min}
              onChange={(e) => {
                const next = [...sorted];
                next[i] = { ...p, time_min: Number(e.target.value) };
                setG(next);
              }}
              className="px-2.5 py-1 bg-transparent focus:outline-none focus:bg-surface-2"
            />
            <input
              type="number"
              step="1"
              value={p.percent_b}
              onChange={(e) => {
                const next = [...sorted];
                next[i] = { ...p, percent_b: Number(e.target.value) };
                setG(next);
              }}
              className="px-2.5 py-1 bg-transparent focus:outline-none focus:bg-surface-2"
            />
            <button
              className="grid place-items-center text-muted-foreground hover:text-destructive"
              onClick={() => setG(sorted.filter((_, j) => j !== i))}
              aria-label="Remove"
            >
              <Trash className="size-3" />
            </button>
          </div>
        ))}
      </div>
    </Card>
  );
};

const GradientChart = ({ points, onChange }: { points: GradientPoint[]; onChange: (p: GradientPoint[]) => void }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const [hover, setHover] = useState<{ t: number; b: number; px: number; py: number } | null>(null);
  const W = 720, H = 240;
  const PAD = { top: 14, right: 16, bottom: 38, left: 44 };
  const tMax = useMemo(() => Math.max(1, ...points.map((p) => p.time_min)), [points]);
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const sx = (t: number) => PAD.left + (t / tMax) * innerW;
  const sy = (b: number) => PAD.top + innerH - (b / 100) * innerH;
  const invX = (px: number) => Math.max(0, Math.min(tMax, ((px - PAD.left) / innerW) * tMax));
  const invY = (py: number) => Math.max(0, Math.min(100, (1 - (py - PAD.top) / innerH) * 100));

  const percentBAt = (t: number) => {
    if (points.length === 0) return 0;
    const sorted = [...points].sort((a, b) => a.time_min - b.time_min);
    if (t <= sorted[0].time_min) return sorted[0].percent_b;
    for (let i = 0; i < sorted.length - 1; i++) {
      const a = sorted[i], b = sorted[i + 1];
      if (t >= a.time_min && t <= b.time_min) {
        const f = (t - a.time_min) / Math.max(1e-9, b.time_min - a.time_min);
        return a.percent_b + f * (b.percent_b - a.percent_b);
      }
    }
    return sorted.at(-1)!.percent_b;
  };

  const path = points.length ? "M " + points.map((p) => `${sx(p.time_min)},${sy(p.percent_b)}`).join(" L ") : "";
  const areaPath = points.length ? `${path} L ${sx(tMax)},${sy(0)} L ${sx(0)},${sy(0)} Z` : "";

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    if (drag !== null) {
      const next = [...points];
      next[drag] = { time_min: Number(invX(px).toFixed(2)), percent_b: Number(invY(py).toFixed(0)) };
      onChange(next);
      return;
    }
    if (px < PAD.left || px > PAD.left + innerW || py < PAD.top || py > PAD.top + innerH) {
      setHover(null);
      return;
    }
    const t = invX(px);
    const b = percentBAt(t);
    setHover({ t, b, px: sx(t), py: sy(b) });
  };

  return (
    <div className="relative">
      <ChartFrame
        svgRef={svgRef}
        width={W}
        height={H}
        padding={PAD}
        x={{ min: 0, max: tMax, title: "Time", unit: "min" }}
        y={{ min: 0, max: 100, title: "Mobile phase B", unit: "%", ticks: [0, 25, 50, 75, 100] }}
        onMouseMove={onMove}
        onMouseLeave={() => { setHover(null); setDrag(null); }}
        onMouseUp={() => setDrag(null)}
        selectable={false}
        overlay={
          hover && drag === null ? (
            <g pointerEvents="none">
              <line
                x1={hover.px}
                x2={hover.px}
                y1={PAD.top}
                y2={PAD.top + innerH}
                stroke="hsl(var(--accent-clay))"
                strokeWidth={1}
                strokeDasharray="3 3"
                opacity={0.55}
              />
              <circle cx={hover.px} cy={hover.py} r={3.5} fill="hsl(var(--accent-clay))" />
            </g>
          ) : null
        }
      >
        <path d={areaPath} fill="hsl(var(--accent-clay))" opacity={0.08} />
        <path d={path} fill="none" stroke="hsl(var(--accent-clay))" strokeWidth={1.75} strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={sx(p.time_min)}
            cy={sy(p.percent_b)}
            r={drag === i ? 6 : 4.5}
            fill="hsl(var(--background))"
            stroke="hsl(var(--accent-clay))"
            strokeWidth={1.75}
            className="cursor-grab active:cursor-grabbing"
            onMouseDown={() => setDrag(i)}
          />
        ))}
      </ChartFrame>
      {hover && drag === null && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover shadow-pop px-2 py-1.5 text-[11px] tnum"
          style={{
            left: `calc(${(hover.px / W) * 100}% + 8px)`,
            top: `calc(${(hover.py / H) * 100}% - 8px)`,
            transform: "translateY(-100%)",
          }}
        >
          <div className="text-muted-foreground">t = <span className="text-foreground font-medium">{hover.t.toFixed(2)} min</span></div>
          <div className="text-muted-foreground">%B = <span className="text-foreground font-medium">{hover.b.toFixed(1)}%</span></div>
        </div>
      )}
      <div className="mt-2 flex items-center justify-between">
        <ChartLegend items={[{ color: "hsl(var(--accent-clay))", label: "Mobile phase B" }]} />
        <span className="text-[10.5px] text-muted-foreground">drag points · hover for value</span>
      </div>
    </div>
  );
};

/* ---------------- Chromatogram ---------------- */

const ChromatogramCard = ({ method }: { method: Method }) => {
  const runs = useWorkspace((s) => s.runs);
  const methodRuns = Object.values(runs)
    .filter((r) => r.methodId === method.id)
    .sort((a, b) => b.createdAt - a.createdAt);

  return (
    <Card title="Predicted chromatogram">
      {methodRuns.length === 0 ? (
        <div className="h-[220px] grid place-items-center text-[12.5px] text-muted-foreground border border-dashed border-border rounded-md bg-surface-2/40">
          Ask the copilot to predict the chromatogram.
        </div>
      ) : (
        <ChromatogramChart run={methodRuns[0]} method={method} />
      )}
    </Card>
  );
};

const ChromatogramChart = ({ run, method }: { run: import("@/studio/types/hplc").Run; method: Method }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ t: number; signal: number; px: number; py: number; nearestPeak?: import("@/studio/types/hplc").PredictedPeak } | null>(null);
  const W = 720, H = 260;
  const PAD = { top: 18, right: 16, bottom: 38, left: 48 };
  const total = run.predicted.total_time_min;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const signalAt = (t: number) => {
    let s = 0;
    for (const p of run.predicted.peaks) {
      const sigma = Math.max(0.02, p.width_min / 4);
      s += p.height * Math.exp(-Math.pow(t - p.rt_min, 2) / (2 * sigma * sigma));
    }
    return Math.min(1.05, s);
  };

  // Build the trace
  const N = 600;
  const samples: { t: number; s: number }[] = [];
  let yMax = 0;
  for (let i = 0; i <= N; i++) {
    const t = (i / N) * total;
    const s = signalAt(t);
    samples.push({ t, s });
    if (s > yMax) yMax = s;
  }
  yMax = Math.max(0.05, yMax * 1.15);

  const sx = (t: number) => PAD.left + (t / total) * innerW;
  const sy = (s: number) => PAD.top + innerH - (s / yMax) * innerH;
  const invX = (px: number) => Math.max(0, Math.min(total, ((px - PAD.left) / innerW) * total));

  const path = samples.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.t)},${sy(p.s)}`).join(" ");

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    if (px < PAD.left || px > PAD.left + innerW || py < PAD.top || py > PAD.top + innerH) {
      setHover(null);
      return;
    }
    const t = invX(px);
    const s = signalAt(t);
    let nearest = run.predicted.peaks[0];
    let best = Infinity;
    for (const p of run.predicted.peaks) {
      const d = Math.abs(p.rt_min - t);
      if (d < best) { best = d; nearest = p; }
    }
    setHover({ t, signal: s, px: sx(t), py: sy(s), nearestPeak: best < (nearest.width_min || 0.5) ? nearest : undefined });
  };

  return (
    <div className="relative">
      <ChartFrame
        svgRef={svgRef}
        width={W}
        height={H}
        padding={PAD}
        x={{ min: 0, max: total, title: "Retention time", unit: "min" }}
        y={{ min: 0, max: yMax, title: "Detector response", unit: "AU", decimals: 2 }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        overlay={
          <g pointerEvents="none">
            {/* Peak retention lines */}
            {run.predicted.peaks.map((p, i) => (
              <line
                key={`pr-${i}`}
                x1={sx(p.rt_min)}
                x2={sx(p.rt_min)}
                y1={sy(p.height)}
                y2={PAD.top + innerH}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="2 3"
                opacity={0.35}
              />
            ))}
            {/* Peak labels */}
            {run.predicted.peaks.map((p, i) => (
              <g key={`pl-${i}`}>
                <text
                  x={sx(p.rt_min)}
                  y={sy(p.height) - 8}
                  fontSize="10.5"
                  textAnchor="middle"
                  fill="hsl(var(--foreground))"
                  opacity={0.85}
                >
                  {p.name}
                </text>
                <text
                  x={sx(p.rt_min)}
                  y={sy(p.height) - 20}
                  fontSize="9.5"
                  textAnchor="middle"
                  fill="hsl(var(--muted-foreground))"
                >
                  {p.rt_min.toFixed(2)}
                </text>
              </g>
            ))}
            {hover && (
              <g>
                <line
                  x1={hover.px}
                  x2={hover.px}
                  y1={PAD.top}
                  y2={PAD.top + innerH}
                  stroke="hsl(var(--accent-clay))"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  opacity={0.6}
                />
                <circle cx={hover.px} cy={hover.py} r={3} fill="hsl(var(--accent-clay))" />
              </g>
            )}
          </g>
        }
      >
        <path d={path} fill="none" stroke="hsl(var(--foreground))" strokeWidth={1.4} strokeLinejoin="round" />
      </ChartFrame>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover shadow-pop px-2 py-1.5 text-[11px] tnum min-w-[120px]"
          style={{
            left: `calc(${(hover.px / W) * 100}% + 8px)`,
            top: `calc(${(hover.py / H) * 100}% - 8px)`,
            transform: "translateY(-100%)",
          }}
        >
          <div className="text-muted-foreground">RT = <span className="text-foreground font-medium">{hover.t.toFixed(2)} min</span></div>
          <div className="text-muted-foreground">Signal = <span className="text-foreground font-medium">{hover.signal.toFixed(3)}</span></div>
          {hover.nearestPeak && (
            <div className="mt-1 pt-1 border-t border-border text-[10.5px]">
              <span className="text-muted-foreground">Nearest peak:</span>{" "}
              <span className="text-foreground font-medium">{hover.nearestPeak.name}</span>
            </div>
          )}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between">
        <ChartLegend
          items={[
            { color: "hsl(var(--foreground))", label: `${method.detection.detector || "Detector"} @ ${method.detection.wavelength_nm} nm` },
            { color: "hsl(var(--muted-foreground))", label: "Peak RT", dashed: true },
          ]}
        />
        <span className="text-[10.5px] text-muted-foreground">{run.predicted.peaks.length} peaks · {total.toFixed(1)} min total</span>
      </div>

      {/* Peak table */}
      <div className="mt-3 border border-border rounded-md overflow-hidden">
        <div className="grid grid-cols-[1fr_70px_70px_70px] gap-x-2 px-2.5 py-1.5 bg-surface-2 border-b border-border text-[11px] font-medium text-muted-foreground">
          <div>Peak</div>
          <div className="text-right">RT (min)</div>
          <div className="text-right">Width (min)</div>
          <div className="text-right">Height</div>
        </div>
        {run.predicted.peaks.map((p, i) => (
          <div key={i} className="grid grid-cols-[1fr_70px_70px_70px] gap-x-2 px-2.5 py-1 text-[12.5px] border-b border-border last:border-b-0 hover:bg-surface-2/60">
            <div className="truncate">{p.name}</div>
            <div className="tnum text-right">{p.rt_min.toFixed(2)}</div>
            <div className="tnum text-right">{p.width_min.toFixed(2)}</div>
            <div className="tnum text-right text-muted-foreground">{p.height.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const NoteCard = ({ title, body }: { title: string; body: string }) => (
  <Card title={title}>
    <p className="text-sm whitespace-pre-wrap leading-relaxed">{body}</p>
  </Card>
);

const WarningsCard = ({ warnings }: { warnings: string[] }) => (
  <Card title="Warnings">
    <div className="space-y-1.5">
      {warnings.map((w, i) => (
        <div key={i} className="flex gap-2 items-start text-xs border-l-2 border-l-warning bg-surface-2 p-2 rounded-r">
          <Warning className="size-3.5 text-warning shrink-0 mt-0.5" />
          <span>{w}</span>
        </div>
      ))}
    </div>
  </Card>
);

const RunsCard = ({ projectId }: { projectId: string }) => {
  const runs = useWorkspace((s) => s.runs);
  const methods = useWorkspace((s) => s.methods);
  const projectRuns = Object.values(runs)
    .filter((r) => methods[r.methodId]?.projectId === projectId)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 8);

  if (projectRuns.length === 0) return null;

  return (
    <Card title="Run history">
      <div className="grid grid-cols-[110px_1fr_60px_1fr] text-[11px] text-muted-foreground font-medium border-b border-border pb-1.5 mb-1">
        <div>When</div>
        <div>Method</div>
        <div>Peaks</div>
        <div>Notes</div>
      </div>
      {projectRuns.map((r) => {
        const m = methods[r.methodId];
        return (
          <div key={r.id} className="grid grid-cols-[110px_1fr_60px_1fr] text-xs py-1 border-b border-border last:border-b-0">
            <div className="font-mono text-muted-foreground">
              {new Date(r.createdAt).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
            </div>
            <div className="font-mono">{m?.name ?? "—"}</div>
            <div className="font-mono">{r.predicted.peaks.length}</div>
            <div className="text-muted-foreground truncate">{r.notes ?? ""}</div>
          </div>
        );
      })}
    </Card>
  );
};

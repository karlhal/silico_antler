import { useState } from "react";
import { useWorkspace } from "@/studio/store/workspace";
import { Button } from "@/studio/components/ui/button";
import { Check, Plus, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import {
  COLUMN_PRESETS,
  SOLVENT_PRESETS,
  PUMP_PRESETS,
  DETECTOR_PRESETS,
} from "@/studio/lib/presets";

interface HardwareViewProps {
  initialSection?: "columns" | "solvents" | "instrument";
  onClose?: () => void;
}

export const HardwareView = ({ initialSection = "columns", onClose }: HardwareViewProps) => {
  const inventory = useWorkspace((s) => s.inventory);
  const setInventory = useWorkspace((s) => s.setInventory);
  const addColumn = useWorkspace((s) => s.addColumn);
  const removeColumn = useWorkspace((s) => s.removeColumn);
  const addSolvent = useWorkspace((s) => s.addSolvent);
  const removeSolvent = useWorkspace((s) => s.removeSolvent);

  const [section, setSection] = useState<"columns" | "solvents" | "instrument">(initialSection);
  const [customCol, setCustomCol] = useState("");
  const [customSol, setCustomSol] = useState("");

  const colByCat = COLUMN_PRESETS.reduce<Record<string, typeof COLUMN_PRESETS>>((acc, p) => {
    (acc[p.category] ||= []).push(p);
    return acc;
  }, {});
  const solByCat = SOLVENT_PRESETS.reduce<Record<string, typeof SOLVENT_PRESETS>>((acc, p) => {
    (acc[p.category] ||= []).push(p);
    return acc;
  }, {});

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="shrink-0 px-6 pt-6 pb-4 border-b border-border flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <h2 className="font-display text-[20px] tracking-[-0.02em] leading-tight">Hardware & solvents</h2>
          <p className="text-[12.5px] text-muted-foreground mt-1.5 leading-relaxed">
            Configure the columns, solvents, and instrument available in your lab.
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 shrink-0" onClick={onClose} aria-label="Close">
            <X className="size-4" />
          </Button>
        )}
      </div>

      {/* Section tabs */}
      <div className="shrink-0 flex items-center px-6 gap-0.5 py-2 border-b border-border bg-surface">
        {(["columns", "solvents", "instrument"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSection(s)}
            className={cn(
              "px-3 h-7 rounded-md text-[12.5px] font-medium capitalize transition-colors",
              section === s
                ? "bg-background text-foreground border border-border"
                : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
            )}
          >
            {s}
            {s === "columns" && inventory.columns.length > 0 && (
              <span className="ml-1.5 text-[11px] text-muted-foreground tnum">{inventory.columns.length}</span>
            )}
            {s === "solvents" && inventory.solvents.length > 0 && (
              <span className="ml-1.5 text-[11px] text-muted-foreground tnum">{inventory.solvents.length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 text-[13px]">
        {section === "columns" && (
          <>
            {inventory.columns.length > 0 && (
              <section>
                <SectionHeader>In your lab</SectionHeader>
                <div className="flex flex-wrap gap-1.5">
                  {inventory.columns.map((c) => (
                    <Chip key={c} onRemove={() => removeColumn(c)}>{c}</Chip>
                  ))}
                </div>
              </section>
            )}
            {Object.entries(colByCat).map(([cat, items]) => (
              <section key={cat}>
                <SectionHeader>{cat}</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5">
                  {items.map((p) => {
                    const owned = inventory.columns.includes(p.label);
                    return (
                      <PresetRow
                        key={p.id}
                        label={p.label}
                        selected={owned}
                        onClick={() => (owned ? removeColumn(p.label) : addColumn(p.label))}
                      />
                    );
                  })}
                </div>
              </section>
            ))}
            <CustomAdd
              placeholder="Custom column (e.g. C18 75×2.1 1.7µm)"
              value={customCol}
              onChange={setCustomCol}
              onSubmit={() => {
                if (customCol.trim()) {
                  addColumn(customCol.trim());
                  setCustomCol("");
                }
              }}
            />
          </>
        )}

        {section === "solvents" && (
          <>
            {inventory.solvents.length > 0 && (
              <section>
                <SectionHeader>In your lab</SectionHeader>
                <div className="flex flex-wrap gap-1.5">
                  {inventory.solvents.map((c) => (
                    <Chip key={c} onRemove={() => removeSolvent(c)}>{c}</Chip>
                  ))}
                </div>
              </section>
            )}
            {Object.entries(solByCat).map(([cat, items]) => (
              <section key={cat}>
                <SectionHeader>{cat}</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5">
                  {items.map((p) => {
                    const owned = inventory.solvents.includes(p.label);
                    return (
                      <PresetRow
                        key={p.id}
                        label={p.label}
                        selected={owned}
                        onClick={() => (owned ? removeSolvent(p.label) : addSolvent(p.label))}
                      />
                    );
                  })}
                </div>
              </section>
            ))}
            <CustomAdd
              placeholder="Custom solvent (e.g. 5 mM TEA pH 3)"
              value={customSol}
              onChange={setCustomSol}
              onSubmit={() => {
                if (customSol.trim()) {
                  addSolvent(customSol.trim());
                  setCustomSol("");
                }
              }}
            />
          </>
        )}

        {section === "instrument" && (
          <>
            <section>
              <SectionHeader>Pump</SectionHeader>
              <div className="space-y-0.5">
                {PUMP_PRESETS.map((p) => (
                  <RadioRow
                    key={p}
                    label={p}
                    selected={inventory.pump === p}
                    onClick={() => setInventory({ pump: inventory.pump === p ? "" : p })}
                  />
                ))}
              </div>
              <input
                value={inventory.pump && !PUMP_PRESETS.includes(inventory.pump) ? inventory.pump : ""}
                onChange={(e) => setInventory({ pump: e.target.value })}
                placeholder="Other pump…"
                className="mt-2 w-full h-8 px-2.5 text-[13px] rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </section>

            <section>
              <SectionHeader>Detector</SectionHeader>
              <div className="space-y-0.5">
                {DETECTOR_PRESETS.map((d) => (
                  <RadioRow
                    key={d}
                    label={d}
                    selected={inventory.detector === d}
                    onClick={() => setInventory({ detector: inventory.detector === d ? "" : d })}
                  />
                ))}
              </div>
              <input
                value={inventory.detector && !DETECTOR_PRESETS.includes(inventory.detector) ? inventory.detector : ""}
                onChange={(e) => setInventory({ detector: e.target.value })}
                placeholder="Other detector…"
                className="mt-2 w-full h-8 px-2.5 text-[13px] rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </section>
          </>
        )}
      </div>
    </div>
  );
};

const SectionHeader = ({ children }: { children: React.ReactNode }) => (
  <div className="text-[12px] font-medium text-foreground/75 mb-2">{children}</div>
);

const Chip = ({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) => (
  <span className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-2 pl-2.5 pr-1 py-0.5 text-[12px] text-foreground/85">
    {children}
    <button onClick={onRemove} className="text-muted-foreground hover:text-destructive ml-0.5" aria-label="Remove">
      <X className="size-3" />
    </button>
  </span>
);

const PresetRow = ({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    className={cn(
      "w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] hover:bg-sidebar-accent transition-colors",
      selected ? "text-foreground" : "text-muted-foreground"
    )}
  >
    <span
      className={cn(
        "size-3.5 grid place-items-center rounded-[3px] border shrink-0",
        selected ? "bg-primary border-primary text-primary-foreground" : "border-border"
      )}
    >
      {selected && <Check className="size-2.5" strokeWidth={3} />}
    </span>
    <span className="truncate">{label}</span>
  </button>
);

const RadioRow = ({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    className={cn(
      "w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] hover:bg-sidebar-accent transition-colors",
      selected ? "text-foreground" : "text-muted-foreground"
    )}
  >
    <span
      className={cn(
        "size-3.5 rounded-full border grid place-items-center shrink-0",
        selected ? "border-primary" : "border-border"
      )}
    >
      {selected && <span className="size-2 rounded-full bg-primary" />}
    </span>
    <span className={selected ? "font-medium" : ""}>{label}</span>
  </button>
);

const CustomAdd = ({
  placeholder,
  value,
  onChange,
  onSubmit,
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
}) => (
  <div className="flex gap-1.5 pt-1">
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && onSubmit()}
      placeholder={placeholder}
      className="flex-1 h-8 px-2.5 text-[13px] rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
    />
    <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={onSubmit} aria-label="Add">
      <Plus className="size-3.5" />
    </Button>
  </div>
);

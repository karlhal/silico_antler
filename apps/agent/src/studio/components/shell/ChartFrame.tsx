import { useMemo } from "react";

export interface AxisConfig {
  min: number;
  max: number;
  title: string;
  unit?: string;
  /** Optional explicit tick values; if omitted we compute "nice" ticks. */
  ticks?: number[];
  /** Number of decimal places for tick labels (default: auto). */
  decimals?: number;
}

export interface ChartFrameProps {
  width: number;
  height: number;
  padding?: { top: number; right: number; bottom: number; left: number };
  x: AxisConfig;
  y: AxisConfig;
  /** SVG content drawn inside the plotting area. */
  children: React.ReactNode;
  /** Optional overlay drawn on top of the plot (e.g. tooltips, crosshair). */
  overlay?: React.ReactNode;
  /** Mouse handlers proxied to the SVG root, useful for hover tooltips. */
  onMouseMove?: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseLeave?: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseDown?: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseUp?: (e: React.MouseEvent<SVGSVGElement>) => void;
  svgRef?: React.Ref<SVGSVGElement>;
  className?: string;
  /** Disable selection — useful while dragging. */
  selectable?: boolean;
}

/** Compute "nice" tick values for the given range, targeting ~count ticks. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (max <= min) return [min];
  const range = max - min;
  const rough = range / (count - 1);
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  let step: number;
  if (norm < 1.5) step = 1 * mag;
  else if (norm < 3) step = 2 * mag;
  else if (norm < 7) step = 5 * mag;
  else step = 10 * mag;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + 1e-9; v += step) {
    ticks.push(Number(v.toFixed(10)));
  }
  return ticks;
}

function formatTick(v: number, decimals?: number) {
  if (decimals !== undefined) return v.toFixed(decimals);
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(2).replace(/\.?0+$/, "");
}

export const ChartFrame = ({
  width: W,
  height: H,
  padding = { top: 12, right: 12, bottom: 34, left: 44 },
  x,
  y,
  children,
  overlay,
  onMouseMove,
  onMouseLeave,
  onMouseDown,
  onMouseUp,
  svgRef,
  className,
  selectable = true,
}: ChartFrameProps) => {
  const innerW = W - padding.left - padding.right;
  const innerH = H - padding.top - padding.bottom;

  const xTicks = useMemo(() => x.ticks ?? niceTicks(x.min, x.max, 6), [x.min, x.max, x.ticks]);
  const yTicks = useMemo(() => y.ticks ?? niceTicks(y.min, y.max, 5), [y.min, y.max, y.ticks]);

  const sx = (v: number) => padding.left + ((v - x.min) / (x.max - x.min)) * innerW;
  const sy = (v: number) => padding.top + innerH - ((v - y.min) / (y.max - y.min)) * innerH;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      className={`${className ?? ""} ${selectable ? "" : "select-none"}`.trim()}
      style={{ display: "block", width: "100%", height: H, fontVariantNumeric: "tabular-nums" }}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
    >
      {/* Plot background */}
      <rect
        x={padding.left}
        y={padding.top}
        width={innerW}
        height={innerH}
        fill="hsl(var(--surface))"
      />

      {/* Y gridlines + ticks */}
      {yTicks.map((t) => {
        const py = sy(t);
        return (
          <g key={`y-${t}`}>
            <line
              x1={padding.left}
              x2={padding.left + innerW}
              y1={py}
              y2={py}
              stroke="hsl(var(--border))"
              strokeDasharray="2 3"
              opacity={0.7}
            />
            <line
              x1={padding.left - 3}
              x2={padding.left}
              y1={py}
              y2={py}
              stroke="hsl(var(--border-strong))"
              strokeWidth={1}
            />
            <text
              x={padding.left - 6}
              y={py + 3}
              fontSize="10"
              textAnchor="end"
              fill="hsl(var(--muted-foreground))"
            >
              {formatTick(t, y.decimals)}
            </text>
          </g>
        );
      })}

      {/* X gridlines + ticks */}
      {xTicks.map((t) => {
        const px = sx(t);
        return (
          <g key={`x-${t}`}>
            <line
              x1={px}
              x2={px}
              y1={padding.top}
              y2={padding.top + innerH}
              stroke="hsl(var(--border))"
              strokeDasharray="2 3"
              opacity={0.5}
            />
            <line
              x1={px}
              x2={px}
              y1={padding.top + innerH}
              y2={padding.top + innerH + 3}
              stroke="hsl(var(--border-strong))"
              strokeWidth={1}
            />
            <text
              x={px}
              y={padding.top + innerH + 14}
              fontSize="10"
              textAnchor="middle"
              fill="hsl(var(--muted-foreground))"
            >
              {formatTick(t, x.decimals)}
            </text>
          </g>
        );
      })}

      {/* Axes */}
      <line
        x1={padding.left}
        x2={padding.left + innerW}
        y1={padding.top + innerH}
        y2={padding.top + innerH}
        stroke="hsl(var(--border-strong))"
        strokeWidth={1}
      />
      <line
        x1={padding.left}
        x2={padding.left}
        y1={padding.top}
        y2={padding.top + innerH}
        stroke="hsl(var(--border-strong))"
        strokeWidth={1}
      />

      {/* Plot content (clipped to inner area for safety) */}
      <defs>
        <clipPath id={`clip-${W}-${H}`}>
          <rect x={padding.left} y={padding.top} width={innerW} height={innerH} />
        </clipPath>
      </defs>
      <g clipPath={`url(#clip-${W}-${H})`}>{children}</g>

      {/* Axis titles */}
      <text
        x={padding.left + innerW / 2}
        y={H - 4}
        fontSize="10.5"
        textAnchor="middle"
        fill="hsl(var(--foreground))"
        opacity={0.75}
      >
        {x.title}
        {x.unit ? (
          <tspan opacity={0.6}> ({x.unit})</tspan>
        ) : null}
      </text>
      <text
        x={11}
        y={padding.top + innerH / 2}
        fontSize="10.5"
        textAnchor="middle"
        fill="hsl(var(--foreground))"
        opacity={0.75}
        transform={`rotate(-90 11 ${padding.top + innerH / 2})`}
      >
        {y.title}
        {y.unit ? (
          <tspan opacity={0.6}> ({y.unit})</tspan>
        ) : null}
      </text>

      {/* Top overlay (tooltip / crosshair) */}
      {overlay}
    </svg>
  );
};

export const ChartLegend = ({
  items,
}: {
  items: { color: string; label: string; dashed?: boolean }[];
}) => (
  <div className="flex items-center gap-3 flex-wrap text-[11px] text-muted-foreground">
    {items.map((it) => (
      <div key={it.label} className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-[2px] w-4 rounded-full"
          style={{
            background: it.color,
            backgroundImage: it.dashed
              ? `repeating-linear-gradient(90deg, ${it.color} 0 4px, transparent 4px 7px)`
              : undefined,
          }}
        />
        <span>{it.label}</span>
      </div>
    ))}
  </div>
);

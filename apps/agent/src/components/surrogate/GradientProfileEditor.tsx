import { useMemo, useRef, useState } from 'react'
import {
  buildGradientProgramPoints,
  getGradientHandles,
  moveGradientHandle,
  normalizeGradientProgram,
  type GradientHandleId,
  type GradientProgram
} from '@surrogate-backend-model/gradientPhysics'

type GradientProfileEditorProps = {
  program: GradientProgram
  onChange: (next: GradientProgram) => void
}

const WIDTH = 920
const HEIGHT = 250
const PADDING = { top: 20, right: 24, bottom: 38, left: 48 }

function buildPath(points: Array<{ x: number; y: number }>) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(' ')
}

export function GradientProfileEditor({ program, onChange }: GradientProfileEditorProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [draggingHandle, setDraggingHandle] = useState<GradientHandleId | null>(null)
  const normalizedProgram = useMemo(() => normalizeGradientProgram(program), [program])
  const handles = useMemo(() => getGradientHandles(normalizedProgram), [normalizedProgram])
  const renderedHandles = useMemo(
    () => [...handles].sort((left, right) => Number(left.movableY) - Number(right.movableY)),
    [handles]
  )
  const points = useMemo(() => buildGradientProgramPoints(normalizedProgram), [normalizedProgram])
  const innerWidth = WIDTH - PADDING.left - PADDING.right
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom
  const maxTime = normalizedProgram.reequilibrateUntilMin

  const xFor = (timeMin: number) =>
    PADDING.left + (timeMin / Math.max(0.001, maxTime)) * innerWidth
  const yFor = (percentB: number) =>
    HEIGHT - PADDING.bottom - (percentB / 100) * innerHeight
  const timeFor = (x: number) =>
    ((x - PADDING.left) / Math.max(1, innerWidth)) * maxTime
  const percentFor = (y: number) =>
    ((HEIGHT - PADDING.bottom - y) / Math.max(1, innerHeight)) * 100

  const plottedPoints = points.map((point) => ({
    x: xFor(point.timeMin),
    y: yFor(point.percentB)
  }))

  const handleDrag = (clientX: number, clientY: number) => {
    if (!draggingHandle || !svgRef.current) {
      return
    }

    const bounds = svgRef.current.getBoundingClientRect()
    const localX = ((clientX - bounds.left) / bounds.width) * WIDTH
    const localY = ((clientY - bounds.top) / bounds.height) * HEIGHT
    const nextTime = timeFor(localX)
    const nextPercent = percentFor(localY)

    onChange(moveGradientHandle(normalizedProgram, draggingHandle, nextTime, nextPercent))
  }

  return (
    <div className="gradient-editor-shell">
      <svg
        ref={svgRef}
        className="chart-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Editable gradient profile"
        onPointerMove={(event) => handleDrag(event.clientX, event.clientY)}
        onPointerUp={() => setDraggingHandle(null)}
        onPointerCancel={() => setDraggingHandle(null)}
      >
        <rect
          x="0"
          y="0"
          width={WIDTH}
          height={HEIGHT}
          rx="24"
          fill="var(--silico-chart-surface)"
        />

        {[0, 25, 50, 75, 100].map((tick) => {
          const y = yFor(tick)
          return (
            <g key={tick}>
              <line
                x1={PADDING.left}
                x2={WIDTH - PADDING.right}
                y1={y}
                y2={y}
                stroke="var(--silico-chart-grid)"
                strokeDasharray="4 8"
              />
              <text
                x={PADDING.left - 12}
                y={y + 4}
                textAnchor="end"
                className="chart-axis-tick"
              >
                {tick}
              </text>
            </g>
          )
        })}

        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const timeTick = maxTime * ratio
          const x = xFor(timeTick)
          return (
            <g key={ratio}>
              <line
                x1={x}
                x2={x}
                y1={HEIGHT - PADDING.bottom}
                y2={PADDING.top}
                stroke="var(--silico-chart-grid)"
                strokeDasharray="4 8"
              />
              <text
                x={x}
                y={HEIGHT - 8}
                textAnchor="middle"
                className="chart-axis-tick"
              >
                {timeTick.toFixed(1)}
              </text>
            </g>
          )
        })}

        <path
          d={buildPath(plottedPoints)}
          fill="none"
          stroke="var(--silico-chart-line)"
          strokeWidth="4"
          strokeDasharray="10 8"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {renderedHandles.map((handle) => (
          <g key={handle.id}>
            <circle
              cx={xFor(handle.timeMin)}
              cy={yFor(handle.percentB)}
              r="10"
              fill="var(--silico-bg-base)"
              stroke="var(--silico-chart-line)"
              strokeWidth="3"
              className="gradient-handle"
              onPointerDown={(event) => {
                event.preventDefault()
                event.stopPropagation()
                event.currentTarget.setPointerCapture(event.pointerId)
                setDraggingHandle(handle.id)
              }}
            />
          </g>
        ))}

        <text
          x={PADDING.left}
          y={14}
          textAnchor="start"
          className="chart-axis-label"
        >
          % B
        </text>
        <text
          x={WIDTH - PADDING.right}
          y={HEIGHT - 8}
          textAnchor="end"
          className="chart-axis-label"
        >
          Time (min)
        </text>
      </svg>
    </div>
  )
}

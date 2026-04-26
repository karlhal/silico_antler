import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { scaleLinear } from 'd3-scale'
import { select } from 'd3-selection'
import {
  zoom,
  zoomIdentity,
  type D3ZoomEvent,
  type ZoomBehavior,
  type ZoomTransform
} from 'd3-zoom'
import type { SurrogateChartPoint, SurrogatePeak } from './surrogateModel'

type ChromatogramChartProps = {
  series: SurrogateChartPoint[]
  peaks: SurrogatePeak[]
  title: string
  activePeakIndex: number | null
  onPeakSelect: (index: number) => void
}

const WIDTH = 920
const HEIGHT = 340
const PADDING = 24

function readCssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') {
    return fallback
  }

  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function areaPolygon(
  series: SurrogateChartPoint[],
  xFor: (value: number) => number,
  yFor: (value: number) => number
) {
  const points = series.map((point) => `${xFor(point.x)},${yFor(point.y)}`).join(' ')
  return `${PADDING},${HEIGHT - PADDING} ${points} ${WIDTH - PADDING},${HEIGHT - PADDING}`
}

function nearestSeriesY(series: SurrogateChartPoint[], x: number) {
  return series.reduce(
    (best, point) => (Math.abs(point.x - x) < Math.abs(best.x - x) ? point : best),
    series[0] ?? { x: 0, y: 0 }
  ).y
}

export function ChromatogramChart({
  series,
  peaks,
  title,
  activePeakIndex,
  onPeakSelect
}: ChromatogramChartProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const gradientId = useId()
  const maxX = Math.max(...series.map((point) => point.x), 1)
  const maxY = Math.max(...series.map((point) => point.y), 1)

  const baseXScale = useMemo(
    () => scaleLinear().domain([0, maxX]).range([PADDING, WIDTH - PADDING]),
    [maxX]
  )
  const yScale = useMemo(
    () => scaleLinear().domain([0, maxY]).range([HEIGHT - PADDING, PADDING]),
    [maxY]
  )
  const xScale = useMemo(() => transform.rescaleX(baseXScale), [baseXScale, transform])

  const polyline = series.map((point) => `${xScale(point.x)},${yScale(point.y)}`).join(' ')

  useEffect(() => {
    if (!svgRef.current) {
      return
    }

    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .translateExtent([
        [PADDING, 0],
        [WIDTH - PADDING, HEIGHT]
      ])
      .extent([
        [PADDING, 0],
        [WIDTH - PADDING, HEIGHT]
      ])
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        setTransform(event.transform)
      })

    zoomBehaviorRef.current = behavior
    select(svgRef.current).call(behavior)

    return () => {
      select(svgRef.current).on('.zoom', null)
    }
  }, [])

  function handleResetZoom() {
    if (!svgRef.current || !zoomBehaviorRef.current) {
      return
    }

    select(svgRef.current).call(zoomBehaviorRef.current.transform, zoomIdentity)
    setTransform(zoomIdentity)
  }

  async function handleExportPng() {
    if (!svgRef.current) {
      return
    }

    const serializer = new XMLSerializer()
    const source = serializer.serializeToString(svgRef.current)
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const image = new Image()

    image.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = WIDTH * 2
      canvas.height = HEIGHT * 2
      const context = canvas.getContext('2d')

      if (!context) {
        URL.revokeObjectURL(url)
        return
      }

      context.scale(2, 2)
      context.fillStyle = readCssVar('--silico-bg-base', '#f7f6f3')
      context.fillRect(0, 0, WIDTH, HEIGHT)
      context.drawImage(image, 0, 0, WIDTH, HEIGHT)

      const anchor = document.createElement('a')
      anchor.href = canvas.toDataURL('image/png')
      anchor.download = 'silico-surrogate-chromatogram.png'
      anchor.click()

      URL.revokeObjectURL(url)
    }

    image.src = url
  }

  return (
    <div className="chart-shell">
      <div className="chart-head">
        <div>
          <h3>{title}</h3>
        </div>
        <div className="chart-actions">
          <button className="toolbar-button" onClick={handleResetZoom} type="button">
            Reset zoom
          </button>
          <button className="toolbar-button" onClick={handleExportPng} type="button">
            Export PNG
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        className="chart-svg interactive-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={title}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="var(--silico-chart-line)" stopOpacity="0.28" />
            <stop
              offset="100%"
              stopColor="var(--silico-accent-cobalt-soft)"
              stopOpacity="0.06"
            />
          </linearGradient>
        </defs>

        <rect
          x="0"
          y="0"
          width={WIDTH}
          height={HEIGHT}
          rx="24"
          fill="var(--silico-chart-surface)"
        />

        {[0.25, 0.5, 0.75].map((ratio) => {
          const y = HEIGHT - PADDING - ratio * (HEIGHT - PADDING * 2)
          return (
            <line
              key={ratio}
              x1={PADDING}
              x2={WIDTH - PADDING}
              y1={y}
              y2={y}
              stroke="var(--silico-chart-grid)"
              strokeDasharray="4 8"
            />
          )
        })}

        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const value = maxX * ratio
          const x = xScale(value)
          return (
            <g key={ratio}>
              <line
                x1={x}
                x2={x}
                y1={HEIGHT - PADDING}
                y2={HEIGHT - PADDING + 6}
                stroke="var(--silico-chart-axis)"
              />
              <text x={x} y={HEIGHT - 6} textAnchor="middle" className="chart-axis-tick">
                {value.toFixed(1)}
              </text>
            </g>
          )
        })}

        <polygon
          points={areaPolygon(series, (value) => xScale(value), (value) => yScale(value))}
          fill={`url(#${gradientId})`}
        />
        <polyline
          fill="none"
          points={polyline}
          stroke="var(--silico-chart-line)"
          strokeWidth="4"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {peaks.map((peak, index) => {
          const x = xScale(peak.retention_time_min)
          const y = yScale(nearestSeriesY(series, peak.retention_time_min))
          const active = activePeakIndex === index

          return (
            <g
              key={`${peak.label}-${index}`}
              className={active ? 'chart-peak active' : 'chart-peak'}
              onClick={() => onPeakSelect(index)}
            >
              <line
                x1={x}
                x2={x}
                y1={HEIGHT - PADDING}
                y2={y}
                stroke={active ? 'var(--silico-chart-active)' : 'var(--silico-chart-axis)'}
                strokeDasharray="3 4"
              />
              <circle
                cx={x}
                cy={y}
                r={active ? 7 : 5}
                fill={active ? 'var(--silico-chart-active)' : 'var(--silico-chart-line)'}
              />
              <text x={x} y={y - 14} textAnchor="middle" className="chart-label">
                {peak.label}
              </text>
            </g>
          )
        })}

        <rect
          x={PADDING}
          y={PADDING}
          width={WIDTH - PADDING * 2}
          height={HEIGHT - PADDING * 2}
          fill="transparent"
        />
      </svg>
    </div>
  )
}

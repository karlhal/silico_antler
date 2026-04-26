import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent
} from 'react'
import { contours, type ContourMultiPolygon } from 'd3-contour'
import { interpolateViridis } from 'd3-scale-chromatic'
import { select } from 'd3-selection'
import {
  zoom,
  zoomIdentity,
  type D3ZoomEvent,
  type ZoomBehavior,
  type ZoomTransform
} from 'd3-zoom'
import type { SurrogateLandscape } from './surrogateModel'

type LandscapeHeatmapProps = {
  landscape: SurrogateLandscape
  current: {
    temperature_c: number
    meoh_pct: number
  }
  onSelect: (next: { temperature_c: number; meoh_pct: number }) => void
}

type RGB = [number, number, number]

const WIDTH = 920
const HEIGHT = 420
const MARGIN = { top: 22, right: 24, bottom: 44, left: 58 }
const CONTOUR_COUNT = 12
const TARGET_THRESHOLD_SECONDS = 3
const FALLBACK_SURFACE_COLOR: RGB = [227, 223, 215]

function readCssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') {
    return fallback
  }

  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function nearestIndex(values: number[], target: number) {
  let bestIndex = 0
  let bestDistance = Number.POSITIVE_INFINITY

  for (let index = 0; index < values.length; index += 1) {
    const distance = Math.abs(values[index] - target)
    if (distance < bestDistance) {
      bestIndex = index
      bestDistance = distance
    }
  }

  return bestIndex
}

function parseColor(color: string): RGB {
  const hexMatch = color.match(/^#([0-9a-f]{6})$/i)
  if (hexMatch) {
    const hex = hexMatch[1]
    return [
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16)
    ]
  }

  const rgbMatch = color.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/i)
  if (rgbMatch) {
    return [Number(rgbMatch[1]), Number(rgbMatch[2]), Number(rgbMatch[3])]
  }

  return FALLBACK_SURFACE_COLOR
}

function contourPath(
  geometry: ContourMultiPolygon,
  width: number,
  height: number,
  columns: number,
  rows: number
) {
  const scaleX = columns > 1 ? width / (columns - 1) : width
  const scaleY = rows > 1 ? height / (rows - 1) : height

  return geometry.coordinates
    .map((polygon) =>
      polygon
        .map((ring) =>
          ring
            .map((point, index) => {
              const x = point[0] ?? 0
              const y = point[1] ?? 0
              return `${index === 0 ? 'M' : 'L'}${(x * scaleX).toFixed(2)},${(y * scaleY).toFixed(2)}`
            })
            .join(' ')
        )
        .join(' Z ')
    )
    .join(' Z ')
}

function buildStarPath(
  cx: number,
  cy: number,
  outerRadius: number,
  innerRadius: number,
  points = 5
) {
  const path: string[] = []

  for (let index = 0; index < points * 2; index += 1) {
    const radius = index % 2 === 0 ? outerRadius : innerRadius
    const angle = -Math.PI / 2 + (index * Math.PI) / points
    const x = cx + Math.cos(angle) * radius
    const y = cy + Math.sin(angle) * radius
    path.push(`${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`)
  }

  path.push('Z')
  return path.join(' ')
}

function sampleLandscape(values: number[][], x: number, y: number): number | null {
  const rows = values.length
  const columns = values[0]?.length ?? 0

  if (!rows || !columns) {
    return null
  }

  const x0 = clamp(Math.floor(x), 0, columns - 1)
  const x1 = clamp(x0 + 1, 0, columns - 1)
  const y0 = clamp(Math.floor(y), 0, rows - 1)
  const y1 = clamp(y0 + 1, 0, rows - 1)
  const tx = x - x0
  const ty = y - y0

  const corners = [values[y0][x0], values[y0][x1], values[y1][x0], values[y1][x1]]
  const hasValidValue = corners.some((value) => value >= 0)

  if (!hasValidValue) {
    return null
  }

  const [v00, v10, v01, v11] = corners.map((value) => Math.max(value, 0))
  const top = v00 * (1 - tx) + v10 * tx
  const bottom = v01 * (1 - tx) + v11 * tx

  return top * (1 - ty) + bottom * ty
}

function buildHeatmapDataUrl(
  values: number[][],
  width: number,
  height: number,
  maxValue: number,
  surfaceColor: RGB
) {
  if (typeof document === 'undefined' || !width || !height) {
    return ''
  }

  const rasterScale =
    typeof window === 'undefined'
      ? 3
      : Math.min(4, Math.max(3, Math.ceil(window.devicePixelRatio || 1) + 1))
  const rasterWidth = Math.max(1, Math.round(width * rasterScale))
  const rasterHeight = Math.max(1, Math.round(height * rasterScale))
  const canvas = document.createElement('canvas')
  canvas.width = rasterWidth
  canvas.height = rasterHeight
  const context = canvas.getContext('2d')

  if (!context) {
    return ''
  }

  const imageData = context.createImageData(rasterWidth, rasterHeight)
  const palette = Array.from({ length: 512 }, (_, index) =>
    parseColor(interpolateViridis(index / 511))
  )
  const divisor = maxValue > 0 ? maxValue : 1

  for (let y = 0; y < rasterHeight; y += 1) {
    const landscapeY =
      rasterHeight > 1 ? (y / (rasterHeight - 1)) * Math.max(values.length - 1, 0) : 0
    for (let x = 0; x < rasterWidth; x += 1) {
      const landscapeX =
        rasterWidth > 1
          ? (x / (rasterWidth - 1)) * Math.max((values[0]?.length ?? 1) - 1, 0)
          : 0
      const sample = sampleLandscape(values, landscapeX, landscapeY)
      const paletteIndex =
        sample === null
          ? -1
          : clamp(Math.round((sample / divisor) * (palette.length - 1)), 0, palette.length - 1)
      const [red, green, blue] = paletteIndex === -1 ? surfaceColor : palette[paletteIndex]
      const offset = (y * rasterWidth + x) * 4

      imageData.data[offset] = red
      imageData.data[offset + 1] = green
      imageData.data[offset + 2] = blue
      imageData.data[offset + 3] = 255
    }
  }

  context.putImageData(imageData, 0, 0)
  return canvas.toDataURL('image/png')
}

export function LandscapeHeatmap({
  landscape,
  current,
  onSelect
}: LandscapeHeatmapProps) {
  const clipPathId = useId().replace(/:/g, '')
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const themeKey =
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light'

  const innerWidth = WIDTH - MARGIN.left - MARGIN.right
  const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const columns = landscape.meoh_axis.length
  const rows = landscape.temp_axis.length
  const cellWidth = columns > 0 ? innerWidth / columns : innerWidth
  const cellHeight = rows > 0 ? innerHeight / rows : innerHeight
  const currentX = nearestIndex(landscape.meoh_axis, current.meoh_pct)
  const currentY = nearestIndex(landscape.temp_axis, current.temperature_c)
  const bestX = nearestIndex(landscape.meoh_axis, landscape.best_point.meoh_pct)
  const bestY = nearestIndex(landscape.temp_axis, landscape.best_point.temperature_c)

  const flatValues = useMemo(
    () => landscape.values.flat().map((value) => Math.max(value, 0)),
    [landscape.values]
  )
  const maxValue = useMemo(() => Math.max(...flatValues, 0), [flatValues])
  const surfaceColor = useMemo(
    () => parseColor(readCssVar('--silico-chart-invalid', '#e3dfd7')),
    [themeKey]
  )
  const heatmapDataUrl = useMemo(
    () => buildHeatmapDataUrl(landscape.values, innerWidth, innerHeight, maxValue, surfaceColor),
    [innerHeight, innerWidth, landscape.values, maxValue, surfaceColor]
  )
  const chartSurface = readCssVar('--silico-chart-surface', '#ece8e1')
  const contourStroke = readCssVar('--silico-chart-outline', 'rgba(29, 35, 44, 0.26)')
  const targetStroke = readCssVar('--silico-chart-target', 'rgba(190, 155, 95, 0.96)')
  const currentHalo = readCssVar('--silico-chart-line-soft', 'rgba(73, 113, 221, 0.16)')
  const currentFill = readCssVar('--silico-chart-line', '#4971dd')
  const currentStroke = readCssVar('--silico-bg-base', '#f7f6f3')
  const bestFill = readCssVar('--silico-chart-active', '#00a89b')
  const bestStroke = readCssVar('--silico-text-primary', '#1d232c')
  const outerStroke = readCssVar('--silico-chart-outline', 'rgba(29, 35, 44, 0.12)')

  const contourGeometry = useMemo(() => {
    if (!flatValues.length || maxValue <= 0) {
      return []
    }

    const thresholds = Array.from(
      { length: CONTOUR_COUNT },
      (_, index) => ((index + 1) / (CONTOUR_COUNT + 1)) * maxValue
    )
    return contours().size([columns, rows]).thresholds(thresholds)(flatValues)
  }, [columns, flatValues, maxValue, rows])

  const targetContourGeometry = useMemo(() => {
    if (!flatValues.length || maxValue < TARGET_THRESHOLD_SECONDS) {
      return []
    }

    return contours().size([columns, rows]).thresholds([TARGET_THRESHOLD_SECONDS])(flatValues)
  }, [columns, flatValues, maxValue, rows])

  useEffect(() => {
    if (!svgRef.current) {
      return
    }

    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 6])
      .translateExtent([
        [0, 0],
        [WIDTH, HEIGHT]
      ])
      .extent([
        [MARGIN.left, MARGIN.top],
        [WIDTH - MARGIN.right, HEIGHT - MARGIN.bottom]
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

  function handleSelectPoint(event: ReactMouseEvent<SVGRectElement>) {
    if (!svgRef.current || !columns || !rows) {
      return
    }

    const bounds = svgRef.current.getBoundingClientRect()
    if (!bounds.width || !bounds.height) {
      return
    }

    const pointerX = ((event.clientX - bounds.left) * WIDTH) / bounds.width - MARGIN.left
    const pointerY = ((event.clientY - bounds.top) * HEIGHT) / bounds.height - MARGIN.top
    const localX = (pointerX - transform.x) / transform.k
    const localY = (pointerY - transform.y) / transform.k

    if (localX < 0 || localX > innerWidth || localY < 0 || localY > innerHeight) {
      return
    }

    const columnIndex = clamp(Math.floor(localX / cellWidth), 0, columns - 1)
    const rowIndex = clamp(Math.floor(localY / cellHeight), 0, rows - 1)

    onSelect({
      temperature_c: landscape.temp_axis[rowIndex],
      meoh_pct: landscape.meoh_axis[columnIndex]
    })
  }

  return (
    <div className="chart-shell">
      <div className="chart-head">
        <div>
          <h3>Landscape heatmap</h3>
        </div>
        <div className="chart-actions">
          <p className="chart-note">Select a cell to set the operating point.</p>
          <button className="toolbar-button" onClick={handleResetZoom} type="button">
            Reset view
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        className="chart-svg interactive-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Optimization landscape heatmap"
      >
        <defs>
          <clipPath id={clipPathId}>
            <rect x="0" y="0" width={innerWidth} height={innerHeight} rx="18" />
          </clipPath>
        </defs>

        <rect x="0" y="0" width={WIDTH} height={HEIGHT} rx="24" fill={chartSurface} />

        <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
          <g clipPath={`url(#${clipPathId})`}>
            <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
              {heatmapDataUrl ? (
                <image
                  href={heatmapDataUrl}
                  x="0"
                  y="0"
                  width={innerWidth}
                  height={innerHeight}
                  preserveAspectRatio="none"
                />
              ) : null}

              {contourGeometry.map((geometry, index) => (
                <path
                  key={`${geometry.value}-${index}`}
                  d={contourPath(geometry, innerWidth, innerHeight, columns, rows)}
                  fill="none"
                  stroke={contourStroke}
                  strokeWidth={0.9}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
              ))}

              {targetContourGeometry.map((geometry, index) => (
                <path
                  key={`target-${geometry.value}-${index}`}
                  d={contourPath(geometry, innerWidth, innerHeight, columns, rows)}
                  fill="none"
                  stroke={targetStroke}
                  strokeWidth={1.7}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
              ))}

              <circle
                cx={currentX * cellWidth + cellWidth / 2}
                cy={currentY * cellHeight + cellHeight / 2}
                r="13"
                fill={currentHalo}
                pointerEvents="none"
              />
              <circle
                cx={currentX * cellWidth + cellWidth / 2}
                cy={currentY * cellHeight + cellHeight / 2}
                r="6.5"
                fill={currentFill}
                stroke={currentStroke}
                strokeWidth="2.6"
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />

              <path
                d={buildStarPath(
                  bestX * cellWidth + cellWidth / 2,
                  bestY * cellHeight + cellHeight / 2,
                  10,
                  5.2
                )}
                fill={bestFill}
                stroke={bestStroke}
                strokeWidth="1.8"
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />

              <rect
                x="0"
                y="0"
                width={innerWidth}
                height={innerHeight}
                fill="transparent"
                onClick={handleSelectPoint}
              />
            </g>
          </g>

          <rect
            x="0"
            y="0"
            width={innerWidth}
            height={innerHeight}
            rx="18"
            fill="none"
            stroke={outerStroke}
          />

          <text
            x={innerWidth / 2}
            y={innerHeight + 34}
            textAnchor="middle"
            className="chart-axis-label"
          >
            Methanol %
          </text>
          <text
            x={-innerHeight / 2}
            y={-36}
            textAnchor="middle"
            transform="rotate(-90)"
            className="chart-axis-label"
          >
            Temperature deg C
          </text>
        </g>
      </svg>

      <div className="heatmap-legend">
        <div className="heatmap-legend-head">
          <strong>Min peak separation (s)</strong>
          <span>
            0.000 to {maxValue.toFixed(3)}
          </span>
        </div>
        <div className="heatmap-colorbar" aria-hidden="true" />
        <div className="heatmap-legend-notes">
          <p>
            <span className="legend-line-swatch" aria-hidden="true" /> Threshold contour: 3.0 s
            target line
          </p>
          <p>
            <span className="legend-invalid-swatch" aria-hidden="true" /> Pale cells mark points
            penalized by the retention cap
          </p>
        </div>
      </div>
    </div>
  )
}

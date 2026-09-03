/** SVG previews of the marks the chart stamps. A faithful copy of the Excalidraw element
 * factories in EmbeddedExcalidraw.jsx, not a shared code path: those build Excalidraw
 * elements inside the React chart bundle, and the config page is a plain Vue bundle.
 * `marker_preview_behaviors()` reads PREVIEW_BEHAVIORS so a behaviour added to the field
 * without a shape here fails a test instead of drawing the wrong mark. */

import { markerSizeOf } from "./marker_size.js"

export const PREVIEW_BEHAVIORS = [
  "numbered_dot",
  "blue_dot",
  "three_dots",
  "triangle",
  "triangle_cluster",
  "hatch",
  "five_lines",
  "x_mark",
  "target",
  "area",
  "finding_dot",
  "freehand",
  "line",
]

const DEFAULT_COLOR = "#0f766e"

function triangle(x, y, size, color) {
  const half = size / 2
  const height = size * 0.9
  const points = `${x},${y - height / 2} ${x - half},${y + height / 2} ${x + half},${y + height / 2}`
  return `<polygon points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round"/>`
}

const AREA_HALF_WIDTH = 40
const AREA_HALF_HEIGHT = 28

function areaOutline(color) {
  return `<rect x="${-AREA_HALF_WIDTH}" y="${-AREA_HALF_HEIGHT}" width="${AREA_HALF_WIDTH * 2}" height="${AREA_HALF_HEIGHT * 2}" fill="none" stroke="${color}" stroke-width="2"/>`
}

/**
 * 45-degree fill lines trimmed to the area box. Clipped by arithmetic rather than a <clipPath>,
 * because every tile in the picker renders this markup and shared element ids would collide.
 */
function diagonals(color, step, direction) {
  const lines = []
  for (let offset = -(AREA_HALF_WIDTH + AREA_HALF_HEIGHT); offset <= AREA_HALF_WIDTH + AREA_HALF_HEIGHT; offset += step) {
    const start = Math.max(-AREA_HALF_WIDTH, offset - AREA_HALF_HEIGHT)
    const end = Math.min(AREA_HALF_WIDTH, offset + AREA_HALF_HEIGHT)
    if (start >= end) continue
    const [x1, x2] = direction > 0 ? [start, end] : [-start, -end]
    lines.push(`<line x1="${x1}" y1="${start - offset}" x2="${x2}" y2="${end - offset}" stroke="${color}" stroke-width="2"/>`)
  }
  return lines.join("")
}

const SHAPES = {
  dot: (color) => `<circle cx="0" cy="0" r="8" fill="${color}" stroke="${color}" stroke-width="1.5"/>`,
  hollowDot: (color) => `<circle cx="0" cy="0" r="8" fill="none" stroke="${color}" stroke-width="2.5"/>`,
  ringedDot: (color) =>
    `<circle cx="0" cy="0" r="11" fill="none" stroke="${color}" stroke-width="2"/>` +
    `<circle cx="0" cy="0" r="5" fill="${color}" stroke="${color}" stroke-width="1.5"/>`,
  dotCluster: (color) =>
    [
      [0, -12],
      [-12, 8],
      [12, 8],
    ]
      .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="${color}"/>`)
      .join(""),
  triangle: (color) => triangle(0, 0, 22, color),
  triangleCluster: (color) =>
    [
      [0, -14],
      [-14, 10],
      [14, 10],
    ]
      .map(([x, y]) => triangle(x, y, 16, color))
      .join(""),
  cross: (color) =>
    `<line x1="-18" y1="-18" x2="18" y2="18" stroke="${color}" stroke-width="3" stroke-linecap="round"/>` +
    `<line x1="18" y1="-18" x2="-18" y2="18" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`,
  target: (color) =>
    `<circle cx="0" cy="0" r="18" fill="none" stroke="${color}" stroke-width="2"/>` +
    `<circle cx="0" cy="0" r="7" fill="${color}"/>` +
    `<line x1="-26" y1="0" x2="26" y2="0" stroke="${color}" stroke-width="2"/>` +
    `<line x1="0" y1="-26" x2="0" y2="26" stroke="${color}" stroke-width="2"/>`,
  area: (color) =>
    `<rect x="${-AREA_HALF_WIDTH}" y="${-AREA_HALF_HEIGHT}" width="${AREA_HALF_WIDTH * 2}" height="${AREA_HALF_HEIGHT * 2}" fill="${color}" fill-opacity="0.18" stroke="${color}" stroke-width="2"/>`,
  areaHachure: (color) => diagonals(color, 12, 1) + areaOutline(color),
  areaCrossHatch: (color) => diagonals(color, 14, 1) + diagonals(color, 14, -1) + areaOutline(color),
  line: (color) =>
    `<line x1="-34" y1="14" x2="34" y2="-14" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`,
  stroke: (color) =>
    `<path d="M-34 10 C -26 -22, -6 -26, 2 -8 C 10 8, 26 12, 34 -6" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`,
}

/** Mirrors createStampElements()'s substring chain, in its order. An unknown behaviour
 * falls through to the dot there too. */
export function markerShapeFor(behavior) {
  const key = String(behavior || "").toLowerCase()
  if (!key) return null
  if (key.includes("x")) return SHAPES.cross
  if (key.includes("target")) return SHAPES.target
  // The three area behaviours share the dragged rectangle and differ only in fill. They come
  // before `line` because five_lines contains that substring.
  if (key.includes("five_lines")) return SHAPES.areaCrossHatch
  if (key.includes("hatch")) return SHAPES.areaHachure
  if (key.includes("area")) return SHAPES.area
  if (key.includes("line")) return SHAPES.line
  if (key.includes("triangle_cluster")) return SHAPES.triangleCluster
  if (key.includes("triangle")) return SHAPES.triangle
  if (key.includes("three_dots")) return SHAPES.dotCluster
  if (key.includes("finding_dot")) return SHAPES.ringedDot
  if (key.includes("freehand") || key.includes("stroke") || key.includes("paint")) return SHAPES.stroke
  if (key.includes("blue_dot")) return SHAPES.hollowDot
  return SHAPES.dot
}

/**
 * `scale` draws the shape at the multiplier the chart would stamp it at. `frame` widens the
 * box so the largest scale still fits: a sample that clips is worse than a small one.
 */
export function markerPreviewSvg(behavior, color, size = 44, scale = 1, frame = 1) {
  const shape = markerShapeFor(behavior)
  const height = Math.round((size * 68) / 92)
  const [width, boxHeight] = [92 * frame, 68 * frame]
  const body = shape
    ? `<g transform="scale(${markerSizeOf(scale)})">${shape(color || DEFAULT_COLOR)}</g>`
    : `<text x="0" y="5" text-anchor="middle" font-size="13" fill="#94a3b8">—</text>`
  return `<svg viewBox="${-width / 2} ${-boxHeight / 2} ${width} ${boxHeight}" width="${size}" height="${height}" aria-hidden="true">${body}</svg>`
}

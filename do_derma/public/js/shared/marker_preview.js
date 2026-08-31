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
]

const DEFAULT_COLOR = "#0f766e"

function triangle(x, y, size, color) {
  const half = size / 2
  const height = size * 0.9
  const points = `${x},${y - height / 2} ${x - half},${y + height / 2} ${x + half},${y + height / 2}`
  return `<polygon points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round"/>`
}

const SHAPES = {
  dot: (color) => `<circle cx="0" cy="0" r="8" fill="${color}" stroke="${color}" stroke-width="1.5"/>`,
  dotCluster: (color) =>
    [
      [0, -12],
      [-12, 8],
      [12, 8],
    ]
      .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="${color}"/>`)
      .join(""),
  triangleCluster: (color) =>
    [
      [0, -14],
      [-14, 10],
      [14, 10],
    ]
      .map(([x, y]) => triangle(x, y, 16, color))
      .join(""),
  hatch: (color) =>
    [-20, -10, 0, 10, 20]
      .map(
        (offset) =>
          `<line x1="-36" y1="${offset + 18}" x2="36" y2="${offset - 18}" stroke="${color}" stroke-width="3" stroke-linecap="round"/>`
      )
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
    `<rect x="-40" y="-28" width="80" height="56" fill="${color}" fill-opacity="0.18" stroke="${color}" stroke-width="2"/>`,
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
  if (key.includes("hatch") || key.includes("five_lines")) return SHAPES.hatch
  if (key.includes("area")) return SHAPES.area
  if (key.includes("triangle")) return SHAPES.triangleCluster
  if (key.includes("finding_dot") || key.includes("three_dots")) return SHAPES.dotCluster
  if (key.includes("freehand") || key.includes("stroke") || key.includes("paint")) return SHAPES.stroke
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

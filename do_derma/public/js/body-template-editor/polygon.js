/** Share of the template's smaller rendered side that still counts as "back at the start". */
export const CLOSE_TOLERANCE_RATIO = 0.02

const FALLBACK_TOLERANCE = 8

/**
 * @param {{ renderedWidth: number, renderedHeight: number } | null | undefined} layout
 * @returns {number}
 */
export function closeTolerance(layout) {
  const smaller = Math.min(Number(layout?.renderedWidth) || 0, Number(layout?.renderedHeight) || 0)
  return smaller > 0 ? smaller * CLOSE_TOLERANCE_RATIO : FALLBACK_TOLERANCE
}

/**
 * @typedef {"" | "too_few_points" | "open" | "self_intersecting"} AreaOutlineReason
 * @typedef {{ isValid: boolean, reason: AreaOutlineReason }} AreaOutlineVerdict
 */

/**
 * Decide whether a stroke is a usable area outline: at least three distinct corners,
 * ending where it started, and never crossing itself. Pure — no React, no Excalidraw.
 *
 * @param {Array<[number, number]> | null | undefined} points
 * @param {number} tolerance
 * @returns {AreaOutlineVerdict}
 */
export function validateAreaPolygon(points, tolerance) {
  const cleaned = toPointPairs(points)
  if (cleaned.length < 3) return { isValid: false, reason: "too_few_points" }
  if (distance(cleaned[0], cleaned[cleaned.length - 1]) > Math.max(0, Number(tolerance) || 0)) {
    return { isValid: false, reason: "open" }
  }

  const corners = cleaned.slice(0, -1)
  if (corners.length < 3) return { isValid: false, reason: "too_few_points" }
  if (hasSelfIntersection(corners)) return { isValid: false, reason: "self_intersecting" }
  return { isValid: true, reason: "" }
}

/** @returns {Array<[number, number]>} the finite [x, y] pairs, in order. */
function toPointPairs(points) {
  if (!Array.isArray(points)) return []
  return points
    .filter((point) => Array.isArray(point) && point.length >= 2)
    .map(([x, y]) => [Number(x), Number(y)])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
}

function distance([x1, y1], [x2, y2]) {
  return Math.hypot(x2 - x1, y2 - y1)
}

/** True when any two non-adjacent edges of the closed ring touch or cross. */
function hasSelfIntersection(corners) {
  const total = corners.length
  for (let first = 0; first < total; first += 1) {
    for (let second = first + 1; second < total; second += 1) {
      if (areAdjacentEdges(first, second, total)) continue
      const crosses = segmentsIntersect(
        corners[first],
        corners[(first + 1) % total],
        corners[second],
        corners[(second + 1) % total]
      )
      if (crosses) return true
    }
  }
  return false
}

function areAdjacentEdges(first, second, total) {
  return second === first + 1 || (first === 0 && second === total - 1)
}

function segmentsIntersect(start1, end1, start2, end2) {
  const d1 = orientation(start2, end2, start1)
  const d2 = orientation(start2, end2, end1)
  const d3 = orientation(start1, end1, start2)
  const d4 = orientation(start1, end1, end2)

  if (d1 * d2 < 0 && d3 * d4 < 0) return true
  if (d1 === 0 && isOnSegment(start2, end2, start1)) return true
  if (d2 === 0 && isOnSegment(start2, end2, end1)) return true
  if (d3 === 0 && isOnSegment(start1, end1, start2)) return true
  return d4 === 0 && isOnSegment(start1, end1, end2)
}

/** -1, 0 or 1 for clockwise, collinear, counter-clockwise. */
function orientation([ax, ay], [bx, by], [cx, cy]) {
  const cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
  if (Math.abs(cross) < 1e-9) return 0
  return cross > 0 ? 1 : -1
}

function isOnSegment([ax, ay], [bx, by], [px, py]) {
  return px >= Math.min(ax, bx) && px <= Math.max(ax, bx) && py >= Math.min(ay, by) && py <= Math.max(ay, by)
}

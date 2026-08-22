/** The multiplier a mark is stamped at. Source of truth for both bundles and for
 * `do_derma/config/marker_size.py`, which parses these constants so the server cannot
 * drift from the sliders. */

export const MARKER_SIZE_MIN = 0.5
export const MARKER_SIZE_MAX = 2
export const MARKER_SIZE_STEP = 0.25
export const MARKER_SIZE_DEFAULT = 1

/** An unset size is 1.0: the geometry every mark was drawn at before sizes existed. */
export function markerSizeOf(value) {
  const size = Number(value)
  if (!Number.isFinite(size) || size <= 0) return MARKER_SIZE_DEFAULT
  return Math.min(MARKER_SIZE_MAX, Math.max(MARKER_SIZE_MIN, size))
}

export function steppedMarkerSize(value) {
  const stepped = Math.round(markerSizeOf(value) / MARKER_SIZE_STEP) * MARKER_SIZE_STEP
  return Math.min(MARKER_SIZE_MAX, Math.max(MARKER_SIZE_MIN, Number(stepped.toFixed(2))))
}

/** Stroke thins out of sight when a mark shrinks, so it scales but never below a hairline. */
export function scaledStrokeWidth(width, size) {
  return Math.max(1, Number(width || 0) * markerSizeOf(size))
}

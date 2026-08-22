import React from "react"
import { MARKER_SIZE_MAX, MARKER_SIZE_MIN, MARKER_SIZE_STEP } from "../../shared/marker_size.js"

const __ = window.__ || ((text) => text)

/** The multiplier the next stamp lands at, or the selected mark's own while one is edited. */
export default function MarkerSizeControl({ size, onChange, onStep }) {
  return (
    <div className="derma-marker-size" data-test="annotation-marker-size" data-size={size}>
      <span>{__("Size")}</span>
      <button
        type="button"
        className="ghost small"
        data-test="annotation-marker-size-down"
        disabled={size <= MARKER_SIZE_MIN}
        aria-label={__("Smaller mark")}
        onClick={() => onStep(-1)}
      >
        −
      </button>
      <input
        type="range"
        min={MARKER_SIZE_MIN}
        max={MARKER_SIZE_MAX}
        step={MARKER_SIZE_STEP}
        value={size}
        data-test="annotation-marker-size-slider"
        aria-label={__("Mark size")}
        onChange={(event) => onChange(event.target.value)}
      />
      <button
        type="button"
        className="ghost small"
        data-test="annotation-marker-size-up"
        disabled={size >= MARKER_SIZE_MAX}
        aria-label={__("Larger mark")}
        onClick={() => onStep(1)}
      >
        +
      </button>
      <strong>{`${size}×`}</strong>
    </div>
  )
}

const __ = window.__ || ((txt) => txt)

/** Server-side codes cross the wire; the panels own their English. */
export function labelFor(labels, code) {
  return __(labels[code] || code)
}

/** Who owns a required field - `_required_field_owners` in api.py. Read by the list and
 * by the builder, which names the flag on a locked row. */
export const REQUIRED_FIELD_SOURCE_LABELS = {
  template: "Template",
  product_tracking: "Product tracking",
  device_settings: "Device settings",
  variables_json: "Variables JSON",
}

/** A marker behaviour as a clinic reads it. The options come from meta at runtime, so this
 * humanises whatever arrives instead of carrying a list that would go stale. */
export function markerBehaviorLabel(behavior) {
  const key = String(behavior || "").trim()
  if (!key) return __("No marker")
  return key
    .split("_")
    .map((word) => (word.length > 2 ? word[0].toUpperCase() + word.slice(1) : word.toUpperCase()))
    .join(" ")
}

/** The fieldname a variable label collapses to. Mirrors `_variable_fieldname` in api.py:
 * the builder previews what the server will store, and the studio keys values by it. */
export function variableFieldname(label) {
  return String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

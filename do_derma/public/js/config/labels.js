const __ = window.__ || ((txt) => txt)

/** Server-side codes cross the wire; the panels own their English. */
export function labelFor(labels, code) {
  return __(labels[code] || code)
}

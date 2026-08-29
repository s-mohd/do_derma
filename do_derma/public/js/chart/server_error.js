const __ = window.__ || ((txt) => txt)

/** Plain text from a refused frappe.call, which rejects with the jqXHR rather than an Error. */
export function serverErrorText(err, fallback = "") {
  const raw = err?.responseJSON?._server_messages || err?._server_messages
  try {
    const first = JSON.parse(JSON.parse(raw)[0])
    const text = htmlToPlainText(first?.message || first)
    if (text) return text
  } catch (parseError) {
    /* fall through to the error's own message */
  }
  return htmlToPlainText(err?.message || "") || fallback || __("Something went wrong.")
}

export function htmlToPlainText(value) {
  const raw = String(value || "")
  if (!raw) return ""
  if (!/[<>]/.test(raw)) return raw
  const html = raw
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h[1-6]|tr)>/gi, "\n")
    .replace(/<li[^>]*>/gi, "- ")
  const el = document.createElement("div")
  el.innerHTML = html
  return (el.textContent || el.innerText || "")
    .replace(/\u00a0/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

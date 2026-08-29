const __ = window.__ || ((txt) => txt)

/**
 * What to show a practitioner when a call fails. frappe.call rejects with the jqXHR, so the
 * reason lives in `responseJSON`, not on the error itself, and `error.message` is often an
 * object that renders as "[object Object]".
 */
export function serverErrorText(error, fallback = "") {
  const readable = htmlToPlainText(readErrorText(error))
  return readable || fallback || __("Something went wrong.")
}

/** The same message, for callers with no fallback of their own to offer. */
export function describeError(error) {
  return serverErrorText(error)
}

function readErrorText(error) {
  if (!error) return ""
  if (typeof error === "string") return error
  const serverMessage =
    firstServerMessage(error.responseJSON?._server_messages) ||
    firstServerMessage(error._server_messages)
  if (serverMessage) return serverMessage
  if (typeof error.message === "string" && error.message) return error.message
  if (error.message && typeof error.message === "object") return readErrorText(error.message)
  if (typeof error.exception === "string" && error.exception) return error.exception
  if (typeof error.exc_type === "string" && error.exc_type) return error.exc_type
  return readErrorText(error.responseJSON)
}

/** Frappe wraps a thrown message in two layers of JSON. */
function firstServerMessage(serverMessages) {
  if (!serverMessages) return ""
  try {
    const raw = JSON.parse(serverMessages)[0]
    if (!raw) return ""
    return JSON.parse(raw).message || String(raw)
  } catch {
    return ""
  }
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
    .replace(/ /g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

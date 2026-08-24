/**
 * What to show a practitioner when a call fails. frappe.call rejects with the response body
 * rather than an Error, so `error.message` is often an object and renders as "[object Object]".
 */
export function describeError(error) {
  const readable = readErrorText(error)
  if (readable) return readable
  try {
    return JSON.stringify(error)
  } catch {
    return String(error)
  }
}

function readErrorText(error) {
  if (!error) return ""
  if (typeof error === "string") return error
  const serverMessage = firstServerMessage(error._server_messages)
  if (serverMessage) return serverMessage
  if (typeof error.message === "string" && error.message) return error.message
  if (error.message && typeof error.message === "object") return readErrorText(error.message)
  if (typeof error.exception === "string" && error.exception) return error.exception
  if (typeof error.exc_type === "string" && error.exc_type) return error.exc_type
  return ""
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

const __ = window.__ || ((text) => text)

/**
 * Prints a whole page the server built on the practitioner's Letter Head
 * (do_derma/printing/pages.py). The window opens inside the click, before the
 * request, so pop-up blockers let it through.
 */
export async function printPage(loadPage) {
  const printWindow = window.open("", "_blank")
  if (!printWindow) {
    frappe.show_alert({ message: __("Allow pop-ups to print."), indicator: "orange" })
    return
  }
  try {
    const { title, html } = await loadPage()
    printWindow.document.write(`<!doctype html>
      <html><head><title>${frappe.utils.escape_html(title || "")}</title></head>
      <body style="font-family:sans-serif;margin:0;">${html}</body></html>`)
    printWindow.document.close()
    printWindow.focus()
    setTimeout(() => printWindow.print(), 350)
  } catch (error) {
    printWindow.close()
    throw error
  }
}

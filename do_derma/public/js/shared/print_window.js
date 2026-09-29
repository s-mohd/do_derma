const __ = window.__ || ((text) => text)

/**
 * Prints `bodyHtml` in a new window. The caller escapes everything it interpolates;
 * `title` is escaped here because it lands in the document head.
 */
export function printHtml(title, bodyHtml) {
  const printWindow = window.open("", "_blank")
  if (!printWindow) {
    frappe.show_alert({ message: __("Allow pop-ups to print."), indicator: "orange" })
    return
  }
  printWindow.document.write(`<!doctype html>
    <html><head><title>${frappe.utils.escape_html(title || "")}</title></head>
    <body style="font-family:sans-serif;margin:24px;">${bodyHtml}</body></html>`)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => printWindow.print(), 350)
}

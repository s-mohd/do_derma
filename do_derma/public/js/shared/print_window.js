const __ = window.__ || ((text) => text)

const DEFAULT_LOGO = "/assets/do_derma/images/derma-one-logo.png"

/**
 * Prints `bodyHtml` in a new window under the Derma One letterhead (same as the note and
 * letters, do_derma/printing/letterhead.py): logo on top, company block fixed to the foot of
 * every sheet above a repeating spacer. The caller escapes everything it interpolates into
 * `bodyHtml`; `title` and `logoUrl` are escaped here.
 */
export function printHtml(title, bodyHtml, { logoUrl = "" } = {}) {
  const printWindow = window.open("", "_blank")
  if (!printWindow) {
    frappe.show_alert({ message: __("Allow pop-ups to print."), indicator: "orange" })
    return
  }
  const escape = frappe.utils.escape_html
  printWindow.document.write(`<!doctype html>
    <html><head><title>${escape(title || "")}</title>
    <style>
      @page { size: A4; margin: 10mm 12mm 0; }
      .derma-letterhead { width: 100%; border-collapse: collapse; }
      .derma-letterhead td { padding: 0; }
      .derma-letterhead-foot { position: fixed; left: 0; right: 0; bottom: 0; padding-bottom: 12mm; text-align: center; color: #222; font: 10px/1.5 Arial, sans-serif; }
      .derma-letterhead-foot b { display: block; font: 11px Georgia, "Times New Roman", serif; letter-spacing: 4px; margin-bottom: 5px; }
    </style></head>
    <body style="font-family:sans-serif;margin:0;">
      <table class="derma-letterhead"><tfoot><tr><td><div style="height:42mm;"></div></td></tr></tfoot><tbody><tr><td>
        <div style="text-align:center;margin:0 0 20px;"><img src="${escape(logoUrl || DEFAULT_LOGO)}" alt="Logo" style="max-width:290px;max-height:66px;width:auto;height:auto;"></div>
        ${bodyHtml}
      </td></tr></tbody></table>
      <div class="derma-letterhead-foot"><b>DERMA ONE MEDICAL CENTRE W.L.L.</b>
        P.O. Box 31008, Floors 6 &amp; 7, Bldg 71, Road 3201, Block 332, Kingdom of Bahrain<br>
        Tel: +973 1724 0042 &nbsp; Email: info@dermaonecentre.com &nbsp; CR No. 100506-1<br>
        www.dermaonecentre.com</div>
    </body></html>`)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => printWindow.print(), 350)
}

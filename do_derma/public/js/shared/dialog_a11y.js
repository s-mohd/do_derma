const __ = window.__ || ((text) => text)

/**
 * Names a dialog's controls for assistive technology. Frappe renders a control's label
 * without a `for`, so the accessibility tree shows bare `combobox` / `textbox` entries and
 * an unnamed close button. Call once, after the dialog is shown.
 */
export function nameDialogControls(dialog) {
  if (!dialog?.$wrapper) return
  for (const field of Object.values(dialog.fields_dict || {})) {
    const input = field.$input?.get?.(0)
    const label = field.df?.label
    if (input && label && !input.getAttribute("aria-label")) input.setAttribute("aria-label", label)
  }
  const close = dialog.$wrapper.find(".modal-header .btn-modal-close").get(0)
  if (close && !close.getAttribute("aria-label")) close.setAttribute("aria-label", __("Close"))
}

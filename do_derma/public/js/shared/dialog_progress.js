/**
 * Runs a dialog's primary action with in-flight feedback. The dialog stays open, saying what
 * it is doing, until the work finishes, so the pause between the click and the refreshed page
 * is explained and the button cannot be pressed twice.
 *
 * @param {object} dialog frappe.ui.Dialog the action was fired from
 * @param {string} message What to show while the work runs
 * @param {() => Promise<unknown>} action The work itself. Return `false` to keep the dialog
 *   open, for work that failed in a way the clinician still has to act on.
 * @returns {Promise<void>}
 */
export async function runDialogAction(dialog, message, action) {
  dialog?.disable_primary_action?.()
  dialog?.set_message?.(message)
  try {
    if ((await action()) !== false) dialog?.hide?.()
  } finally {
    dialog?.clear_message?.()
    dialog?.enable_primary_action?.()
  }
}

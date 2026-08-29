// Frappe's disable_primary_action only adds Bootstrap's `.disabled` class, which dims a
// <button> without stopping its click, so the button is disabled through the DOM property here.
const inFlight = new WeakSet()

/**
 * Runs a dialog's primary action with in-flight feedback. The dialog stays open, saying what
 * it is doing, until the work finishes, so the pause between the click and the refreshed page
 * is explained and the action cannot be fired twice.
 *
 * @param {object} dialog frappe.ui.Dialog the action was fired from
 * @param {string} message What to show while the work runs
 * @param {() => Promise<unknown>} action The work itself. Return `false` to keep the dialog
 *   open, for work that failed in a way the clinician still has to act on.
 * @returns {Promise<void>}
 */
export async function runDialogAction(dialog, message, action) {
  if (!dialog || inFlight.has(dialog)) return
  inFlight.add(dialog)
  const button = dialog.get_primary_btn?.()?.get?.(0)
  if (button) button.disabled = true
  dialog.disable_primary_action?.()
  dialog.set_message?.(message)
  try {
    if ((await action()) !== false) dialog.hide?.()
  } finally {
    inFlight.delete(dialog)
    if (button) button.disabled = false
    dialog.clear_message?.()
    dialog.enable_primary_action?.()
  }
}

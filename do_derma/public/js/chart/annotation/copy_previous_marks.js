import { describeError } from "../../shared/error_text.js"

const __ = window.__ || ((txt) => txt)

/** The variable fields a mark carries on itself, alongside its `procedure_variables` rows. */
const MARK_VARIABLE_FIELDS = [
  "product_item",
  "product_name",
  "dose",
  "dose_unit",
  "plane",
  "technique",
  "device",
  "settings",
  "passes",
  "lot_no",
  "expiry_date",
  "lesion_id",
  "diagnosis",
  "severity",
  "status",
]

/** What the picker calls a mark: "#2 Botox - Forehead", never its autoname. */
export function markCopyLabel(mark) {
  const detail = [mark?.procedure_template || mark?.category, mark?.region_label || mark?.body_region]
    .filter(Boolean)
    .join(" — ")
  const number = mark?.sequence ? `#${mark.sequence}` : ""
  return [number, detail].filter(Boolean).join(" ") || __("Mark")
}

/**
 * The `save_chart_mark` payload that reproduces a mark on the drawing now open.
 *
 * `annotation` and `annotation_json` are deliberately absent. The first is stamped by the
 * save that adopts the copy, and the second is the idempotency key the annotation fan-out
 * matches elements to marks by - copying it would point two marks at one element.
 */
export function markCopyValues(source, context) {
  const values = {
    patient: context.patient,
    appointment: context.appointment,
    encounter: context.encounter,
    clinical_procedure: context.clinicalProcedure || null,
    procedure_template: source.procedure_template,
    category: source.category,
    marker_behavior: source.marker_behavior,
    marker_color: source.marker_color,
    marker_size: source.marker_size,
    body_template: source.body_template,
    body_view: source.body_view,
    body_region: source.body_region,
    region_label: source.region_label,
    body_template_part: source.body_template_part || null,
    x_percent: source.x_percent,
    y_percent: source.y_percent,
    procedure_variables: ownVariables(source),
  }
  for (const field of MARK_VARIABLE_FIELDS) {
    if (source[field] !== undefined && source[field] !== null) values[field] = source[field]
  }
  return values
}

/**
 * Only what the source mark answered for itself. A value it merely borrowed belongs to *that*
 * visit's procedure, and copying it forward would pin last visit's dose or lot number onto this
 * visit as this mark's own - past the new procedure's own answer, and invisibly.
 */
function ownVariables(source) {
  const inherited = source.inherited_variables || {}
  return Object.fromEntries(
    Object.entries(source.procedure_variables || {}).filter(([fieldname]) => !(fieldname in inherited))
  )
}

/**
 * Copies the chosen marks onto the open drawing, one `save_chart_mark` each - the same call
 * placing a mark by hand makes. Resolves with the marks the server created, in the order
 * they were asked for; a mark the server refuses is reported and skipped, so one bad row
 * does not cost the practitioner the rest of the copy.
 */
export async function copyMarksIntoDrawing(sources, context) {
  const created = []
  const failed = []
  for (const source of sources) {
    try {
      const response = await window.frappe.call({
        method: "do_derma.api.save_chart_mark",
        args: { values: markCopyValues(source, context) },
      })
      if (response?.message?.name) created.push(response.message)
    } catch (error) {
      failed.push(`${markCopyLabel(source)}: ${describeError(error)}`)
    }
  }
  if (failed.length) {
    window.frappe?.msgprint?.({
      title: __("Some marks were not copied"),
      message: failed.join("<br>"),
      indicator: "orange",
    })
  }
  return created
}

/**
 * Asks which of the previous drawing's marks to bring over, then copies them. Mirrors the
 * chart's own "Copy marks from last visit" picker: every mark checked, nothing copied until
 * the practitioner confirms.
 */
export function openCopyPreviousMarksDialog({ marks, context, onCopied }) {
  const candidates = marks || []
  if (!candidates.length) return null
  const dialog = new window.frappe.ui.Dialog({
    title: __("Copy marks from the previous drawing"),
    fields: [
      {
        fieldname: "marks",
        fieldtype: "MultiCheck",
        label: __("Marks"),
        columns: 1,
        options: candidates.map((mark) => ({
          label: markCopyLabel(mark),
          value: mark.name,
          checked: 1,
        })),
      },
    ],
    primary_action_label: __("Copy"),
    primary_action: async ({ marks: selected }) => {
      if (!selected?.length) {
        window.frappe.msgprint(__("Select at least one mark to copy."))
        return
      }
      const chosen = candidates.filter((mark) => selected.includes(mark.name))
      dialog.get_primary_btn().prop("disabled", true)
      try {
        const created = await copyMarksIntoDrawing(chosen, context)
        dialog.hide()
        if (created.length) {
          onCopied?.(created)
          window.frappe.show_alert?.({
            message: __("Copied {0} mark(s).").replace("{0}", created.length),
            indicator: "green",
          })
        }
      } finally {
        dialog.get_primary_btn().prop("disabled", false)
      }
    },
  })
  dialog.show()
  return dialog
}

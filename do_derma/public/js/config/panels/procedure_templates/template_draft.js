/** The editable shape of a procedure template, keyed the way `save_derma_procedure_template`
 * reads it. One owner for what the detail view sends. */

export const MARKER_COLOR_PRESETS = [
  "#0f766e",
  "#2563eb",
  "#b91c1c",
  "#c2410c",
  "#7c3aed",
  "#0891b2",
  "#15803d",
  "#334155",
]

export const SAFETY_FLAGS = [
  { key: "consent_required", label: "Consent required" },
  { key: "before_after_photo_required", label: "Before / after photo required" },
  { key: "product_tracking_required", label: "Product / lot required" },
  { key: "device_settings_required", label: "Device settings required" },
]

const EDITABLE_KEYS = [
  "template",
  "description",
  "item_group",
  "medical_department",
  "category",
  "marker_behavior",
  "marker_color",
  "marker_size",
  "note_template",
  ...SAFETY_FLAGS.map((flag) => flag.key),
  "is_billable",
  "disabled",
  "rate",
]

export function blankTemplateDraft() {
  return {
    template: "",
    description: "",
    item_group: "",
    medical_department: "",
    category: "",
    marker_behavior: "",
    marker_color: "",
    marker_size: 0,
    note_template: "",
    consent_required: 0,
    before_after_photo_required: 0,
    product_tracking_required: 0,
    device_settings_required: 0,
    is_billable: 1,
    disabled: 0,
    rate: 0,
    allowed_body_templates: [],
    variables: [],
  }
}

export function templateDraft(payload = {}) {
  const draft = blankTemplateDraft()
  for (const key of EDITABLE_KEYS) {
    if (key in payload) draft[key] = payload[key]
  }
  draft.allowed_body_templates = [...(payload.allowed_body_templates || [])]
  draft.variables = (payload.variables || []).map((variable) => ({ ...variable }))
  return draft
}

<template>
  <section class="workspace-panel prescription-panel">
    <header class="panel-header">
      <div class="actions">
        <button type="button" class="ghost" :disabled="loading || saving" @click="$emit('refresh')">{{ __("Refresh") }}</button>
        <button
          type="button"
          class="primary"
          :disabled="loading || saving || !canSave"
          @click="emitSave"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </div>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="loading" class="empty-state">{{ __("Loading prescriptions...") }}</div>
    <div v-else-if="!hasSessionContext" class="empty-state">
      {{ __("Prescriptions are visit-scoped. Select or start an appointment session first.") }}
    </div>
    <div v-else-if="!hasEncounter" class="empty-state">
      {{ __("No encounter found for this session.") }}
    </div>
    <div v-else>
      <div ref="tableHost" class="table-host"></div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  hasEncounter: { type: Boolean, default: false },
  encounterName: { type: String, default: "" },
  rows: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["refresh", "save"])

const tableHost = ref(null)
let tableControl = null
const dirtyRows = ref([])
let renderQueued = false

const canSave = computed(() => props.hasSessionContext && props.hasEncounter && !props.readOnly)

watch(
  () => [props.rows, props.hasEncounter, props.hasSessionContext, props.readOnly],
  () => {
    scheduleRender()
  },
  { deep: true, immediate: true }
)

onBeforeUnmount(() => {
  destroyControl()
})

function normalizeRows(rows) {
  return (rows || []).map((row) => ({
    name: row.name || "",
    medication: row.medication || "",
    drug_code: row.drug_code || "",
    drug_name: row.drug_name || "",
    dosage: row.dosage || "",
    period: row.period || "",
    dosage_form: row.dosage_form || "",
    comment: row.comment || "",
    number_of_repeats_allowed: row.number_of_repeats_allowed ?? "",
    interval: row.interval ?? "",
    interval_uom: row.interval_uom || "",
    dosage_by_interval: row.dosage_by_interval ?? 0,
    intent: row.intent || "",
    priority: row.priority || "",
    strength: row.strength ?? "",
    strength_uom: row.strength_uom || "",
  }))
}

function scheduleRender() {
  if (renderQueued) return
  renderQueued = true
  Promise.resolve().then(async () => {
    renderQueued = false
    await renderTable()
  })
}

function destroyControl() {
  if (!tableControl) return
  try {
    tableControl.$wrapper?.remove()
  } catch (e) {
    /* no-op */
  }
  tableControl = null
}

async function onMedicationChange() {
  const row = this?.doc || this?.grid_row?.doc
  const medication = row?.medication || ""
  if (!row) return

  if (!medication) {
    row.drug_code = ""
    row.dosage = ""
    row.period = ""
    row.dosage_form = ""
    this?.grid_row?.refresh_field("drug_code")
    this?.grid_row?.refresh_field("dosage")
    this?.grid_row?.refresh_field("period")
    this?.grid_row?.refresh_field("dosage_form")
    syncDirtyRows()
    return
  }

  try {
    const [medicationsResp, defaultsResp] = await Promise.all([
      frappe.call("healthcare.healthcare.doctype.patient_encounter.patient_encounter.get_medications", {
        medication,
      }),
      frappe.db.get_value("Medication", medication, [
        "default_prescription_dosage",
        "default_prescription_duration",
        "dosage_form",
      ]),
    ])

    const linkedItems = medicationsResp?.message || []
    if (linkedItems.length === 1 && linkedItems[0]?.item) {
      row.drug_code = linkedItems[0].item
    } else if (!linkedItems.some((entry) => entry?.item === row.drug_code)) {
      row.drug_code = ""
    }

    const defaults = defaultsResp?.message || {}
    row.dosage = defaults.default_prescription_dosage || ""
    row.period = defaults.default_prescription_duration || ""
    row.dosage_form = defaults.dosage_form || ""

    this?.grid_row?.refresh_field("drug_code")
    this?.grid_row?.refresh_field("dosage")
    this?.grid_row?.refresh_field("period")
    this?.grid_row?.refresh_field("dosage_form")
    syncDirtyRows()
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("Failed to apply medication defaults", err)
  }
}

function syncDirtyRows() {
  if (!tableControl?.grid) {
    dirtyRows.value = normalizeRows(props.rows || [])
    return
  }
  dirtyRows.value = normalizeRows(tableControl.grid.get_data?.() || tableControl.grid.df?.data || [])
}

async function renderTable() {
  if (!tableHost.value || !props.hasEncounter || !props.hasSessionContext) {
    destroyControl()
    dirtyRows.value = normalizeRows(props.rows || [])
    return
  }

  await new Promise((resolve) => {
    frappe.model.with_doctype("Drug Prescription", () => resolve())
  })

  await nextTick()
  if (!tableHost.value) return

  destroyControl()
  tableHost.value.innerHTML = ""

  const readOnly = props.readOnly ? 1 : 0
  tableControl = frappe.ui.form.make_control({
    parent: tableHost.value,
    render_input: true,
    doc: { doctype: "Patient Encounter" },
    df: {
      fieldname: "drug_prescription",
      fieldtype: "Table",
      label: __("Drug Prescription"),
      options: "Drug Prescription",
      read_only: readOnly,
      in_place_edit: 0,
      cannot_add_rows: props.readOnly ? 1 : 0,
      cannot_delete_rows: props.readOnly ? 1 : 0,
      fields: [
        {
          fieldname: "medication",
          fieldtype: "Link",
          options: "Medication",
          label: __("Medication"),
          in_list_view: 1,
          columns: 4,
          onchange: onMedicationChange,
        },
        {
          fieldname: "drug_code",
          fieldtype: "Link",
          options: "Item",
          label: __("Drug Code"),
          in_list_view: 1,
          columns: 2,
        },
        {
          fieldname: "drug_name",
          fieldtype: "Data",
          label: __("Drug Name / Description"),
          in_list_view: 0,
          columns: 4,
          read_only: 1,
        },
        {
          fieldname: "dosage",
          fieldtype: "Link",
          options: "Prescription Dosage",
          label: __("Dosage"),
          in_list_view: 1,
          columns: 1,
        },
        {
          fieldname: "period",
          fieldtype: "Link",
          options: "Prescription Duration",
          label: __("Period"),
          in_list_view: 1,
          columns: 1,
        },
        {
          fieldname: "dosage_form",
          fieldtype: "Link",
          options: "Dosage Form",
          label: __("Dosage Form"),
          in_list_view: 1,
          columns: 1,
        },
        {
          fieldname: "number_of_repeats_allowed",
          fieldtype: "Float",
          label: __("Repeats"),
          in_list_view: 1,
          columns: 1,
        },
        {
          fieldname: "comment",
          fieldtype: "Small Text",
          label: __("Comment"),
          in_list_view: 0,
          columns: 4,
        },
      ],
    },
  })

  const grid = tableControl.grid
  if (grid) {
    grid.df.data = normalizeRows(props.rows || [])
    grid.refresh()
    tableControl.$wrapper?.on?.("input change blur", "input, textarea, select, .form-control", syncDirtyRows)
  }

  syncDirtyRows()
}

function emitSave() {
  if (!canSave.value || props.saving || props.loading) return
  syncDirtyRows()
  emit("save", normalizeRows(dirtyRows.value || []))
}
</script>

<style scoped>
.workspace-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}

.panel-header {
  display: flex;
  justify-content: end;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.panel-header .meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.actions {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

button {
  border-radius: 8px;
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

button.ghost {
  background: #f8fafc;
  color: #334155;
}

button.primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-text {
  color: #b91c1c;
  font-size: 12px;
  margin: 0 0 8px;
}

.empty-state {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 12px;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
}

.table-host:deep(.frappe-control) {
  margin-bottom: 0;
}
</style>

<template>
  <section class="workspace-panel anesthesia-panel">
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

    <div v-if="loading" class="empty-state">{{ __("Loading anesthesia...") }}</div>
    <div v-else-if="!hasSessionContext" class="empty-state">
      {{ __("Anesthesia is visit-scoped. Select or start an appointment session first.") }}
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
  typeOptions: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["refresh", "save"])

const tableHost = ref(null)
let tableControl = null
const dirtyRows = ref([])
let renderQueued = false

const canSave = computed(() => props.hasSessionContext && props.hasEncounter && !props.readOnly)

watch(
  () => [props.rows, props.typeOptions, props.hasEncounter, props.hasSessionContext, props.readOnly],
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
    anesthesia_type: row.anesthesia_type || "",
    cartridge: row.cartridge ?? "",
    notes: row.notes || "",
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
    frappe.model.with_doctype("Dental Anesthesia", () => resolve())
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
      fieldname: "custom_dental_anesthesia",
      fieldtype: "Table",
      label: __("Anesthesia"),
      options: "Dental Anesthesia",
      read_only: readOnly,
      in_place_edit: 0,
      cannot_add_rows: props.readOnly ? 1 : 0,
      cannot_delete_rows: props.readOnly ? 1 : 0,
      fields: [
        {
          fieldname: "anesthesia_type",
          fieldtype: "Select",
          label: __("Type"),
          options: (props.typeOptions || []).join("\n"),
          in_list_view: 1,
          columns: 3,
        },
        {
          fieldname: "cartridge",
          fieldtype: "Int",
          label: __("Cartridge"),
          in_list_view: 1,
          columns: 2,
        },
        {
          fieldname: "notes",
          fieldtype: "Small Text",
          label: __("Notes"),
          in_list_view: 1,
          columns: 6,
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

.table-host:deep(.form-grid .grid-heading-row [data-fieldname="cartridge"]),
.table-host:deep(.form-grid .grid-body [data-fieldname="cartridge"]) {
  text-align: left !important;
}

.table-host:deep(.form-grid .grid-body [data-fieldname="cartridge"] .static-area),
.table-host:deep(.form-grid .grid-body [data-fieldname="cartridge"] input.form-control) {
  text-align: left !important;
}
</style>

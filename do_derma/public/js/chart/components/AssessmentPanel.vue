<template>
  <section class="assessment-panel">
    <header class="assessment-header">
      <div class="header-actions">
        <button type="button" class="ghost" @click="$emit('refresh')">{{ __("Refresh") }}</button>

        <button
          v-if="!hasEncounter"
          type="button"
          class="primary"
          :disabled="loading || saving || !canStartEditing"
          @click="$emit('request-edit')"
        >
          {{ __("Start Assessment") }}
        </button>

        <button
          v-else-if="!editMode && canStartEditing"
          type="button"
          class="ghost"
          :disabled="loading || saving"
          @click="$emit('request-edit')"
        >
          {{ __("Edit Assessment") }}
        </button>

        <template v-else-if="editMode">
          <button
            type="button"
            class="primary"
            :disabled="loading || saving"
            @click="submitDraft"
          >
            {{ saving ? __("Saving...") : __("Save") }}
          </button>
        </template>
      </div>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-if="hasEncounter && Number(docstatus ?? 0) === 1 && !allowOnSubmitFields.length" class="status-note">
      {{ __("Encounter is submitted. No assessment fields are marked Allow on Submit.") }}
    </p>
    <p v-else-if="hasEncounter && Number(docstatus ?? 0) === 1" class="status-note">
      {{ __("Encounter is submitted. Only Allow on Submit fields are editable.") }}
    </p>
    <p v-else-if="hasEncounter && Number(docstatus ?? 0) === 2" class="status-note">
      {{ __("Encounter is cancelled. Assessment is read-only.") }}
    </p>

    <div v-if="loading" class="empty-state">
      {{ __("Loading assessment...") }}
    </div>

    <div v-else-if="!layout.length" class="empty-state">
      {{ __("No fields found in Patient Encounter tab custom_assessment.") }}
    </div>

    <div v-else-if="!hasEncounter" class="empty-state">
      <p>{{ __("No encounter yet for this appointment.") }}</p>
      <p class="hint">{{ __("Click Start Assessment to create an encounter and continue here.") }}</p>
    </div>

    <div v-else class="assessment-sections">
      <section
        v-for="(section, sectionIndex) in layoutSections"
        :key="section.key"
        class="assessment-section"
        :class="{ 'has-separator': sectionIndex > 0 }"
      >
        <h4 v-if="section.label" class="assessment-section-title">{{ section.label }}</h4>

        <div
          class="assessment-columns"
          :style="{
            '--assessment-columns': String(section.columns.length || 1),
          }"
        >
          <section
            v-for="(column, colIdx) in section.columns"
            :key="`${section.key}-column-${colIdx}`"
            class="assessment-column"
          >
            <div
              v-for="field in column"
              :key="field.layout_key || field.fieldname"
              class="assessment-field"
            >
              <div class="field-control-host" :ref="(el) => bindFieldHost(field.fieldname, el)"></div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const TABLE_FIELD_TYPES = new Set(["Table", "Table MultiSelect"])
const LAYOUT_BREAK_FIELD_TYPES = new Set(["Section Break", "Column Break"])
const NO_VALUE_FIELD_TYPES = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "Button",
  "Image",
  "HTML",
  "Fold",
  "Heading",
])

const props = defineProps({
  layout: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  contextValues: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasEncounter: { type: Boolean, default: false },
  encounterName: { type: String, default: "" },
  docstatus: { type: [Number, null], default: null },
  editMode: { type: Boolean, default: false },
  allowOnSubmitFields: { type: Array, default: () => [] },
})

const emit = defineEmits(["request-edit", "save", "refresh"])

const fieldHosts = new Map()
const controls = new Map()
let workingDoc = {}
let renderToken = 0
let refreshQueued = false
let dirtySyncTimer = null
let dirtySyncRunning = false
const savedSignature = ref("")
const isDirty = ref(false)
const runtimeValues = ref({})
const runtimeSignature = ref("")
const evaluationDoc = computed(() => {
  const values = props.editMode ? runtimeValues.value || {} : props.values || {}
  return { ...(props.contextValues || {}), ...(values || {}) }
})
const allowOnSubmitSet = computed(() => new Set((props.allowOnSubmitFields || []).filter(Boolean)))
const isSubmittedEncounter = computed(() => Number(props.docstatus ?? 0) === 1)
const canEditEncounter = computed(() => {
  if (!props.hasEncounter) return false
  const status = Number(props.docstatus ?? 0)
  if (status === 0) return true
  if (status === 1) return allowOnSubmitSet.value.size > 0
  return false
})

const canStartEditing = computed(() => {
  if (!props.layout.length) return false
  if (!props.hasEncounter) return true
  return canEditEncounter.value
})

const visibleLayout = computed(() => {
  const source = props.layout || []
  const values = props.editMode ? runtimeValues.value || {} : props.values || {}
  const contextDoc = evaluationDoc.value || {}
  let currentSectionVisible = true
  let currentSectionReadOnly = false
  const filtered = []

  for (const field of source) {
    if (!field) continue

    const isHidden = Number(field.hidden || 0) === 1
    const dependsVisible = field.depends_on ? evaluateDependsOn(field.depends_on, contextDoc) : true
    const rowVisible = !isHidden && dependsVisible
    const fieldtype = field.fieldtype || ""

    if (fieldtype === "Section Break") {
      currentSectionVisible = rowVisible
      currentSectionReadOnly = rowVisible ? isRowReadOnly(field, contextDoc) : false
      if (rowVisible) {
        filtered.push({
          ...field,
          _inherited_read_only: currentSectionReadOnly ? 1 : 0,
        })
      }
      continue
    }

    if (!currentSectionVisible || !rowVisible) {
      continue
    }

    if (!props.editMode && field?.is_value_field) {
      if (!field?.fieldname) continue
      if (!field.show_if_empty && !hasContent(values[field.fieldname])) {
        continue
      }
    }

    if (currentSectionReadOnly && field?.is_value_field) {
      filtered.push({
        ...field,
        _inherited_read_only: 1,
      })
    } else {
      filtered.push(field)
    }
  }

  return filtered
})

const layoutSections = computed(() => {
  const sections = []
  let sectionIndex = 0
  let current = {
    key: "section-0",
    label: "",
    columns: [[]],
  }

  const pushSection = () => {
    const hasFields = (current.columns || []).some((col) => col.length)
    if (!hasFields && !current.label) return
    current.columns = (current.columns || []).filter((col) => col.length)
    if (!current.columns.length) current.columns = [[]]
    sections.push(current)
  }

  for (const row of visibleLayout.value || []) {
    const fieldtype = row?.fieldtype || ""

    if (fieldtype === "Section Break") {
      pushSection()
      sectionIndex += 1
      current = {
        key: row.layout_key || `section-${sectionIndex}`,
        label: row.label || "",
        columns: [[]],
      }
      continue
    }

    if (fieldtype === "Column Break") {
      current.columns.push([])
      continue
    }

    if (!row?.is_value_field || !row?.fieldname || LAYOUT_BREAK_FIELD_TYPES.has(fieldtype)) {
      continue
    }

    if (!current.columns.length) current.columns = [[]]
    current.columns[current.columns.length - 1].push(row)
  }

  pushSection()
  return sections
})

const layoutRenderSignature = computed(() =>
  JSON.stringify(
    (layoutSections.value || []).map((section) => ({
      key: section.key,
      label: section.label,
      columns: (section.columns || []).map((col) =>
        col.map((row) => row.layout_key || row.fieldname || String(row.idx || ""))
      ),
    }))
  )
)

watch(
  () => [props.layout, props.editMode, props.hasEncounter, props.docstatus, props.allowOnSubmitFields],
  () => {
    scheduleRefreshControls()
  },
  { deep: true, immediate: true }
)

watch(
  () => props.values,
  (values) => {
    const cloned = cloneObject(values || {})
    runtimeValues.value = cloned
    runtimeSignature.value = payloadSignature(cloned)
  },
  { deep: true, immediate: true }
)

watch(
  () => layoutRenderSignature.value,
  () => {
    scheduleRefreshControls()
  }
)

watch(
  () => [props.editMode, props.hasEncounter],
  () => {
    if (props.editMode && props.hasEncounter) {
      syncDirtyFlag()
      return
    }
    stopDirtySync()
    isDirty.value = false
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  stopDirtySync()
  teardownAllControls()
})

function bindFieldHost(fieldname, el) {
  if (el) {
    fieldHosts.set(fieldname, el)
    return
  }

  fieldHosts.delete(fieldname)
  teardownControl(fieldname)
}

function scheduleRefreshControls() {
  if (refreshQueued) return
  refreshQueued = true
  Promise.resolve().then(() => {
    refreshQueued = false
    refreshControls()
  })
}

function hasContent(value) {
  if (value === null || value === undefined) return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === "string") return Boolean(value.trim())
  return true
}

function cloneRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.map((row) => ({ ...(row || {}) }))
}

function cloneObject(value) {
  if (!value || typeof value !== "object") return {}
  try {
    return JSON.parse(JSON.stringify(value))
  } catch (e) {
    return { ...value }
  }
}

function defaultValue(field) {
  return TABLE_FIELD_TYPES.has(field?.fieldtype) ? [] : ""
}

function isRowReadOnly(row, doc = {}) {
  const base = Number(row?.read_only || 0) === 1
  const conditional = row?.read_only_depends_on ? evaluateDependsOn(row.read_only_depends_on, doc) : false
  return base || conditional
}

function isPastVisitField(fieldname) {
  return typeof fieldname === "string" && fieldname.startsWith("custom_past_visit_")
}

function evaluateDependsOn(expression, doc = {}) {
  if (!expression) return true
  if (typeof expression === "boolean") return expression
  if (typeof expression === "function") return Boolean(expression(doc))
  if (typeof expression !== "string") return true

  if (expression.startsWith("eval:")) {
    try {
      return Boolean(frappe?.utils?.eval?.(expression.slice(5), { doc, parent: doc }))
    } catch (e) {
      return false
    }
  }

  const value = doc?.[expression]
  return Array.isArray(value) ? value.length > 0 : Boolean(value)
}

function payloadSignature(payload) {
  try {
    return JSON.stringify(payload || {})
  } catch (e) {
    return ""
  }
}

function stopDirtySync() {
  if (dirtySyncTimer) {
    clearTimeout(dirtySyncTimer)
    dirtySyncTimer = null
  }
}

function scheduleDirtySync() {
  stopDirtySync()
  dirtySyncTimer = setTimeout(() => {
    dirtySyncTimer = null
    syncDirtyFlag()
  }, 180)
}

function teardownControl(fieldname) {
  const control = controls.get(fieldname)
  if (!control) return
  try {
    control.$wrapper?.remove()
  } catch (e) {
    /* no-op */
  }
  controls.delete(fieldname)
}

function teardownAllControls() {
  for (const fieldname of controls.keys()) {
    teardownControl(fieldname)
  }
}

function withDoctype(doctype) {
  if (!doctype || !frappe?.model?.with_doctype) {
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    try {
      frappe.model.with_doctype(doctype, () => resolve())
    } catch (e) {
      resolve()
    }
  })
}

async function ensureMetaLoaded() {
  await withDoctype("Patient Encounter")

  const tableOptions = new Set()
  for (const row of props.layout || []) {
    if (!row?.is_value_field) continue
    if (TABLE_FIELD_TYPES.has(row?.fieldtype) && row?.options) {
      tableOptions.add(row.options)
    }
  }

  for (const childDoctype of tableOptions) {
    await withDoctype(childDoctype)
  }
}

function buildWorkingDoc() {
  const doc = { doctype: "Patient Encounter" }
  const sourceValues = props.editMode ? runtimeValues.value || {} : props.values || {}
  for (const row of props.layout || []) {
    if (!row?.is_value_field) continue
    const fieldname = row?.fieldname
    if (!fieldname) continue

    const sourceValue = sourceValues?.[fieldname]
    if (TABLE_FIELD_TYPES.has(row?.fieldtype)) {
      doc[fieldname] = cloneRows(sourceValue)
    } else {
      doc[fieldname] = sourceValue === null || sourceValue === undefined ? "" : sourceValue
    }
  }
  workingDoc = doc
}

function buildControlDf(row) {
  if (!row?.is_value_field) return null
  const fieldname = row?.fieldname
  if (!fieldname) return null

  const metaDf = frappe?.meta?.get_docfield?.("Patient Encounter", fieldname) || {}
  const fieldtype = metaDf.fieldtype || row.fieldtype || "Data"
  const df = {
    ...metaDf,
    fieldname,
    fieldtype,
    label: metaDf.label || row.label || fieldname,
    options: metaDf.options || row.options || "",
    hidden: 0,
    read_only: 1,
    reqd: Number(metaDf.reqd || 0),
  }
  if (props.editMode) {
    const source = {
      ...(props.contextValues || {}),
      ...(Object.keys(workingDoc || {}).length ? workingDoc : runtimeValues.value || props.values || {}),
    }
    const rowReadOnly = isRowReadOnly(row, source)
    const inheritedReadOnly = Number(row?._inherited_read_only || 0) === 1
    const metaReadOnly = Number(metaDf.read_only || 0) === 1
    const forcedReadOnly = isPastVisitField(fieldname)
    const submittedNotAllowed = isSubmittedEncounter.value && !allowOnSubmitSet.value.has(fieldname)
    df.read_only = rowReadOnly || inheritedReadOnly || metaReadOnly || forcedReadOnly || submittedNotAllowed ? 1 : 0
  } else {
    df.read_only = 1
  }
  if (props.editMode && row.mandatory_depends_on) {
    const source = {
      ...(props.contextValues || {}),
      ...(Object.keys(workingDoc || {}).length ? workingDoc : runtimeValues.value || props.values || {}),
    }
    df.reqd = evaluateDependsOn(row.mandatory_depends_on, source) ? 1 : 0
  }

  if (fieldtype === "Table") {
    const childMeta = df.options ? frappe.get_meta(df.options) : null
    const childFields = childMeta?.fields || []
    df.fields = childFields.filter((childDf) => !NO_VALUE_FIELD_TYPES.has(childDf.fieldtype))
    df.data = cloneRows(workingDoc[fieldname])
    const tableReadOnly = Number(df.read_only || 0) === 1
    df.cannot_add_rows = tableReadOnly ? 1 : 0
    df.cannot_delete_rows = tableReadOnly ? 1 : 0
    df.in_place_edit = tableReadOnly ? 0 : 1
  }

  return df
}

async function makeControl(row) {
  const host = fieldHosts.get(row.fieldname)
  if (!host) return

  const df = buildControlDf(row)
  if (!df) return

  host.innerHTML = ""

  const control = frappe?.ui?.form?.make_control?.({
    parent: host,
    df,
    doc: workingDoc,
    render_input: true,
  })

  if (!control) return
  const updateRuntimeValue = () => {
    if (!props.editMode || !row?.fieldname) return
    if (!runtimeValues.value || typeof runtimeValues.value !== "object") {
      runtimeValues.value = {}
    }
    if (df.fieldtype === "Table MultiSelect") {
      runtimeValues.value[row.fieldname] = cloneRows(control?.rows || [])
      return
    }
    if (df.fieldtype === "Table") {
      runtimeValues.value[row.fieldname] = cloneRows(control?.grid?.df?.data || [])
      return
    }
    runtimeValues.value[row.fieldname] = control?.get_value ? control.get_value() : workingDoc[row.fieldname]
  }
  const markDirty = () => {
    if (!props.editMode || !props.hasEncounter) return
    updateRuntimeValue()
    scheduleDirtySync()
  }
  control.$input?.on?.("input change keyup blur", markDirty)
  control.$wrapper?.on?.("input", "input, textarea, select, .form-control", markDirty)
  control.$wrapper?.on?.("change", "input, textarea, select, .form-control", markDirty)
  control.$wrapper?.on?.("keyup", "input, textarea", markDirty)

  if (df.fieldtype === "Table MultiSelect") {
    const initialRows = cloneRows(workingDoc[row.fieldname])
    const originalUpdateRows = control._update_rows?.bind(control)
    control._update_rows = function (rows) {
      const nextRows = Array.isArray(rows) ? rows : []
      if (originalUpdateRows) {
        originalUpdateRows(nextRows)
      } else {
        this.rows = nextRows
      }
      if (this.doc) {
        this.doc[this.df.fieldname] = cloneRows(nextRows)
      }
      markDirty()
      return nextRows
    }
    control._update_rows(initialRows)
    if (control.doc) {
      control.doc[df.fieldname] = cloneRows(initialRows)
    }
    control.refresh?.()
  }

  if (df.fieldtype === "Table" && control.grid) {
    control.grid.df.data = cloneRows(workingDoc[row.fieldname])
    control.refresh()
  }

  controls.set(row.fieldname, control)
}

function collectPayload() {
  const payload = {}
  const onlyAllowOnSubmitFields = isSubmittedEncounter.value

  for (const row of props.layout || []) {
    if (!row?.is_value_field) continue
    const fieldname = row?.fieldname
    if (!fieldname) continue
    if (onlyAllowOnSubmitFields && !allowOnSubmitSet.value.has(fieldname)) continue

    const control = controls.get(fieldname)
    let value

    if (row?.fieldtype === "Table MultiSelect") {
      value = Array.isArray(control?.rows)
        ? cloneRows(control.rows)
        : cloneRows(control?.get_model_value?.() || [])
    } else if (control?.get_value) {
      value = control.get_value()
    } else {
      value = workingDoc[fieldname]
    }

    if (TABLE_FIELD_TYPES.has(row?.fieldtype)) {
      payload[fieldname] = cloneRows(value)
    } else {
      payload[fieldname] = value ?? defaultValue(row)
    }
  }

  return payload
}

function syncDirtyFlag() {
  if (dirtySyncRunning) return
  dirtySyncRunning = true
  try {
    if (!props.editMode || !props.hasEncounter) {
      isDirty.value = false
      return
    }

    const payload = collectPayload()
    const current = payloadSignature(payload)
    runtimeSignature.value = current
    isDirty.value = Boolean(current && current !== savedSignature.value)
  } finally {
    dirtySyncRunning = false
  }
}

function submitDraft() {
  if (!props.editMode || !props.hasEncounter || props.saving) return
  const payload = collectPayload()
  const signature = payloadSignature(payload)
  emit("save", payload)
  savedSignature.value = signature
  isDirty.value = false
}

async function refreshControls() {
  const token = ++renderToken

  if (!props.hasEncounter || !layoutSections.value.length) {
    teardownAllControls()
    return
  }

  await ensureMetaLoaded()
  await nextTick()
  if (token !== renderToken) return

  teardownAllControls()
  buildWorkingDoc()

  for (const section of layoutSections.value || []) {
    for (const column of section.columns || []) {
      for (const row of column || []) {
        await makeControl(row)
      }
    }
  }

  if (props.editMode && props.hasEncounter) {
    const payload = collectPayload()
    runtimeValues.value = cloneObject(payload)
    const sig = payloadSignature(payload)
    runtimeSignature.value = sig
    savedSignature.value = sig
    isDirty.value = false
  }
}
</script>

<style scoped>
.assessment-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
  margin-bottom: 12px;
}

.assessment-header {
  display: flex;
  justify-content: end;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.assessment-header h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.assessment-header .meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
  color: #ffffff;
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

.status-note {
  color: #92400e;
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

.empty-state .hint {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
}

.assessment-sections {
  display: grid;
  gap: 16px;
}

.assessment-section {
  display: grid;
  gap: 10px;
}

.assessment-section.has-separator {
  border-top: 1px solid #e2e8f0;
  padding-top: 14px;
}

.assessment-section-title {
  margin: 0;
  font-size: 14px;
  line-height: 1.35;
  font-weight: 700;
  color: #0f172a;
}

.assessment-columns {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(var(--assessment-columns, 1), minmax(0, 1fr));
}

.assessment-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.assessment-field {
  min-width: 0;
}

.field-control-host:deep(.frappe-control) {
  margin-bottom: 0;
}

.field-control-host:deep(.frappe-control .form-group) {
  margin-bottom: 0;
}

.field-control-host:deep(.control-label) {
  color: #1e293b;
  font-size: 14px;
  line-height: 1.3;
  font-weight: 600;
  letter-spacing: 0;
  margin-bottom: 6px;
  text-transform: none;
}

.field-control-host:deep(textarea.form-control),
.field-control-host:deep(input.form-control),
.field-control-host:deep(.control-input .form-control),
.field-control-host:deep(.table-multiselect.form-control) {
  background: var(--control-bg, #edeef0);
  border-color: #e5e7eb;
  border-radius: 12px;
}

.field-control-host:deep(.table-multiselect.form-control .tb-selected-value) {
  margin-bottom: 6px;
}
</style>

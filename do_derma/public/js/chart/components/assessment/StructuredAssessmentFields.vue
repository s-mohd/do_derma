<template>
  <div class="structured-fields" data-test="structured-assessment-fields">
    <p v-if="!layout.length" class="fields-empty">
      {{ __("No structured assessment fields are configured. Set them in Derma Settings.") }}
    </p>

    <p v-else-if="!editMode && !layoutSections.length" class="fields-empty">
      {{ __("Nothing documented in this format.") }}
    </p>

    <section
      v-for="(section, sectionIndex) in layoutSections"
      :key="section.key"
      class="fields-section"
      :class="{ 'has-separator': sectionIndex > 0 }"
    >
      <h4 v-if="section.label" class="fields-section-title">{{ section.label }}</h4>

      <div class="fields-columns" :style="{ '--fields-columns': String(section.columns.length || 1) }">
        <section
          v-for="(column, colIdx) in section.columns"
          :key="`${section.key}-column-${colIdx}`"
          class="fields-column"
        >
          <div v-for="field in column" :key="field.layout_key || field.fieldname" class="fields-field">
            <div class="field-control-host" :ref="(el) => bindFieldHost(field.fieldname, el)"></div>
          </div>
        </section>
      </div>
    </section>
  </div>
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
const DIRTY_SYNC_DELAY_MS = 180

const props = defineProps({
  layout: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  contextValues: { type: Object, default: () => ({}) },
  editMode: { type: Boolean, default: false },
  docstatus: { type: [Number, null], default: null },
  allowOnSubmitFields: { type: Array, default: () => [] },
})

const emit = defineEmits(["dirty"])

const fieldHosts = new Map()
const controls = new Map()
let workingDoc = {}
let renderToken = 0
let refreshQueued = false
let dirtySyncTimer = null
const savedSignature = ref("")
const runtimeValues = ref({})

const allowOnSubmitSet = computed(() => new Set((props.allowOnSubmitFields || []).filter(Boolean)))
const isSubmittedEncounter = computed(() => Number(props.docstatus ?? 0) === 1)
const evaluationDoc = computed(() => {
  const values = props.editMode ? runtimeValues.value || {} : props.values || {}
  return { ...(props.contextValues || {}), ...(values || {}) }
})

const visibleLayout = computed(() => {
  const values = props.editMode ? runtimeValues.value || {} : props.values || {}
  const contextDoc = evaluationDoc.value || {}
  let currentSectionVisible = true
  let currentSectionReadOnly = false
  const filtered = []

  for (const field of props.layout || []) {
    if (!field) continue

    const dependsVisible = field.depends_on ? evaluateDependsOn(field.depends_on, contextDoc) : true
    const rowVisible = Number(field.hidden || 0) !== 1 && dependsVisible
    const fieldtype = field.fieldtype || ""

    if (fieldtype === "Section Break") {
      currentSectionVisible = rowVisible
      currentSectionReadOnly = rowVisible ? isRowReadOnly(field, contextDoc) : false
      if (rowVisible) filtered.push({ ...field, _inherited_read_only: currentSectionReadOnly ? 1 : 0 })
      continue
    }

    if (!currentSectionVisible || !rowVisible) continue

    // Read mode shows only what was documented, so an empty field never
    // occupies space in a note someone is reviewing.
    if (!props.editMode && field?.is_value_field) {
      if (!field?.fieldname) continue
      if (!field.show_if_empty && !hasContent(values[field.fieldname])) continue
    }

    filtered.push(currentSectionReadOnly && field?.is_value_field ? { ...field, _inherited_read_only: 1 } : field)
  }

  return filtered
})

const layoutSections = computed(() => {
  const sections = []
  let sectionIndex = 0
  let current = { key: "section-0", label: "", columns: [[]] }

  const pushSection = () => {
    if (!(current.columns || []).some((col) => col.length) && !current.label) return
    current.columns = (current.columns || []).filter((col) => col.length)
    if (!current.columns.length) current.columns = [[]]
    sections.push(current)
  }

  for (const row of visibleLayout.value || []) {
    const fieldtype = row?.fieldtype || ""

    if (fieldtype === "Section Break") {
      pushSection()
      sectionIndex += 1
      current = { key: row.layout_key || `section-${sectionIndex}`, label: row.label || "", columns: [[]] }
      continue
    }

    if (fieldtype === "Column Break") {
      current.columns.push([])
      continue
    }

    if (!row?.is_value_field || !row?.fieldname || LAYOUT_BREAK_FIELD_TYPES.has(fieldtype)) continue

    if (!current.columns.length) current.columns = [[]]
    current.columns[current.columns.length - 1].push(row)
  }

  pushSection()
  // Drop a trailing section that only carried a label.
  return sections.filter((section) => (section.columns || []).some((col) => col.length))
})

const layoutRenderSignature = computed(() =>
  JSON.stringify(
    (layoutSections.value || []).map((section) => ({
      key: section.key,
      label: section.label,
      columns: (section.columns || []).map((col) => col.map((row) => row.layout_key || row.fieldname)),
    }))
  )
)

watch(
  () => [props.layout, props.editMode, props.docstatus, props.allowOnSubmitFields],
  () => scheduleRefreshControls(),
  { deep: true, immediate: true }
)

watch(
  () => props.values,
  (values) => {
    runtimeValues.value = cloneObject(values || {})
  },
  { deep: true, immediate: true }
)

watch(() => layoutRenderSignature.value, () => scheduleRefreshControls())

onBeforeUnmount(() => {
  stopDirtySync()
  teardownAllControls()
})

defineExpose({ collectPayload, markSaved })

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
  return Array.isArray(rows) ? rows.map((row) => ({ ...(row || {}) })) : []
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
  const conditional = row?.read_only_depends_on ? evaluateDependsOn(row.read_only_depends_on, doc) : false
  return Number(row?.read_only || 0) === 1 || conditional
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
  if (!dirtySyncTimer) return
  clearTimeout(dirtySyncTimer)
  dirtySyncTimer = null
}

function scheduleDirtySync() {
  stopDirtySync()
  dirtySyncTimer = setTimeout(() => {
    dirtySyncTimer = null
    emitDirty()
  }, DIRTY_SYNC_DELAY_MS)
}

function emitDirty() {
  if (!props.editMode) {
    emit("dirty", false)
    return
  }
  const current = payloadSignature(collectPayload())
  emit("dirty", Boolean(current && current !== savedSignature.value))
}

function markSaved() {
  savedSignature.value = payloadSignature(collectPayload())
  emit("dirty", false)
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
  for (const fieldname of controls.keys()) teardownControl(fieldname)
}

function withDoctype(doctype) {
  if (!doctype || !frappe?.model?.with_doctype) return Promise.resolve()
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
    if (row?.is_value_field && TABLE_FIELD_TYPES.has(row?.fieldtype) && row?.options) {
      tableOptions.add(row.options)
    }
  }
  for (const childDoctype of tableOptions) await withDoctype(childDoctype)
}

function buildWorkingDoc() {
  const doc = { doctype: "Patient Encounter" }
  const sourceValues = props.editMode ? runtimeValues.value || {} : props.values || {}
  for (const row of props.layout || []) {
    if (!row?.is_value_field || !row?.fieldname) continue
    const sourceValue = sourceValues?.[row.fieldname]
    doc[row.fieldname] = TABLE_FIELD_TYPES.has(row?.fieldtype)
      ? cloneRows(sourceValue)
      : sourceValue === null || sourceValue === undefined
        ? ""
        : sourceValue
  }
  workingDoc = doc
}

function buildControlDf(row) {
  if (!row?.is_value_field || !row?.fieldname) return null
  const fieldname = row.fieldname

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

  const source = {
    ...(props.contextValues || {}),
    ...(Object.keys(workingDoc || {}).length ? workingDoc : runtimeValues.value || props.values || {}),
  }

  if (props.editMode) {
    const submittedNotAllowed = isSubmittedEncounter.value && !allowOnSubmitSet.value.has(fieldname)
    df.read_only =
      isRowReadOnly(row, source) ||
      Number(row?._inherited_read_only || 0) === 1 ||
      Number(metaDf.read_only || 0) === 1 ||
      isPastVisitField(fieldname) ||
      submittedNotAllowed
        ? 1
        : 0
    if (row.mandatory_depends_on) {
      df.reqd = evaluateDependsOn(row.mandatory_depends_on, source) ? 1 : 0
    }
  }

  if (fieldtype === "Table") {
    const childMeta = df.options ? frappe.get_meta(df.options) : null
    df.fields = (childMeta?.fields || []).filter((childDf) => !NO_VALUE_FIELD_TYPES.has(childDf.fieldtype))
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
  const control = frappe?.ui?.form?.make_control?.({ parent: host, df, doc: workingDoc, render_input: true })
  if (!control) return

  const updateRuntimeValue = () => {
    if (!props.editMode || !row?.fieldname) return
    if (!runtimeValues.value || typeof runtimeValues.value !== "object") runtimeValues.value = {}
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
    if (!props.editMode) return
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
      if (this.doc) this.doc[this.df.fieldname] = cloneRows(nextRows)
      markDirty()
      return nextRows
    }
    control._update_rows(initialRows)
    if (control.doc) control.doc[df.fieldname] = cloneRows(initialRows)
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
    if (!row?.is_value_field || !row?.fieldname) continue
    const fieldname = row.fieldname
    if (onlyAllowOnSubmitFields && !allowOnSubmitSet.value.has(fieldname)) continue

    const control = controls.get(fieldname)
    let value

    if (row?.fieldtype === "Table MultiSelect") {
      value = Array.isArray(control?.rows) ? cloneRows(control.rows) : cloneRows(control?.get_model_value?.() || [])
    } else if (control?.get_value) {
      value = control.get_value()
    } else {
      value = workingDoc[fieldname]
    }

    payload[fieldname] = TABLE_FIELD_TYPES.has(row?.fieldtype) ? cloneRows(value) : (value ?? defaultValue(row))
  }

  return payload
}

async function refreshControls() {
  const token = ++renderToken

  if (!layoutSections.value.length) {
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
      for (const row of column || []) await makeControl(row)
    }
  }

  if (props.editMode) markSaved()
}
</script>

<style scoped>
.structured-fields {
  display: grid;
  gap: 16px;
}

.fields-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 14px;
  margin: 0;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
}

.fields-section {
  display: grid;
  gap: 10px;
}

.fields-section.has-separator {
  border-top: 1px solid #e2e8f0;
  padding-top: 14px;
}

.fields-section-title {
  margin: 0;
  font-size: 14px;
  line-height: 1.35;
  font-weight: 700;
  color: #0f172a;
}

.fields-columns {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(var(--fields-columns, 1), minmax(0, 1fr));
}

.fields-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.fields-field {
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

<template>
  <section class="workspace-panel prescription-panel" data-test="prescription-panel">
    <Teleport defer to="#chart-section-actions">
      <span v-if="hasEncounter && !loading" class="chart-pill" data-tone="neutral" data-test="prescription-count">
        {{ rowCount }}
      </span>
      <span v-if="statusPill" class="chart-pill" :data-tone="statusPill.tone" data-test="prescription-status">
        {{ statusPill.label }}
      </span>
      <template v-if="canEdit">
        <button
          type="button"
          class="primary small"
          data-test="prescription-save"
          :disabled="loading || saving || (!isDirty && !openPicker)"
          @mousedown.prevent
          @click="save"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </template>
    </Teleport>

    <p v-if="errorText" class="error-text" role="alert" data-test="prescription-error">{{ errorText }}</p>

    <div v-if="loading" class="empty-state">{{ __("Loading prescriptions...") }}</div>
    <div v-else-if="!hasSessionContext" class="empty-state">
      {{ __("Prescriptions are visit-scoped. Select or start an appointment session first.") }}
    </div>
    <div v-else-if="!hasEncounter" class="empty-state">{{ __("No encounter found for this session.") }}</div>
    <p v-else-if="!orderedRows.length && !drafts.length" class="empty-line">
      {{ __("No medications prescribed for this visit.") }}
    </p>
    <table v-else class="prescription-table">
      <colgroup>
        <col class="col-medication" />
        <col class="col-dosage" />
        <col class="col-duration" />
        <col class="col-form" />
        <col class="col-repeats" />
        <col class="col-actions" />
      </colgroup>
      <thead>
        <tr>
          <th class="chart-label">{{ __("Medication") }}</th>
          <th class="chart-label">{{ __("Dosage") }}</th>
          <th class="chart-label">{{ __("Duration") }} <span class="required-mark">*</span></th>
          <th class="chart-label">{{ __("Form") }}</th>
          <th class="chart-label">{{ __("Repeats") }}</th>
          <th class="chart-label"><span class="sr-only">{{ __("Actions") }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in orderedRows" :key="row.medication_request" class="ordered-row" data-test="prescription-ordered-row">
          <td>
            <span class="medication-name">{{ row.medication || row.drug_name || row.drug_code }}</span>
            <small v-if="row.drug_code" class="drug-code">{{ row.drug_code }}</small>
          </td>
          <td>{{ row.dosage || "—" }}</td>
          <td>{{ row.period || "—" }}</td>
          <td>{{ row.dosage_form || "—" }}</td>
          <td>{{ row.number_of_repeats_allowed || "—" }}</td>
          <td class="ordered-cell">
            <span class="chart-pill" data-tone="ok" :title="row.medication_request">{{ __("Ordered") }}</span>
          </td>
        </tr>
        <PrescriptionRow
          v-for="(draft, index) in drafts"
          :key="draft.key"
          :ref="(component) => (rowComponents[draft.key] = component)"
          :row="draft"
          :read-only="!canEdit"
          :is-next="isTrailing(draft)"
          :duplicate-of="duplicateOf[orderedRows.length + index]"
          :open-field="openPicker?.key === draft.key ? openPicker.field : ''"
          :comment-open="openComment === draft.key"
          :missing="showMissing ? getRequiredGaps(draft) : []"
          @update="(field, value) => updateField(draft, field, value)"
          @open-picker="(field) => (openPicker = { key: draft.key, field })"
          @close-picker="openPicker = null"
          @toggle-comment="openComment = openComment === draft.key ? null : draft.key"
          @remove="removeRow(draft)"
        />
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import PrescriptionRow from "./PrescriptionRow.vue"

const __ = window.__ || ((text) => text)

const VALUE_FIELDS = [
  "medication",
  "drug_code",
  "dosage",
  "period",
  "dosage_form",
  "number_of_repeats_allowed",
  "comment",
]
const REQUIRED_FIELDS = { medication: __("Medication"), period: __("Duration") }

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

const emit = defineEmits(["save"])

let nextKey = 0
const rowComponents = {}
const drafts = ref([])
const snapshot = ref("")
const openPicker = ref(null)
const openComment = ref(null)
const showMissing = ref(false)

const canEdit = computed(() => props.hasSessionContext && props.hasEncounter && !props.readOnly)
const orderedRows = computed(() => (props.rows || []).filter((row) => row.medication_request))
const rowCount = computed(() => orderedRows.value.length + getPayload().length)
const isDirty = computed(() => JSON.stringify(getPayload()) !== snapshot.value)

const statusPill = computed(() => {
  if (!props.hasEncounter) return null
  if (props.readOnly) return { label: __("Finalized"), tone: "neutral" }
  if (props.saving) return { label: __("Saving..."), tone: "neutral" }
  if (isDirty.value) return { label: __("Unsaved changes"), tone: "caution" }
  return null
})

const validationError = computed(() => {
  if (!showMissing.value) return ""
  const index = drafts.value.findIndex((draft) => getRequiredGaps(draft).length)
  if (index < 0) return ""
  const field = getRequiredGaps(drafts.value[index])[0]
  return __("Row {0}: {1} is required.")
    .replace("{0}", orderedRows.value.length + index + 1)
    .replace("{1}", REQUIRED_FIELDS[field])
})

// For each line, the row number of an earlier line with the same medication, or 0.
const duplicateOf = computed(() => {
  const firstRows = new Map()
  const medications = [
    ...orderedRows.value.map((row) => row.medication),
    ...drafts.value.map((draft) => draft.values.medication),
  ]
  return medications.map((medication, index) => {
    if (!medication) return 0
    if (!firstRows.has(medication)) firstRows.set(medication, index + 1)
    const firstRow = firstRows.get(medication)
    return firstRow === index + 1 ? 0 : firstRow
  })
})

// A server error describes the rows that were sent; it goes once they change.
const errorPayload = ref("")
const serverError = computed(() =>
  props.error && JSON.stringify(getPayload()) === errorPayload.value ? props.error : ""
)
const errorText = computed(() => validationError.value || serverError.value)

watch([() => props.rows, canEdit], resetDrafts, { immediate: true })
watch(() => props.error, () => (errorPayload.value = JSON.stringify(getPayload())), { immediate: true })

function makeDraft(original = {}) {
  const values = Object.fromEntries(VALUE_FIELDS.map((field) => [field, original[field] ?? ""]))
  return { key: ++nextKey, original, values, linkedItems: [], lookup: 0, filling: false }
}

function resetDrafts() {
  drafts.value = (props.rows || []).filter((row) => !row.medication_request).map((row) => makeDraft(row))
  snapshot.value = JSON.stringify(getPayload())
  ensureTrailingDraft()
  openPicker.value = null
  openComment.value = null
  showMissing.value = false
}

function isBlank(draft) {
  return VALUE_FIELDS.every(
    (field) => !draft.values[field] || (field === "number_of_repeats_allowed" && !Number(draft.values[field]))
  )
}

function getRequiredGaps(draft) {
  if (isBlank(draft)) return []
  return Object.keys(REQUIRED_FIELDS).filter((field) => !draft.values[field])
}

function getPayload() {
  return drafts.value.filter((draft) => !isBlank(draft)).map((draft) => ({ ...draft.original, ...draft.values }))
}

// An editable visit always ends with one blank line ready for the next medication.
function ensureTrailingDraft() {
  const last = drafts.value.at(-1)
  if (canEdit.value && (!last || !isBlank(last))) drafts.value.push(makeDraft())
}

function isTrailing(draft) {
  return canEdit.value && draft.key === drafts.value.at(-1)?.key && isBlank(draft)
}

function removeRow(draft) {
  drafts.value = drafts.value.filter((entry) => entry.key !== draft.key)
  if (openPicker.value?.key === draft.key) openPicker.value = null
  if (openComment.value === draft.key) openComment.value = null
}

function updateField(draft, field, value) {
  if (field === "medication") return applyMedication(draft, value)
  draft.values[field] = value
}

async function applyMedication(draft, medication) {
  if (medication === draft.values.medication) return
  const token = ++draft.lookup
  draft.values = { ...draft.values, medication, drug_code: "", dosage: "", period: "", dosage_form: "" }
  draft.original = { ...draft.original, drug_name: "" }
  draft.linkedItems = []
  if (!medication) return
  ensureTrailingDraft()
  draft.filling = true
  try {
    const [itemsResponse, defaultsResponse] = await Promise.all([
      frappe.call("healthcare.healthcare.doctype.patient_encounter.patient_encounter.get_medications", {
        medication,
      }),
      frappe.db.get_value("Medication", medication, [
        "default_prescription_dosage",
        "default_prescription_duration",
        "dosage_form",
      ]),
    ])
    if (token !== draft.lookup) return
    draft.linkedItems = (itemsResponse?.message || []).map((entry) => entry?.item).filter(Boolean)
    const defaults = defaultsResponse?.message || {}
    draft.values = {
      ...draft.values,
      drug_code: draft.linkedItems.length === 1 ? draft.linkedItems[0] : "",
      dosage: defaults.default_prescription_dosage || "",
      period: defaults.default_prescription_duration || "",
      dosage_form: defaults.dosage_form || "",
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn("Failed to apply medication defaults", error)
    if (token === draft.lookup) {
      frappe.show_alert({ message: __("Could not fill in this medication's defaults."), indicator: "red" })
    }
  } finally {
    if (token === draft.lookup) draft.filling = false
  }
}

async function save() {
  if (!canEdit.value || props.saving || props.loading) return
  await rowComponents[openPicker.value?.key]?.commitPicker()
  showMissing.value = true
  if (validationError.value) return
  showMissing.value = false
  emit("save", getPayload())
}
</script>

<style scoped>
.error-text {
  margin: 0 0 8px;
  color: var(--chart-danger-text);
  font-size: 12px;
}

.empty-state {
  padding: 14px;
  border: 1px dashed var(--chart-border-strong);
  border-radius: 10px;
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 13px;
}

.empty-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: var(--chart-muted);
  font-size: 13px;
}

.prescription-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.col-medication {
  width: 32%;
}

.col-dosage {
  width: 17%;
}

.col-duration,
.col-form {
  width: 15%;
}

.col-repeats {
  width: 10%;
}

.col-actions {
  width: 11%;
}

.prescription-table th {
  padding: 8px 10px;
  border-bottom: 1px solid var(--chart-border);
  text-align: left;
}

.required-mark {
  color: var(--chart-danger-text);
}

.prescription-table :deep(td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--chart-surface-muted);
  color: var(--chart-text);
  font-size: 13px;
  vertical-align: top;
}

.prescription-table :deep(.medication-name) {
  font-weight: 600;
}

.prescription-table :deep(.drug-code) {
  display: block;
  margin-top: 3px;
  color: var(--chart-muted);
  font-size: 12px;
}

.ordered-cell {
  text-align: right;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>

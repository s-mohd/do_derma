<template>
  <section class="assessment-panel" data-test="assessment-panel">
    <p v-if="error" class="error-text" data-test="assessment-error">{{ error }}</p>
    <p v-if="submittedNote" class="status-note">{{ submittedNote }}</p>

    <div v-if="loading" class="empty-state">{{ __("Loading assessment...") }}</div>

    <div v-else-if="!hasEncounter" class="empty-state">
      <p>{{ __("No encounter yet for this appointment.") }}</p>
      <button
        type="button"
        class="primary"
        data-test="assessment-start"
        :disabled="saving"
        @click="$emit('request-edit')"
      >
        {{ __("Start Assessment") }}
      </button>
    </div>

    <template v-else>
      <SoapNoteFields
        v-if="mode === SOAP || mode === HP"
        ref="fieldsRef"
        :layout="mode === SOAP ? soapLayout : hpLayout"
        :values="mode === SOAP ? soapValues : hpValues"
        :edit-mode="editMode"
        :docstatus="docstatus"
        :allow-on-submit-fields="allowOnSubmitFields"
        @dirty="(value) => (isDirty = value)"
      />
      <StructuredAssessmentFields
        v-else
        ref="fieldsRef"
        :layout="layout"
        :values="values"
        :context-values="contextValues"
        :edit-mode="editMode"
        :docstatus="docstatus"
        :allow-on-submit-fields="allowOnSubmitFields"
        @dirty="(value) => (isDirty = value)"
      />

      <p v-if="!editMode && inactiveModeHasContent" class="status-note" data-test="assessment-other-format">
        {{ otherFormatNote }}
      </p>

      <footer class="assessment-footer">
        <span class="footer-status">{{ footerStatus }}</span>
        <button
          v-if="canPrint"
          type="button"
          class="ghost"
          data-test="assessment-print"
          :title="__('Print this note on the clinic letterhead')"
          @click="printNote"
        >
          {{ __("Print") }}
        </button>
        <button
          v-if="!editMode && canEdit"
          type="button"
          class="primary"
          data-test="assessment-edit"
          @click="$emit('request-edit')"
        >
          {{ __("Edit") }}
        </button>
        <button
          v-else-if="editMode"
          type="button"
          class="primary"
          data-test="assessment-save"
          :disabled="saving || !isDirty"
          @click="submitDraft"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </footer>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue"

import SoapNoteFields from "./SoapNoteFields.vue"
import StructuredAssessmentFields from "./StructuredAssessmentFields.vue"

const __ = window.__ || ((txt) => txt)

const SOAP = "SOAP"
const HP = "HP"
const STRUCTURED = "Structured"
const MODE_LABELS = { SOAP: "SOAP Note", HP: "History & Physical", Structured: "Structured Assessment" }
// One print format per report type, seeded by do_derma.printing.note - never mixed.
const PRINT_FORMATS = { SOAP: "Derma Assessment Note (SOAP)", HP: "Derma Assessment Note (H&P)", Structured: "Derma Assessment Note (Structured)" }

const props = defineProps({
  mode: { type: String, default: STRUCTURED },
  availableModes: { type: Array, default: () => [STRUCTURED] },
  layout: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  soapLayout: { type: Array, default: () => [] },
  soapValues: { type: Object, default: () => ({}) },
  hpLayout: { type: Array, default: () => [] },
  hpValues: { type: Object, default: () => ({}) },
  contextValues: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasEncounter: { type: Boolean, default: false },
  docstatus: { type: [Number, null], default: null },
  editMode: { type: Boolean, default: false },
  allowOnSubmitFields: { type: Array, default: () => [] },
  encounter: { type: String, default: "" },
  isFilled: { type: Boolean, default: false },
})

const emit = defineEmits(["request-edit", "save"])

const fieldsRef = ref(null)
const isDirty = ref(false)

// Printing goes through the seeded "Derma Assessment Note" print format, which
// renders whichever format the encounter is stamped with - what you see is what prints.
const canPrint = computed(() => Boolean(props.encounter) && props.isFilled)

function printNote() {
  const url = `/printview?doctype=Patient%20Encounter&name=${encodeURIComponent(props.encounter)}&format=${encodeURIComponent(PRINT_FORMATS[props.mode] || "Derma Assessment Note")}&no_letterhead=0&_lang=${window.frappe?.boot?.lang || "en"}`
  window.open(url, "_blank", "noopener")
}

const valuesByMode = computed(() => ({ [STRUCTURED]: props.values, [SOAP]: props.soapValues, [HP]: props.hpValues }))
const otherModesWithContent = computed(() =>
  Object.entries(valuesByMode.value)
    .filter(([mode, source]) => mode !== props.mode && Object.values(source || {}).some(hasContent))
    .map(([mode]) => mode)
)
const isSubmitted = computed(() => Number(props.docstatus ?? 0) === 1)

const canEdit = computed(() => {
  if (!props.hasEncounter) return false
  const status = Number(props.docstatus ?? 0)
  if (status === 0) return true
  if (status === 1) return (props.allowOnSubmitFields || []).length > 0
  return false
})

const inactiveModeHasContent = computed(() => otherModesWithContent.value.length > 0)

const otherFormatNote = computed(() =>
  __("This visit also has content saved as {0}.").replace(
    "{0}",
    otherModesWithContent.value.map((mode) => __(MODE_LABELS[mode])).join(", ")
  )
)

const submittedNote = computed(() => {
  if (!props.hasEncounter) return ""
  const status = Number(props.docstatus ?? 0)
  if (status === 2) return __("Encounter is cancelled. Assessment is read-only.")
  if (status !== 1) return ""
  return (props.allowOnSubmitFields || []).length
    ? __("Encounter is submitted. Only Allow on Submit fields are editable.")
    : __("Encounter is submitted. No assessment fields are marked Allow on Submit.")
})

const footerStatus = computed(() => {
  if (props.saving) return __("Saving...")
  if (props.editMode && isDirty.value) return __("Unsaved changes")
  if (props.editMode) return __("No changes")
  return isSubmitted.value ? "" : __("Read-only. Choose Edit to continue documenting.")
})

watch(
  () => props.mode,
  () => {
    isDirty.value = false
  }
)

function hasContent(value) {
  if (value === null || value === undefined) return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === "string") return Boolean(value.trim())
  return true
}

function submitDraft() {
  if (!props.editMode || props.saving) return
  const payload = fieldsRef.value?.collectPayload?.() || {}
  emit("save", { payload, mode: props.mode })
  fieldsRef.value?.markSaved?.()
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

button {
  border-radius: 8px;
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

button.primary {
  border-color: #087b75;
  background: #087b75;
  color: #ffffff;
}

button:disabled {
  opacity: 0.55;
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
  margin: 8px 0 0;
}

.empty-state {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 14px;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
  display: grid;
  gap: 10px;
  justify-items: start;
}

.empty-state p {
  margin: 0;
}

.assessment-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}

.footer-status {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: #64748b;
}
</style>

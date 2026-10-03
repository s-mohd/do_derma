<template>
  <section class="assessment-panel" data-test="assessment-panel">
    <Teleport defer to="#chart-section-actions">
      <template v-if="hasEncounter && !loading">
        <span
          v-if="headerStatus"
          class="chart-pill"
          :data-tone="saving ? null : 'caution'"
          data-test="assessment-status"
        >{{ headerStatus }}</span>
        <button
          v-if="canPrint"
          type="button"
          class="ghost small"
          data-test="assessment-print"
          :title="__('Print this note on the clinic letterhead')"
          @click="printNote"
        >
          {{ __("Print") }}
        </button>
        <button
          v-if="!editMode && canEdit"
          type="button"
          class="primary small"
          data-test="assessment-edit"
          @click="$emit('request-edit')"
        >
          {{ __("Edit") }}
        </button>
        <button
          v-else-if="editMode"
          type="button"
          class="primary small"
          data-test="assessment-save"
          :disabled="saving || !isDirty"
          @click="submitDraft"
        >
          {{ saving ? __("Saving...") : __("Save") }}
        </button>
      </template>
    </Teleport>
    <p v-if="error" class="error-text" data-test="assessment-error">{{ error }}</p>
    <p v-if="submittedNote" class="chart-pill status-note">{{ submittedNote }}</p>

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
      <h3 class="assessment-block-title">{{ __("Clinical note") }}</h3>
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

      <div v-if="!editMode && otherModesWithContent.length" class="other-formats" data-test="assessment-other-format">
        <template v-for="otherMode in otherModesWithContent" :key="otherMode">
          <span v-if="isModeInert(otherMode)" class="chart-pill" data-tone="caution" :data-test="`assessment-other-format-${otherMode.toLowerCase()}`">
            {{ otherFormatLabel(otherMode) }}
          </span>
          <button
            v-else
            type="button"
            class="chart-pill"
            data-tone="caution"
            :data-test="`assessment-other-format-${otherMode.toLowerCase()}`"
            :title="__('Switch this visit to {0}').replace('{0}', __(MODE_LABELS[otherMode]))"
            @click="emit('switch-mode', otherMode)"
          >
            {{ otherFormatLabel(otherMode) }}
          </button>
        </template>
      </div>

      <section v-if="hasAdvice" class="advice-block" data-test="assessment-advice">
        <header class="advice-head">
          <h3 class="assessment-block-title">{{ __("Patient advice") }}</h3>
          <label v-if="canPrint" class="advice-toggle" data-test="assessment-advice-toggle" :title="__('Optional: add the patient advice block to the printed note')">
            <input type="checkbox" :checked="includeAdvice" :disabled="togglingAdvice" @change="toggleAdvice($event.target.checked)" />
            {{ __("Include in print") }}
          </label>
          <select
            v-if="canPrint && includeAdvice"
            class="advice-language"
            data-test="assessment-advice-language"
            :value="adviceLanguage"
            :disabled="togglingAdvice"
            :title="__('Which advice prints: Auto follows the language the report is written in')"
            @change="setAdviceLanguage($event.target.value)"
          >
            <option value="Auto">{{ __("Auto (report language)") }}</option>
            <option value="English">{{ __("English") }}</option>
            <option value="Arabic">{{ __("Arabic") }}</option>
            <option value="Both">{{ __("Both") }}</option>
          </select>
        </header>
        <details>
          <summary>{{ __("Show advice") }}</summary>
          <pre v-if="patientAdvice">{{ patientAdvice }}</pre>
          <pre v-if="patientAdviceAr" dir="rtl">{{ patientAdviceAr }}</pre>
          <small>{{ __("Edit the text on the Patient Encounter form.") }}</small>
        </details>
      </section>
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
const SHORT_LABELS = { SOAP: "SOAP", HP: "H&P", Structured: "Structured" }
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
  patientAdvice: { type: String, default: "" },
  patientAdviceAr: { type: String, default: "" },
  printPatientAdvice: { type: Boolean, default: false },
  patientAdviceLanguage: { type: String, default: "Auto" },
  modeLocked: { type: Boolean, default: false },
})

const emit = defineEmits(["request-edit", "save", "advice-toggled", "advice-language", "switch-mode"])

// Patient advice prints only when the doctor opts in - the box is a field on the
// encounter (Allow on Submit), so the choice survives and shows on the form too.
const hasAdvice = computed(() => Boolean(props.patientAdvice || props.patientAdviceAr))
const includeAdvice = ref(Boolean(props.printPatientAdvice))
const togglingAdvice = ref(false)
watch(
  () => props.printPatientAdvice,
  (value) => {
    includeAdvice.value = Boolean(value)
  }
)
// Auto = the language the report is written in; English / Arabic / Both override it.
const adviceLanguage = ref(props.patientAdviceLanguage || "Auto")
watch(
  () => props.patientAdviceLanguage,
  (value) => {
    adviceLanguage.value = value || "Auto"
  }
)

async function setAdviceLanguage(value) {
  const previous = adviceLanguage.value
  adviceLanguage.value = value
  togglingAdvice.value = true
  try {
    await frappe.db.set_value("Patient Encounter", props.encounter, "custom_derma_patient_advice_language", value)
    emit("advice-language", value)
  } catch (error) {
    adviceLanguage.value = previous
    frappe.msgprint(__("Could not update the advice language."))
  } finally {
    togglingAdvice.value = false
  }
}

async function toggleAdvice(checked) {
  togglingAdvice.value = true
  try {
    await frappe.db.set_value("Patient Encounter", props.encounter, "custom_derma_print_patient_advice", checked ? 1 : 0)
    includeAdvice.value = checked
    emit("advice-toggled", checked)
  } catch (error) {
    includeAdvice.value = !checked
    frappe.msgprint(__("Could not update the print option."))
  } finally {
    togglingAdvice.value = false
  }
}

const fieldsRef = ref(null)
const isDirty = ref(false)

// Printing goes through the seeded "Derma Assessment Note" print format, which
// renders whichever format the encounter is stamped with - what you see is what prints.
const canPrint = computed(() => Boolean(props.encounter) && props.isFilled)

function printNote() {
  const url = `/printview?doctype=Patient%20Encounter&name=${encodeURIComponent(props.encounter)}&format=${encodeURIComponent(PRINT_FORMATS[props.mode] || "Derma Assessment Note")}&no_letterhead=1&_lang=${window.frappe?.boot?.lang || "en"}`
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

function isModeInert(mode) {
  return props.modeLocked || !props.availableModes.includes(mode)
}

function otherFormatLabel(mode) {
  return __("{0} has content").replace("{0}", __(SHORT_LABELS[mode] || mode))
}

const submittedNote = computed(() => {
  if (!props.hasEncounter) return ""
  const status = Number(props.docstatus ?? 0)
  if (status === 2) return __("Encounter is cancelled. Assessment is read-only.")
  if (status !== 1) return ""
  return (props.allowOnSubmitFields || []).length
    ? __("Encounter is submitted. Only Allow on Submit fields are editable.")
    : __("Encounter is submitted. No assessment fields are marked Allow on Submit.")
})

const headerStatus = computed(() => {
  if (props.saving) return __("Saving...")
  return props.editMode && isDirty.value ? __("Unsaved changes") : ""
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
  display: grid;
  gap: 14px;
}

.assessment-panel > .assessment-block-title {
  margin-bottom: -4px;
}

.error-text {
  color: var(--chart-danger-text);
  font-size: 12px;
  margin: 0 0 8px;
}

.status-note {
  justify-self: start;
  white-space: normal;
  margin: 0;
}

.empty-state {
  border: 1px dashed var(--chart-border-strong);
  border-radius: 10px;
  padding: 14px;
  color: var(--chart-text-soft);
  font-size: 13px;
  background: var(--chart-surface-muted);
  display: grid;
  gap: 10px;
  justify-items: start;
}

.empty-state p {
  margin: 0;
}

.advice-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--chart-text-soft);
  cursor: pointer;
}

.advice-language {
  border: 1px solid var(--chart-border-strong);
  border-radius: 8px;
  padding: 5px 8px;
  font-size: 12px;
  background: var(--chart-surface);
}

.other-formats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.advice-block {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
}

.advice-head .assessment-block-title {
  margin: 0;
}

.advice-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.advice-block summary {
  cursor: pointer;
  color: var(--chart-text-soft);
}

.advice-block pre {
  white-space: pre-wrap;
  font: inherit;
  margin: 8px 0 0;
}

.advice-block small {
  display: block;
  margin-top: 6px;
  color: var(--chart-muted);
}
</style>

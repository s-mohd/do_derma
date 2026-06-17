<template>
  <div class="chart-topbar">
    <div class="topbar-main">
      <section class="session-shell" :class="{ disabled: sessionControlsDisabled }">
        <header class="session-head">
          <div class="session-head-copy">
            <strong>{{ __("Session Context") }}</strong>
            <small v-if="sessionHint">{{ sessionHint }}</small>
            <div v-if="caseSummary" class="case-context-inline">
              <span class="case-chip">{{ caseSummary.case_type || __("Treatment Case") }}</span>
              <span class="case-meta">
                {{ caseSummary.name }} · {{ caseSummary.status }}
                <template v-if="caseSummary.current_session_no"> · {{ __("Session") }} #{{ caseSummary.current_session_no }}</template>
              </span>
              <span v-if="caseSummary.next_visit_date" class="case-meta">
                {{ __("Next") }}: {{ formatDate(caseSummary.next_visit_date) }}
              </span>
            </div>
          </div>
          <button
            v-if="readOnlyByContext"
            type="button"
            class="context-lock-toggle"
            :class="{ unlocked: !readOnlyContext }"
            @click="toggleReadOnlyOverride"
          >
            {{ readOnlyContext ? __("Read only") : __("Editable") }}
          </button>
        </header>

        <div class="session-grid">
          <div ref="providerRef" class="frappe-link"></div>
          <div ref="assistantRef" class="frappe-link"></div>
          <div ref="dateRef" class="frappe-control-host"></div>
          <div ref="categoryRef" class="frappe-control-host"></div>
          <div ref="pastAppointmentRef" class="frappe-link" :class="categoryControl?.get_value() === 'Follow-up' ? '' : 'hidden'"></div>
          <div ref="treatmentCaseRef" class="frappe-link"></div>
        </div>

        <!-- <div class="session-actions">
          <button
            type="button"
            class="ghost"
            :disabled="!hasPatientContext"
            @click="emit('start-treatment-case')"
          >
            {{ __("Start Treatment Case") }}
          </button>
          <div ref="labMenuRef" class="lab-dropdown">
            <button
              type="button"
              class="ghost lab-launcher"
              :class="{ attention: labNeedsAttention }"
              @click="toggleLabMenu"
            >
              <span>{{ __("Lab Desk") }}</span>
              <span class="lab-pill">{{ `${labSummary.open || 0} ${__('open')}` }}</span>
              <span v-if="candidateCount" class="lab-pill queued">{{ `${candidateCount} ${__('to create')}` }}</span>
            </button>
            <div v-if="labMenuOpen" class="lab-menu">
          <div class="lab-menu-header">
            <div>
              <strong>{{ labPanelTitle }}</strong>
              <small>{{ labMenuSubtitle }}</small>
            </div>
            <div class="lab-summary-row">
              <span v-if="labReadiness.label" class="summary-chip" :class="labReadiness.key">{{ labReadiness.label }}</span>
              <span class="summary-chip">{{ `${labSummary.open || 0} ${__('open')}` }}</span>
              <span v-if="labSummary.overdue" class="summary-chip overdue">{{ `${labSummary.overdue} ${__('overdue')}` }}</span>
              <span v-if="labSummary.ready_for_delivery" class="summary-chip ready">{{ `${labSummary.ready_for_delivery} ${__('ready')}` }}</span>
            </div>
          </div>
          <div v-if="labReadiness.note" class="lab-readiness-note">{{ labReadiness.note }}</div>

          <div class="lab-section action-section">
            <div class="section-title">{{ __("Start here") }}</div>
            <div class="lab-action-grid">
              <button
                type="button"
                class="lab-action-card primary"
                :disabled="!canCreateFromVisit"
                @click="submitCreateLabCase"
              >
                <strong>{{ __("Create from visit") }}</strong>
                <small>{{ visitActionHelp }}</small>
              </button>
              <button
                type="button"
                class="lab-action-card secondary"
                :disabled="!canCreatePlannedLabCase"
                @click="submitCreatePlannedLabCase"
              >
                <strong>{{ __("Planned draft") }}</strong>
                <small>{{ __("Use when lab work is being planned before the final procedure is entered.") }}</small>
              </button>
            </div>
          </div>

          <div v-if="labCandidates.length" class="lab-section">
            <div class="section-title">{{ __("Suggested from this visit") }}</div>
            <label v-for="row in labCandidates" :key="row.name" class="lab-candidate-row">
              <input
                type="checkbox"
                :checked="selectedLabProcedureNames.includes(row.name)"
                :disabled="readOnlyContext"
                @change="toggleLabCandidate(row.name)"
              />
              <div class="candidate-copy">
                <span class="candidate-title">{{ formatCandidateLabel(row) }}</span>
                <small>
                  {{ row.lab_case_default_case_type || __('Lab work') }}
                  <template v-if="row.lab_case_default_mode"> · {{ row.lab_case_default_mode }}</template>
                </small>
              </div>
            </label>
            <div class="lab-selection-note">{{ selectionSummary }}</div>
          </div>

          <div v-if="labCases.length" class="lab-section">
            <div class="section-title">{{ __("Existing cases") }}</div>
            <div
              v-for="row in labCases"
              :key="row.name"
              class="lab-case-row"
              role="button"
              tabindex="0"
              @click="openLabCase(row.name)"
              @keydown.enter.prevent="openLabCase(row.name)"
            >
              <div class="lab-case-copy">
                <span class="case-name">{{ row.name }}</span>
                <small>{{ formatLabCaseMeta(row) }}</small>
              </div>
              <div class="lab-case-actions">
                <button
                  v-if="row.is_planned_case && canLinkSelectedProcedures"
                  type="button"
                  class="ghost small inline-link"
                  @click.stop="linkSelectedProcedures(row.name)"
                >
                  {{ __("Link selected") }}
                </button>
                <span class="case-status" :class="labStatusClass(row)">{{ caseStatusLabel(row) }}</span>
              </div>
            </div>
          </div>

          <div v-if="!labCandidates.length && !labCases.length" class="lab-empty">
            {{ emptyStateLabel }}
          </div>
        </div>
          </div>

          <div ref="consentMenuRef" class="consent-dropdown">
            <button
              v-if="signedCount > 0"
              type="button"
              class="ghost"
              @click="toggleConsentMenu"
            >
              {{ signedCount ? `Signed consents (${signedCount})` : `Signed consents (0)` }}
            </button>
            <div v-if="consentMenuOpen" class="consent-menu">
              <button
                v-for="row in signedConsents"
                :key="row.name"
                type="button"
                @click="selectConsent(row)"
              >
                <span class="label">{{ row.consent_form_template || row.name }}</span>
                <small v-if="row.signed_on">{{ formatSignedOn(row.signed_on) }}</small>
              </button>
            </div>
          </div>
        </div> -->
      </section>
      <section class="mode-rail">
        <span class="mode-label">{{ __("Derma View") }}</span>
        <div class="primary-toggle">
          <button
            :class="{ active: mode === 'procedures' }"
            :disabled="isModeDisabled('procedures')"
            :title="modeHint('procedures')"
            @click="emitMode('procedures')"
          >
            Procedures
          </button>
          <button
            :class="{ active: mode === 'conditions' }"
            :disabled="isModeDisabled('conditions')"
            :title="modeHint('conditions')"
            @click="emitMode('conditions')"
          >
            Findings
          </button>
          <button
            :class="{ active: mode === 'perio' }"
            :disabled="isModeDisabled('perio')"
            :title="modeHint('perio')"
            @click="emitMode('perio')"
          >
            Annotate
          </button>
          <button
            :class="{ active: mode === 'overview' }"
            :disabled="isModeDisabled('overview')"
            :title="modeHint('overview')"
            @click="emitMode('overview')"
          >
            Overview
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  mode: { type: String, default: "procedures" },
  statusPills: { type: Array, default: () => [] },
  practitioners: { type: Array, default: () => [] },
  priceLists: { type: Array, default: () => [] },
  priceList: { type: String, default: "" },
  provider: { type: String, default: "" },
  assistantEmployee: { type: String, default: "" },
  sessionDate: { type: String, default: "" },
  appointmentCategory: { type: String, default: "" },
  pastAppointment: { type: String, default: "" },
  treatmentCase: { type: String, default: "" },
  patientId: { type: String, default: "" },
  appointmentId: { type: String, default: "" },
  treatmentCaseSummary: { type: Object, default: () => ({ case: null }) },
  activeTreatmentCases: { type: Array, default: () => [] },
  signedConsents: { type: Array, default: () => [] },
  modeDisabled: { type: Object, default: () => ({}) },
  readOnlyContext: { type: Boolean, default: false },
  readOnlyByContext: { type: Boolean, default: false },
  readOnlyOverride: { type: Boolean, default: false },
  labCases: { type: Array, default: () => [] },
  labCaseSummary: { type: Object, default: () => ({}) },
  labCaseReadiness: { type: Object, default: () => ({}) },
  labCandidates: { type: Array, default: () => [] },
  hasPatientContext: { type: Boolean, default: false },
  hasSessionContext: { type: Boolean, default: false },
  canCreateSessionLabCase: { type: Boolean, default: false },
  canCreatePlannedLabCase: { type: Boolean, default: false },
})

const emit = defineEmits([
  "update:mode",
  "update:provider",
  "update:assistant-employee",
  "update:session-date",
  "update:appointment-category",
  "update:past-appointment",
  "update:treatment-case",
  "update:priceList",
  "reset",
  "end-session",
  "view-consent",
  "create-session-lab-case",
  "create-planned-lab-case",
  "attach-procedures-to-lab-case",
  "open-lab-case",
  "toggle-read-only-override",
  "start-treatment-case",
])

const categoryOptions = Object.freeze(["First Time", "Follow-up"])
const localProvider = ref(props.provider || "")
const localAssistantEmployee = ref(props.assistantEmployee || "")
const localSessionDate = ref(props.sessionDate || "")
function normalizeCategoryValue(value) {
  const raw = (value || "").toString().trim()
  if (!raw) return ""
  if (raw === "Procedure" || raw === "Session") return "Follow-up"
  if (raw === "Case Start") return "First Time"
  return categoryOptions.includes(raw) ? raw : ""
}

const localAppointmentCategory = ref(normalizeCategoryValue(props.appointmentCategory))
const localPastAppointment = ref(props.pastAppointment || "")
const localTreatmentCase = ref(props.treatmentCase || "")
const localPriceList = ref(props.priceList || "")
const dateRef = ref(null)
const categoryRef = ref(null)
const providerRef = ref(null)
const assistantRef = ref(null)
const pastAppointmentRef = ref(null)
const treatmentCaseRef = ref(null)
const consentMenuRef = ref(null)
const consentMenuOpen = ref(false)
const labMenuRef = ref(null)
const labMenuOpen = ref(false)
const selectedLabProcedureNames = ref([])
let dateControl = null
let categoryControl = null
let providerControl = null
let assistantControl = null
let pastAppointmentControl = null
let treatmentCaseControl = null

const signedCount = computed(() => props.signedConsents.length)
const candidateCount = computed(() => props.labCandidates.length)
const labSummary = computed(() => props.labCaseSummary || {})
const labReadiness = computed(() => props.labCaseReadiness || {})
const labNeedsAttention = computed(() => Boolean((labSummary.value?.overdue || 0) > 0 || candidateCount.value > 0))
const selectedLabProcedureCount = computed(() => selectedLabProcedureNames.value.length)
const canCreateFromVisit = computed(() => props.canCreateSessionLabCase && selectedLabProcedureCount.value > 0)
const canLinkSelectedProcedures = computed(() => props.canCreateSessionLabCase && selectedLabProcedureCount.value > 0)
const labPanelTitle = computed(() => (props.hasSessionContext ? __("Current session lab work") : __("Patient lab work")))
const labMenuSubtitle = computed(() => {
  if (props.hasSessionContext && candidateCount.value) {
    return __(`${candidateCount.value} procedure(s) from this visit can be sent to the lab.`)
  }
  if ((props.labCases || []).length) {
    return props.hasSessionContext
      ? __(`${props.labCases.length} active lab case(s) are linked to this session.`)
      : __(`${props.labCases.length} active lab case(s) exist for this patient.`)
  }
  return props.hasSessionContext
    ? __("Nothing is queued for this session yet.")
    : __("No active lab work is recorded for this patient.")
})
const createButtonLabel = computed(() => {
  const count = selectedLabProcedureNames.value.length
  return count > 1 ? __(`Create one case for ${count} procedures`) : __("Create lab case")
})
const visitActionHelp = computed(() => {
  if (!props.hasSessionContext) return __("Open a visit or appointment to create from procedures.")
  if (!candidateCount.value) return __("No lab-recommended procedures are waiting in this visit.")
  return createButtonLabel.value
})
const selectionSummary = computed(() => {
  if (!candidateCount.value) return ""
  if (!selectedLabProcedureCount.value) return __("Select at least one procedure to create or link.")
  return __(`${selectedLabProcedureCount.value} procedure(s) selected.`)
})
const emptyStateLabel = computed(() =>
  props.hasSessionContext
    ? __("No lab work is linked to this session yet.")
    : __("No active lab work is linked to this patient yet.")
)
const caseSummary = computed(() => props.treatmentCaseSummary?.case || null)
const showPastAppointmentControl = computed(() => localAppointmentCategory.value === "Follow-up")
const sessionControlsDisabled = computed(() => !props.hasSessionContext)
const sessionHint = computed(() =>
  props.hasSessionContext
    ? ""
    : __("Open an active visit to unlock editing.")
)

function isModeDisabled(modeKey) {
  return Boolean(props.modeDisabled?.[modeKey])
}

function modeHint(modeKey) {
  return props.modeDisabled?.[modeKey] || ""
}

function emitMode(modeKey) {
  if (isModeDisabled(modeKey)) return
  emit("update:mode", modeKey)
}

function toggleReadOnlyOverride() {
  if (!props.readOnlyByContext) return
  emit("toggle-read-only-override", !props.readOnlyOverride)
}

function resetLabSelections() {
  selectedLabProcedureNames.value = (props.labCandidates || []).map((row) => row.name).filter(Boolean)
}

watch(
  () => props.provider,
  (next) => {
    localProvider.value = next || ""
    syncProviderControl()
  }
)
watch(
  () => props.assistantEmployee,
  (next) => {
    localAssistantEmployee.value = next || ""
    syncAssistantControl()
  }
)
watch(
  () => props.sessionDate,
  (next) => {
    localSessionDate.value = next || ""
    syncDateControl()
  }
)
watch(
  () => props.appointmentCategory,
  (next) => {
    localAppointmentCategory.value = normalizeCategoryValue(next)
    syncCategoryControl()
  }
)
watch(
  () => props.pastAppointment,
  (next) => {
    localPastAppointment.value = next || ""
    syncPastAppointmentControl()
  }
)
watch(
  () => props.treatmentCase,
  (next) => {
    localTreatmentCase.value = next || ""
    syncTreatmentCaseControl()
  }
)
watch(
  () => props.priceList,
  (next) => {
    localPriceList.value = next || ""
  }
)
watch(
  () => props.labCandidates,
  () => {
    if (!labMenuOpen.value) resetLabSelections()
  },
  { deep: true, immediate: true }
)
watch(
  () => showPastAppointmentControl.value,
  async () => {
    await nextTick()
    syncPastAppointmentControl()
  }
)
watch(
  () => sessionControlsDisabled.value,
  () => {
    syncDateControl()
    syncCategoryControl()
    syncProviderControl()
    syncAssistantControl()
    syncTreatmentCaseControl()
    syncPastAppointmentControl()
  }
)

function syncDateControl() {
  if (dateControl?.get_value && dateControl?.set_value) {
    const current = dateControl.get_value()
    if (current !== (localSessionDate.value || "")) {
      dateControl.set_value(localSessionDate.value || "")
    }
  }
  dateControl?.$input?.prop("disabled", Boolean(sessionControlsDisabled.value))
}

function syncCategoryControl() {
  if (categoryControl?.get_value && categoryControl?.set_value) {
    const current = categoryControl.get_value()
    if (current !== (localAppointmentCategory.value || "")) {
      categoryControl.set_value(localAppointmentCategory.value || "")
    }
  }
  categoryControl?.$input?.prop("disabled", Boolean(sessionControlsDisabled.value))
}

function syncProviderControl() {
  if (providerControl?.get_value && providerControl?.set_value) {
    const current = providerControl.get_value()
    if (current !== (localProvider.value || "")) {
      providerControl.set_value(localProvider.value || "")
    }
  }
  providerControl?.$input?.prop("disabled", Boolean(sessionControlsDisabled.value))
}

function syncAssistantControl() {
  if (assistantControl?.get_value && assistantControl?.set_value) {
    const current = assistantControl.get_value()
    if (current !== (localAssistantEmployee.value || "")) {
      assistantControl.set_value(localAssistantEmployee.value || "")
    }
  }
  assistantControl?.$input?.prop("disabled", Boolean(sessionControlsDisabled.value))
}

function syncPastAppointmentControl() {
  if (pastAppointmentControl?.get_value && pastAppointmentControl?.set_value) {
    const current = pastAppointmentControl.get_value()
    if (current !== (localPastAppointment.value || "")) {
      pastAppointmentControl.set_value(localPastAppointment.value || "")
    }
  }
  pastAppointmentControl?.$input?.prop(
    "disabled",
    Boolean(sessionControlsDisabled.value) || !showPastAppointmentControl.value
  )
}

function syncTreatmentCaseControl() {
  if (treatmentCaseControl?.get_value && treatmentCaseControl?.set_value) {
    const current = treatmentCaseControl.get_value()
    if (current !== (localTreatmentCase.value || "")) {
      treatmentCaseControl.set_value(localTreatmentCase.value || "")
    }
  }
  treatmentCaseControl?.$input?.prop("disabled", Boolean(sessionControlsDisabled.value))
}

function handleSessionDateInput(value) {
  const normalized = value || ""
  if (localSessionDate.value === normalized) return
  localSessionDate.value = normalized
  emit("update:session-date", localSessionDate.value)
}

function handleAppointmentCategoryChange(value) {
  const nextValue = normalizeCategoryValue(value)
  if (localAppointmentCategory.value === nextValue) return
  localAppointmentCategory.value = nextValue
  emit("update:appointment-category", nextValue)
  if (nextValue !== "Follow-up" && localPastAppointment.value) {
    localPastAppointment.value = ""
    syncPastAppointmentControl()
    emit("update:past-appointment", "")
  }
}

function handleSessionCategoryInput(value) {
  const normalized = value || ""
  if (localAppointmentCategory.value === normalized) return
  handleAppointmentCategoryChange(normalized)
}

function handleSessionDateChangeFromControl() {
  const value = dateControl?.get_value ? dateControl.get_value() : ""
  handleSessionDateInput(value)
}

function handleSessionCategoryChangeFromControl() {
  const value = categoryControl?.get_value ? categoryControl.get_value() : ""
  handleSessionCategoryInput(value)
}

function handleTreatmentCaseChangeFromControl() {
  const value = treatmentCaseControl?.get_value ? treatmentCaseControl.get_value() : ""
  if (localTreatmentCase.value === value) return
  localTreatmentCase.value = value || ""
  emit("update:treatment-case", localTreatmentCase.value)
}

function buildCategoryOptions() {
  return ["", ...categoryOptions].join("\n")
}

function toggleConsentMenu() {
  if (!signedCount.value) return
  consentMenuOpen.value = !consentMenuOpen.value
  if (consentMenuOpen.value) {
    labMenuOpen.value = false
  }
}

function toggleLabMenu() {
  if (!labMenuOpen.value) {
    resetLabSelections()
    consentMenuOpen.value = false
  }
  labMenuOpen.value = !labMenuOpen.value
}

function toggleLabCandidate(name) {
  if (!name) return
  if (selectedLabProcedureNames.value.includes(name)) {
    selectedLabProcedureNames.value = selectedLabProcedureNames.value.filter((value) => value !== name)
    return
  }
  selectedLabProcedureNames.value = [...selectedLabProcedureNames.value, name]
}

function submitCreateLabCase() {
  if (!canCreateFromVisit.value) return
  const selected = [...selectedLabProcedureNames.value]
  labMenuOpen.value = false
  emit("create-session-lab-case", selected)
}

function submitCreatePlannedLabCase() {
  if (!props.canCreatePlannedLabCase) return
  labMenuOpen.value = false
  emit("create-planned-lab-case")
}

function linkSelectedProcedures(caseName) {
  if (!caseName || !canLinkSelectedProcedures.value) return
  const selected = [...selectedLabProcedureNames.value]
  labMenuOpen.value = false
  emit("attach-procedures-to-lab-case", { caseName, procedureNames: selected })
}

function openLabCase(caseName) {
  if (!caseName) return
  labMenuOpen.value = false
  emit("open-lab-case", caseName)
}

function selectConsent(row) {
  consentMenuOpen.value = false
  emit("view-consent", row)
}

function formatSignedOn(value) {
  if (!value) return ""
  try {
    return frappe.datetime.str_to_user(value)
  } catch (e) {
    return value
  }
}

function formatDueDate(value) {
  if (!value) return ""
  try {
    return frappe.datetime.str_to_user(value)
  } catch (e) {
    return value
  }
}

function formatCandidateLabel(row) {
  const title = row?.display_name || row?.procedure_template_label || row?.procedure_template || row?.name || __("Procedure")
  const tooth = row?.tooth && row.tooth !== "N/A" ? ` · ${__('Tooth')} ${row.tooth}` : ""
  return `${title}${tooth}`
}

function formatLabCaseMeta(row) {
  const parts = []
  if (row?.is_planned_case) parts.push(__("Planned draft"))
  if (row?.case_type) parts.push(row.case_type)
  if (row?.lab) parts.push(row.lab)
  if (row?.date_due) parts.push(`${__('Due')} ${formatDueDate(row.date_due)}`)
  return parts.join(" · ") || __("Open case")
}

function caseStatusLabel(row) {
  if (row?.is_planned_case && (row?.status || "Draft") === "Draft") {
    return __("Planned")
  }
  return row?.status || __("Open")
}

function labStatusClass(row) {
  if (row?.is_overdue) return "overdue"
  if (row?.is_planned_case && (row?.status || "Draft") === "Draft") return "planned"
  const token = (row?.status || "").toLowerCase()
  if (token.includes("ready") || token.includes("received")) return "ready"
  if (token.includes("sent") || token.includes("production") || token.includes("shipped")) return "in-flight"
  return "draft"
}

function handleOutsideClick(event) {
  if (consentMenuRef.value && !consentMenuRef.value.contains(event.target)) {
    consentMenuOpen.value = false
  }
  if (labMenuRef.value && !labMenuRef.value.contains(event.target)) {
    labMenuOpen.value = false
  }
}

function buildPastAppointmentQuery() {
  const filters = {}
  if (props.patientId) {
    filters.patient = props.patientId
  }
  if (props.appointmentId) {
    filters.name = ["!=", props.appointmentId]
  }
  return { filters }
}

function buildTreatmentCaseQuery() {
  const filters = { status: ["in", ["Draft", "Active", "Paused"]] }
  if (props.patientId) {
    filters.patient = props.patientId
  } else {
    filters.name = ["=", ""]
  }
  return { filters }
}

function buildAssistantQuery() {
  return {
    query: "do_derma.api.get_nursing_assistant_employees",
  }
}

function formatDate(value) {
  if (!value) return ""
  try {
    return frappe.datetime.str_to_user(value)
  } catch (e) {
    return value
  }
}

onMounted(() => {
  if (dateRef.value && frappe?.ui?.form?.make_control) {
    dateControl = frappe.ui.form.make_control({
      parent: dateRef.value,
      df: {
        fieldtype: "Date",
        fieldname: "chart_session_date",
        label: __("Date"),
        placeholder: __("Date"),
      },
      render_input: true,
    })
    dateControl.$input?.on("change", handleSessionDateChangeFromControl)
    syncDateControl()
  }
  if (categoryRef.value && frappe?.ui?.form?.make_control) {
    categoryControl = frappe.ui.form.make_control({
      parent: categoryRef.value,
      df: {
        fieldtype: "Select",
        fieldname: "chart_appointment_category",
        label: __("Appointment category"),
        options: buildCategoryOptions(),
      },
      render_input: true,
    })
    categoryControl.$input?.on("change", handleSessionCategoryChangeFromControl)
    syncCategoryControl()
  }
  if (providerRef.value && frappe?.ui?.form?.make_control) {
    providerControl = frappe.ui.form.make_control({
      parent: providerRef.value,
      df: {
        fieldtype: "Link",
        options: "Healthcare Practitioner",
        fieldname: "chart_practitioner",
        placeholder: "Doctor",
        label: __("Practitioner"),

      },
      render_input: true,
    })
    providerControl.$input?.on("change", () => {
      const val = providerControl.get_value()
      if (localProvider.value !== val) {
        localProvider.value = val || ""
        emit("update:provider", localProvider.value)
      }
    })
    syncProviderControl()
  }
  if (assistantRef.value && frappe?.ui?.form?.make_control) {
    assistantControl = frappe.ui.form.make_control({
      parent: assistantRef.value,
      df: {
        fieldtype: "Link",
        options: "Employee",
        fieldname: "chart_assistant_employee",
        placeholder: __("Assistant"),
        label: __("Assistant"),
        get_query: buildAssistantQuery,
      },
      render_input: true,
    })
    assistantControl.$input?.on("change", () => {
      const val = assistantControl.get_value()
      if (localAssistantEmployee.value !== val) {
        localAssistantEmployee.value = val || ""
        emit("update:assistant-employee", localAssistantEmployee.value)
      }
    })
    syncAssistantControl()
  }
  if (pastAppointmentRef.value && frappe?.ui?.form?.make_control) {
    pastAppointmentControl = frappe.ui.form.make_control({
      parent: pastAppointmentRef.value,
      df: {
        fieldtype: "Link",
        options: "Patient Appointment",
        fieldname: "chart_past_appointment",
        placeholder: __("Past appointment"),
        label: __("Follow-up for"),
        get_query: buildPastAppointmentQuery,
      },
      render_input: true,
    })
    pastAppointmentControl.$input?.on("change", () => {
      const val = pastAppointmentControl.get_value()
      if (localPastAppointment.value !== val) {
        localPastAppointment.value = val || ""
        emit("update:past-appointment", localPastAppointment.value)
      }
    })
    syncPastAppointmentControl()
  }
  if (treatmentCaseRef.value && frappe?.ui?.form?.make_control) {
    treatmentCaseControl = frappe.ui.form.make_control({
      parent: treatmentCaseRef.value,
      df: {
        fieldtype: "Link",
        options: "Treatment Case",
        fieldname: "chart_treatment_case",
        placeholder: __("Treatment case"),
        label: __("Treatment Case"),
        get_query: buildTreatmentCaseQuery,
      },
      render_input: true,
    })
    treatmentCaseControl.$input?.on("change", handleTreatmentCaseChangeFromControl)
    syncTreatmentCaseControl()
  }

  document.addEventListener("click", handleOutsideClick)
})

onBeforeUnmount(() => {
  try {
    dateControl?.$wrapper?.remove()
    categoryControl?.$wrapper?.remove()
    providerControl?.$wrapper?.remove()
    assistantControl?.$wrapper?.remove()
    treatmentCaseControl?.$wrapper?.remove()
    pastAppointmentControl?.$wrapper?.remove()
  } catch (e) {
    /* no-op */
  }
  dateControl = null
  categoryControl = null
  providerControl = null
  assistantControl = null
  treatmentCaseControl = null
  pastAppointmentControl = null
  document.removeEventListener("click", handleOutsideClick)
})
</script>

<style scoped>
.dental-chart-page .chart-topbar {
  margin-bottom: 12px;
}

.dental-chart-page .topbar-main {
  display: grid;
  align-items: start;
  gap: 12px;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
}

.dental-chart-page .mode-rail {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-self: start;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.dental-chart-page .mode-label {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
}

.dental-chart-page .primary-toggle {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid #dbe3ee;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}

.dental-chart-page .primary-toggle button {
  border: none;
  background: transparent;
  min-width: 0;
  padding: 9px 8px;
  font-weight: 700;
  font-size: 12px;
  color: #475467;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.dental-chart-page .primary-toggle button:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.dental-chart-page .primary-toggle button.active {
  background: #2563eb;
  color: #fff;
}

.dental-chart-page .primary-toggle button:not(.active):hover {
  background: #eef2ff;
  color: #1d4ed8;
}

.dental-chart-page .session-shell {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border: 1px solid #d7e2f1;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: inset 4px 0 0 #2563eb;
}

.dental-chart-page .session-shell.disabled {
  opacity: 0.9;
}

.dental-chart-page .session-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.dental-chart-page .session-head-copy {
  min-width: 0;
}

.dental-chart-page .session-head-copy strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.dental-chart-page .session-head-copy small {
  display: block;
  color: #64748b;
  font-size: 11px;
  margin-top: 1px;
}

.dental-chart-page .case-context-inline {
  margin-top: 4px;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.dental-chart-page .case-chip {
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}

.dental-chart-page .case-meta {
  color: #475467;
  font-size: 11px;
}

.dental-chart-page .session-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: 10px;
  align-items: end;
  min-width: 0;
}

.dental-chart-page .session-grid > * {
  min-width: 0;
}

.dental-chart-page .context-lock-toggle {
  display: inline-flex;
  align-items: center;
  border: 1px solid #d6e0ef;
  background: #f8fafc;
  color: #334155;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
}

.dental-chart-page .context-lock-toggle.unlocked {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.dental-chart-page .session-control {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
}

.dental-chart-page .session-control > span {
  font-size: 10px;
  color: #64748b;
  font-weight: 700;
}

.dental-chart-page .frappe-control-host {
  width: 100%;
}

.dental-chart-page .frappe-link :deep(.form-group),
.dental-chart-page .frappe-control-host :deep(.form-group) {
  margin-bottom: 0;
}

.dental-chart-page .frappe-link :deep(.control-label),
.dental-chart-page .frappe-control-host :deep(.control-label) {
  margin-bottom: 5px;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.dental-chart-page .frappe-link :deep(.control-input-wrapper),
.dental-chart-page .frappe-control-host :deep(.control-input-wrapper) {
  width: 100%;
}

.dental-chart-page .frappe-link :deep(input),
.dental-chart-page .frappe-link :deep(select),
.dental-chart-page .frappe-control-host :deep(input),
.dental-chart-page .frappe-control-host :deep(select) {
  width: 100%;
  min-height: 34px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  box-shadow: none;
}

.dental-chart-page .frappe-link :deep(input:focus),
.dental-chart-page .frappe-link :deep(select:focus),
.dental-chart-page .frappe-control-host :deep(input:focus),
.dental-chart-page .frappe-control-host :deep(select:focus) {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.dental-chart-page .session-control :deep(.form-group) {
  margin-bottom: 0;
}

.dental-chart-page .session-control :deep(.control-input-wrapper .input-with-feedback),
.dental-chart-page .session-control :deep(.control-input),
.dental-chart-page .session-control :deep(select),
.dental-chart-page .session-control :deep(input) {
  border: 1px solid #d7dce3;
  border-radius: 8px;
  min-height: 34px;
  padding: 6px 10px;
  font-size: 13px;
  width: 100%;
  background: #f8fafc;
  color: #0f172a;
}

.dental-chart-page .session-control :deep(.control-input-wrapper .input-with-feedback:focus),
.dental-chart-page .session-control :deep(.control-input:focus),
.dental-chart-page .session-control :deep(select:focus),
.dental-chart-page .session-control :deep(input:focus) {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.dental-chart-page .session-control :deep(select:disabled),
.dental-chart-page .session-control :deep(input:disabled) {
  cursor: not-allowed;
  opacity: 0.72;
}

.dental-chart-page .session-control-link .frappe-link {
  min-width: 0;
}

.dental-chart-page .session-control-link :deep(.control-input-wrapper .input-with-feedback) {
  border-radius: 8px;
}

.dental-chart-page .session-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 1px;
}

.dental-chart-page .session-actions .ghost {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475467;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.dental-chart-page .session-actions .ghost:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.dental-chart-page .session-actions .ghost:hover {
  background: #eef2f7;
  border-color: #cfd8e3;
}

.dental-chart-page .lab-dropdown,
.dental-chart-page .consent-dropdown {
  position: relative;
}

.dental-chart-page .lab-launcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dental-chart-page .lab-launcher.attention {
  border-color: #f59e0b;
  background: #fffbeb;
  color: #92400e;
}

.dental-chart-page .lab-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}

.dental-chart-page .lab-pill.queued {
  background: #dbeafe;
  color: #1d4ed8;
}

.dental-chart-page .lab-menu,
.dental-chart-page .consent-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  z-index: 10;
}

.dental-chart-page .lab-menu {
  width: 400px;
  padding: 10px;
  max-height: min(72vh, 680px);
  overflow: auto;
}

.dental-chart-page .lab-menu-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf2f7;
}

.dental-chart-page .lab-menu-header strong,
.dental-chart-page .section-title,
.dental-chart-page .case-name,
.dental-chart-page .candidate-title {
  color: #0f172a;
}

.dental-chart-page .lab-menu-header small,
.dental-chart-page .candidate-copy small,
.dental-chart-page .lab-case-row small,
.dental-chart-page .lab-empty {
  display: block;
  color: #64748b;
}

.dental-chart-page .lab-summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.dental-chart-page .lab-readiness-note {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.dental-chart-page .summary-chip {
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
}

.dental-chart-page .summary-chip.overdue {
  background: #fee2e2;
  color: #b91c1c;
}

.dental-chart-page .summary-chip.action-needed {
  background: #fef3c7;
  color: #92400e;
}

.dental-chart-page .summary-chip.waiting {
  background: #dbeafe;
  color: #1d4ed8;
}

.dental-chart-page .summary-chip.received,
.dental-chart-page .summary-chip.ready {
  background: #dcfce7;
  color: #166534;
}

.dental-chart-page .lab-section {
  padding-top: 10px;
}

.dental-chart-page .action-section {
  padding-top: 12px;
}

.dental-chart-page .section-title {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 8px;
}

.dental-chart-page .lab-action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.dental-chart-page .lab-action-card {
  border: 1px solid #dbe3ee;
  background: #f8fafc;
  border-radius: 14px;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dental-chart-page .lab-action-card strong {
  color: #0f172a;
  font-size: 13px;
}

.dental-chart-page .lab-action-card small {
  color: #64748b;
  line-height: 1.35;
}

.dental-chart-page .lab-action-card.primary {
  background: linear-gradient(145deg, #eff6ff, #dbeafe);
  border-color: #bfdbfe;
}

.dental-chart-page .lab-action-card.secondary {
  background: linear-gradient(145deg, #f8fafc, #ecfeff);
  border-color: #cbd5e1;
}

.dental-chart-page .lab-action-card:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dental-chart-page .lab-candidate-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  cursor: pointer;
}

.dental-chart-page .candidate-copy {
  min-width: 0;
}

.dental-chart-page .lab-selection-note {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}

.dental-chart-page .lab-case-row {
  width: 100%;
  border: 1px solid #edf2f7;
  background: #f8fafc;
  border-radius: 10px;
  padding: 9px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  text-align: left;
  cursor: pointer;
}

.dental-chart-page .lab-case-copy {
  min-width: 0;
}

.dental-chart-page .lab-case-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.dental-chart-page .lab-case-row + .lab-case-row {
  margin-top: 8px;
}

.dental-chart-page .case-status {
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.dental-chart-page .case-status.draft {
  background: #e2e8f0;
  color: #334155;
}

.dental-chart-page .case-status.in-flight {
  background: #dbeafe;
  color: #1d4ed8;
}

.dental-chart-page .case-status.planned {
  background: #fef3c7;
  color: #92400e;
}

.dental-chart-page .case-status.ready {
  background: #dcfce7;
  color: #166534;
}

.dental-chart-page .case-status.overdue {
  background: #fee2e2;
  color: #b91c1c;
}

.dental-chart-page .lab-empty {
  padding-top: 10px;
}

.dental-chart-page .inline-link {
  padding: 4px 8px;
}

.dental-chart-page .consent-menu {
  min-width: 220px;
  padding: 6px;
}

.dental-chart-page .consent-menu button {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 8px 10px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-weight: 600;
  cursor: pointer;
}

.dental-chart-page .consent-menu button:hover,
.dental-chart-page .lab-case-row:hover {
  background: #f3f4f6;
}

.dental-chart-page .consent-menu .label {
  color: #0f172a;
}

.dental-chart-page .consent-menu small {
  color: #64748b;
}

@media (max-width: 1260px) {
  .dental-chart-page .topbar-main {
    grid-template-columns: 1fr;
  }

  .dental-chart-page .session-grid {
    grid-template-columns: repeat(2, minmax(140px, 1fr));
  }

  .dental-chart-page .session-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 860px) {
  .dental-chart-page .topbar-main {
    padding: 8px;
  }

  .dental-chart-page .mode-rail,
  .dental-chart-page .session-shell {
    padding: 8px;
  }

  .dental-chart-page .primary-toggle {
    width: 100%;
  }

  .dental-chart-page .primary-toggle button {
    flex: 1 1 0;
    padding: 8px 7px;
    font-size: 12px;
  }

  .dental-chart-page .session-grid {
    grid-template-columns: 1fr;
  }

  .dental-chart-page .session-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .dental-chart-page .session-actions {
    width: 100%;
    flex-wrap: wrap;
    gap: 8px;
  }

  .dental-chart-page .lab-menu {
    right: auto;
    left: 0;
    width: min(400px, calc(100vw - 56px));
  }

  .dental-chart-page .lab-action-grid {
    grid-template-columns: 1fr;
  }
}
</style>

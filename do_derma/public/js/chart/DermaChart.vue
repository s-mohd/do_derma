<template>
  <div class="dental-chart-page derma-chart-page" data-test="derma-chart-root">
    <div v-if="!contextReady" class="chart-empty-state" data-test="chart-empty-state">
      <h3>{{ __("Select a patient") }}</h3>
      <p>{{ __("Search for a patient here, or pick one in the health sidebar.") }}</p>
      <div ref="patientPickerHost" class="chart-empty-picker" data-test="chart-empty-patient-picker"></div>
    </div>

    <div v-else-if="loading && !patient.name" class="chart-loading-skeleton" role="status" data-test="chart-loading" :aria-label="__('Loading derma chart')">
      <div class="skeleton-block skeleton-header"></div>
      <div class="skeleton-block skeleton-tabs"></div>
      <div class="skeleton-grid">
        <div class="skeleton-block skeleton-main"></div>
        <div class="skeleton-block skeleton-side"></div>
      </div>
    </div>

    <div v-else-if="loadError && !patient.name" class="chart-error-state" data-test="chart-error">
      <h3>{{ __("Unable to load Derma Chart") }}</h3>
      <p>{{ loadError }}</p>
      <button type="button" class="primary" data-test="chart-error-retry" @click="refresh">{{ __("Retry") }}</button>
    </div>

    <template v-else>
      <div v-if="loadError" class="chart-error-banner" role="alert" data-test="chart-error-banner">
        <span>{{ loadError }}</span>
        <button type="button" class="ghost small" @click="refresh">{{ __("Retry") }}</button>
      </div>

      <DermaEncounterHeader
        :patient="patient"
        :appointment="appointment"
        :encounter="encounter"
        :practitioner-name="currentPractitionerName"
        :allergy-text="patientAllergyText"
        :insurance-label="insuranceStatusLabel"
        :has-session-context="hasSessionContext"
        :completing="completingSession"
        :pending="completionPending"
        :alerts="encounterAlertItems"
        @complete="completeSession"
        @alert-action="handleEncounterAlert"
      />

      <section class="derma-section-bar" data-test="derma-section-bar">
        <nav class="derma-section-tabs" :aria-label="__('Derma encounter sections')">
          <button
            v-for="section in SECTION_TABS"
            :key="section.key"
            type="button"
            :data-test="`section-tab-${section.key}`"
            :data-active="activeSection === section.key ? 'true' : 'false'"
            :class="{ active: activeSection === section.key }"
            @click="setActiveSection(section.key)"
          >
            <span>{{ section.label }}</span>
            <i
              v-if="section.key === 'assessment' && assessmentPanel.isFilled"
              class="tab-tick"
              data-test="assessment-tick"
              :title="__('Assessment documented')"
            >✓</i>
            <i
              v-if="section.key === 'procedures' && procedureCount"
              class="tab-count"
              data-test="procedures-tab-count"
              :title="__('{0} procedure(s) this visit').replace('{0}', procedureCount)"
            >{{ procedureCount }}</i>
            <small v-if="section.key !== 'assessment' || !assessmentModeToggleVisible">{{ section.hint }}</small>
            <small
              v-else
              class="tab-mode-toggle"
              data-test="assessment-mode-toggle"
              role="group"
              :aria-label="__('Assessment format')"
              :data-locked="assessmentModeLocked ? 'true' : 'false'"
              :title="assessmentModeLocked ? __('The format is locked after submission.') : ''"
            >
              <span
                v-for="toggleMode in assessmentPanel.availableModes"
                :key="toggleMode"
                role="button"
                :tabindex="assessmentModeLocked ? -1 : 0"
                :data-test="`assessment-mode-${toggleMode.toLowerCase()}`"
                :data-active="assessmentPanel.mode === toggleMode ? 'true' : 'false'"
                @click.stop="requestAssessmentModeChange(toggleMode)"
                @keydown.enter.stop.prevent="requestAssessmentModeChange(toggleMode)"
              >{{ assessmentModeShortLabel(toggleMode) }}</span>
            </small>
          </button>
        </nav>
      </section>

      <section class="derma-console-grid no-side">
        <main class="derma-console-main">
          <template v-if="activeSection === 'assessment'">
            <div class="clinical-notes-grid" data-test="assessment-section">
              <section class="clinical-soap-stack">
                <AssessmentPanel
                  :mode="assessmentPanel.mode"
                  :available-modes="assessmentPanel.availableModes"
                  :layout="assessmentPanel.layout"
                  :values="assessmentPanel.values"
                  :soap-layout="assessmentPanel.soapLayout"
                  :soap-values="assessmentPanel.soapValues"
                  :context-values="assessmentPanel.contextValues"
                  :loading="assessmentPanel.loading"
                  :saving="assessmentPanel.saving"
                  :error="assessmentPanel.error"
                  :has-encounter="Boolean(assessmentPanel.encounter)"
                  :docstatus="assessmentPanel.docstatus"
                  :edit-mode="assessmentPanel.editing"
                  :allow-on-submit-fields="assessmentEditableOnSubmitFields"
                  @request-edit="assessmentPanel.editing = true"
                  @save="saveAssessment"
                />
                <section class="chart-annotation-history encounter-annotation-history">
                  <header>
                    <div>
                      <strong>{{ __("Drawings") }}</strong>
                      <small>{{ annotations.length ? __("{0} saved drawing(s)").replace("{0}", annotations.length) : __("No saved drawings yet") }}</small>
                    </div>
                    <button type="button" class="primary small" data-test="annotate-consultation" @click="openAnnotationStudio({ annotation: null })">
                      <span aria-hidden="true">✎</span>
                      {{ __("Annotate Consultation") }}
                    </button>
                  </header>
                  <div v-if="annotations.length" class="chart-annotation-list">
                    <div v-for="annotation in annotations.slice(0, 8)" :key="annotation.name" class="chart-annotation-card">
                      <button type="button" @click="openAnnotationHistory(annotation)">
                        <span class="chart-annotation-preview">
                          <img
                            v-if="annotationPreview(annotation) && !isBroken(annotationPreview(annotation))"
                            :src="annotationPreview(annotation)"
                            :alt="annotationTemplateLabel(annotation)"
                            loading="lazy"
                            @error="markBroken(annotationPreview(annotation))"
                          />
                          <span v-else>{{ __("No preview") }}</span>
                        </span>
                        <b>{{ annotationTemplateLabel(annotation) }}</b>
                        <small>{{ formatDate(annotation.creation || annotation.modified) }}</small>
                      </button>
                      <button
                        v-if="isResumableAnnotation(annotation)"
                        type="button"
                        class="chart-annotation-edit"
                        data-test="annotation-resume"
                        :title="__('Edit')"
                        @click="openAnnotationStudio({ annotation })"
                      >
                        <span aria-hidden="true">✎</span>
                      </button>
                      <button
                        v-if="isResumableAnnotation(annotation) && !isEncounterLocked"
                        type="button"
                        class="chart-annotation-delete"
                        data-test="annotation-delete"
                        :title="__('Delete')"
                        @click="deleteAnnotation(annotation, 'Patient Encounter', encounter.name)"
                      >
                        <span aria-hidden="true">✕</span>
                      </button>
                    </div>
                  </div>
                  <p v-else class="panel-muted">{{ __("Saved encounter drawings will appear here.") }}</p>
                </section>
              </section>
            </div>
          </template>

          <template v-else-if="activeSection === 'procedures'">
            <div class="procedures-section-stack" data-test="procedures-section">
              <DegradedSectionNotice
                v-if="isSectionDegraded('procedures')"
                section="procedures"
                :label="__('procedures')"
                @retry="refresh"
              />
              <ProcedurePanel
                :status-pills="STATUS_PILLS"
                :groups="groupedProcedures"
                :total-count="procedureCount"
                :doctor-name="currentPractitionerName"
                :price-lists="priceLists"
                :default-price-list="defaultPriceList"
                :sync-disabled="!hasSessionContext || syncingBillables"
                :anesthesia-recorded="anesthesiaRecorded"
                :read-only="isEncounterLocked"
                :previous-mark-count="lastVisitMarks.length"
                :enable-lab-cases="!!featureToggles.enable_lab_cases"
                :enable-billing-sync="!!featureToggles.enable_billing_sync"
                @refresh="refresh"
                @annotate-procedure="annotateProcedure"
                @sync-billables="syncBillablesForSession"
                @new-procedure="createProcedure"
                @copy-marks="copyMarksFromLastVisit"
              />
            </div>
          </template>

          <template v-else-if="activeSection === 'photos'">
            <div class="photos-section-stack" data-test="photos-section">
              <DegradedSectionNotice
                v-if="isSectionDegraded('photos')"
                section="photos"
                :label="__('photos')"
                @retry="refresh"
              />
              <PhotosPanel
                :photo-sets="photoSets"
                :previous-photo-sets="previousPhotoSets"
                :active-procedure="activeProcedure"
                :active-procedure-treatments="activeProcedureTreatments"
                :requires-before-after="requiresBeforeAfterPhotos"
                :read-only="isEncounterLocked"
                @upload="uploadPhotos"
                @retag="retagPhoto"
                @delete="deletePhoto"
              />
            </div>
          </template>

          <PrescriptionPanel
            v-else-if="activeSection === 'prescriptions'"
            :loading="prescriptionPanel.loading"
            :saving="prescriptionPanel.saving"
            :error="prescriptionPanel.error"
            :has-session-context="hasSessionContext"
            :has-encounter="Boolean(prescriptionPanel.encounter)"
            :encounter-name="prescriptionPanel.encounter"
            :rows="prescriptionPanel.rows"
            :read-only="isEncounterLocked"
            @refresh="() => loadPrescriptionPanel(true)"
            @save="savePrescriptionPanel"
          />

          <ConsentPanel
            v-else-if="activeSection === 'consent'"
            :loading="consentPanel.loading"
            :saving="consentPanel.saving"
            :sending="consentPanel.sending"
            :error="consentPanel.error"
            :has-session-context="hasSessionContext"
            :encounter-name="consentPanel.encounter"
            :consents="consentPanel.consents"
            :procedure-options="consentProcedureOptions"
            :preview-html="consentPanel.previewHtml"
            :preview-loading="consentPanel.previewLoading"
            :default-signed-by="patient.patient_name || patient.name"
            :reset-key="consentPanel.resetKey"
            :read-only="isEncounterLocked"
            :enable-whatsapp-consent="!!featureToggles.enable_whatsapp_consent"
            @refresh="() => loadConsentPanel(true)"
            @request-preview="requestConsentPreview"
            @create="createConsentFromPanel"
            @send-whatsapp="sendConsentViaWhatsApp"
            @open-consent="openSignedConsent"
            @resend-consent="resendConsentViaWhatsApp"
            @cancel-consent="cancelRemoteConsent"
          />

          <section v-else-if="activeSection === 'review'" class="workspace-shell review-shell" data-test="review-section">
        <div class="workspace-tabview">
          <div class="workspace-content review-section-stack">
            <section class="derma-timeline-workspace">
              <header>
                <div>
                  <strong>{{ __("Treatment Timeline") }}</strong>
                  <small>{{ visitTimeline.length ? __("{0} previous visit(s)").replace("{0}", visitTimeline.length) : __("No previous derma activity yet") }}</small>
                </div>
                <button type="button" class="ghost small" :disabled="chartOverlayMode === 'today'" @click="clearTimelineOverlay">
                  {{ __("Clear Overlay") }}
                </button>
              </header>

              <div v-if="visitTimeline.length" class="timeline-review-layout">
                <div class="timeline-visit-list">
                  <button
                    v-for="visit in visitTimeline"
                    :key="visit.key"
                    type="button"
                    class="timeline-visit-card"
                    :class="{ active: selectedTimelineVisitKey === visit.key }"
                    @click="selectTimelineVisit(visit)"
                  >
                    <span v-if="visit.preview_image && !isBroken(visit.preview_image)" class="timeline-preview">
                      <img
                        :src="visit.preview_image"
                        :alt="visit.date || visit.key"
                        loading="lazy"
                        @error="markBroken(visit.preview_image)"
                      />
                    </span>
                    <span v-else class="timeline-preview empty">{{ __("No photo") }}</span>
                    <span class="timeline-copy">
                      <strong>{{ formatDate(visit.date || visit.modified) || visit.key }}</strong>
                      <small>{{ visit.summary || __("No details") }}</small>
                      <em>{{ (visit.categories || []).join(", ") || __("Derma visit") }}</em>
                    </span>
                  </button>
                </div>

                <article v-if="selectedTimelineVisit" class="timeline-visit-detail">
                  <header>
                    <div>
                      <strong>{{ formatDate(selectedTimelineVisit.date || selectedTimelineVisit.modified) || __("Selected visit") }}</strong>
                      <small>{{ selectedTimelineVisit.summary }}</small>
                    </div>
                    <div class="timeline-detail-actions">
                      <button type="button" class="primary small" @click="overlayTimelineVisit(selectedTimelineVisit)">
                        {{ __("Overlay Marks") }}
                      </button>
                    </div>
                  </header>

                  <div class="timeline-stat-grid">
                    <span>
                      <b>{{ selectedTimelineVisit.marks?.length || 0 }}</b>
                      <small>{{ __("marks") }}</small>
                    </span>
                    <span>
                      <b>{{ selectedTimelineVisit.procedures?.length || 0 }}</b>
                      <small>{{ __("procedures") }}</small>
                    </span>
                    <span>
                      <b>{{ selectedTimelineVisit.photo_sets?.length || 0 }}</b>
                      <small>{{ __("photo sets") }}</small>
                    </span>
                  </div>

                  <div v-if="selectedTimelineVisit.photo_sets?.length" class="timeline-photo-grid">
                    <figure v-for="set in selectedTimelineVisit.photo_sets.slice(0, 4)" :key="set.name">
                      <img
                        v-if="set.preview_image && !isBroken(set.preview_image)"
                        :src="set.preview_image"
                        :alt="set.set_type || set.name"
                        loading="lazy"
                        @error="markBroken(set.preview_image)"
                      />
                      <span v-else>{{ __("No preview") }}</span>
                      <figcaption>{{ set.set_type || set.body_view || set.name }}</figcaption>
                    </figure>
                  </div>

                  <div v-if="selectedTimelineVisit.procedures?.length" class="timeline-section-list">
                    <h4>{{ __("Procedures") }}</h4>
                    <button
                      v-for="procedure in selectedTimelineVisit.procedures.slice(0, 8)"
                      :key="procedure.name"
                      type="button"
                      @click="openClinicalProcedure(procedure)"
                    >
                      <b>{{ procedure.title || procedure.template_label || procedure.procedure_template || procedure.name }}</b>
                      <small>{{ procedure.derma_detail_text || procedure.notes || procedure.status }}</small>
                    </button>
                  </div>

                  <div v-if="selectedTimelineVisit.status_changes?.length" class="timeline-section-list">
                    <h4>{{ __("Follow-up Signals") }}</h4>
                    <span v-for="(row, index) in selectedTimelineVisit.status_changes.slice(0, 8)" :key="`${row.status}-${index}`">
                      <b>{{ row.status }}</b>
                      <small>{{ [row.label, row.location].filter(Boolean).join(" · ") }}</small>
                    </span>
                  </div>
                </article>
              </div>

              <div v-else class="timeline-empty-state">
                {{ __("Previous visits, procedures, photos, and tracked marks will appear here after the patient has history.") }}
              </div>
            </section>

            <section class="derma-readiness-summary" data-test="review-readiness">
              <header>
                <div>
                  <strong>{{ __("Session Readiness") }}</strong>
                  <small>{{ readinessSummaryText }}</small>
                </div>
                <span class="readiness-mode" :data-mode="readinessEnforcement" data-test="review-readiness-mode">
                  {{ readinessEnforcement === "Block" ? __("Completion refused until resolved") : __("Completion warns only") }}
                </span>
              </header>

              <ul v-if="readinessBlockers.length" class="readiness-blocker-list" data-test="review-readiness-blockers">
                <li v-for="item in readinessBlockers" :key="item.key" :data-source="item.source">
                  <span class="readiness-source">{{ readinessSourceLabel(item.source) }}</span>
                  <b>{{ item.title }}</b>
                  <small>{{ item.detail || item.location || "" }}</small>
                </li>
              </ul>
            </section>

            <section class="derma-inventory-workspace">
              <header>
                <div>
                  <strong>{{ __("Inventory Readiness") }}</strong>
                  <small>{{ inventoryReadiness.length ? __("{0} product group(s)").replace("{0}", inventoryReadiness.length) : __("No product-consuming marks yet") }}</small>
                </div>
                <div class="followup-stats">
                  <span>
                    <b>{{ inventoryStats.ready }}</b>
                    <small>{{ __("ready") }}</small>
                  </span>
                  <span>
                    <b>{{ inventoryStats.warnings }}</b>
                    <small>{{ __("warnings") }}</small>
                  </span>
                  <span>
                    <b>{{ inventoryStats.blockers }}</b>
                    <small>{{ __("blockers") }}</small>
                  </span>
                </div>
              </header>

              <div v-if="inventoryReadiness.length" class="inventory-list">
                <article
                  v-for="item in inventoryReadiness"
                  :key="item.key"
                  class="inventory-card"
                  :class="[item.severity, item.status, { blocking: item.blocking }]"
                >
                  <header>
                    <div>
                      <strong>{{ item.product_name || item.product_item || __("Product") }}</strong>
                      <small>{{ [item.product_item, item.lot_no ? `Lot ${item.lot_no}` : "", item.expiry_date ? `Exp ${formatDate(item.expiry_date)}` : ""].filter(Boolean).join(" · ") }}</small>
                    </div>
                    <span>{{ item.status }}</span>
                  </header>
                  <div class="inventory-metrics">
                    <span v-for="metric in inventoryMetrics(item)" :key="metric.label">
                      <b>{{ metric.value }}</b>
                      <small>{{ metric.label }}</small>
                    </span>
                  </div>
                  <p>{{ item.message }}</p>
                  <footer>
                    <MarkResponseChips
                      :statuses="MARK_RESPONSE_STATUSES"
                      :mark="markForItem(item)"
                      @set="(status) => setItemResponse(item, status)"
                    />
                    <button type="button" class="ghost small" :disabled="!item.product_item" @click="openItem(item.product_item)">
                      {{ __("Open Item") }}
                    </button>
                  </footer>
                </article>
              </div>

              <div v-else class="followup-empty-state">
                {{ __("Inventory readiness will appear after Botox, filler, laser, or other product-consuming marks include product, dose, lot, and expiry details.") }}
              </div>
            </section>

            <section class="derma-followup-workspace">
              <header>
                <div>
                  <strong>{{ __("Follow-Up Intelligence") }}</strong>
                  <small>{{ followupItems.length ? __("{0} item(s)").replace("{0}", followupItems.length) : __("No follow-up risks detected") }}</small>
                </div>
                <div class="followup-stats">
                  <span>
                    <b>{{ followupStats.high }}</b>
                    <small>{{ __("high") }}</small>
                  </span>
                  <span>
                    <b>{{ followupStats.blockers }}</b>
                    <small>{{ __("blockers") }}</small>
                  </span>
                  <span>
                    <b>{{ followupStats.todos }}</b>
                    <small>{{ __("tasks") }}</small>
                  </span>
                </div>
              </header>

              <div v-if="followupItems.length" class="followup-list">
                <article
                  v-for="item in followupItems"
                  :key="item.key"
                  class="followup-card"
                  :class="[item.severity, { blocking: item.blocking, done: item.todo }]"
                >
                  <header>
                    <div>
                      <strong>{{ item.title }}</strong>
                      <small>{{ [item.type, item.category, item.location].filter(Boolean).join(" · ") }}</small>
                    </div>
                    <span>{{ formatDate(item.due_date) || __("No due date") }}</span>
                  </header>
                  <p>{{ item.detail }}</p>
                  <p v-if="item.downgraded_by_todo" class="readiness-downgraded" data-test="followup-downgraded">
                    {{ __("Warns instead of blocking: a follow-up task is already open.") }}
                  </p>
                  <footer>
                    <MarkResponseChips
                      :statuses="MARK_RESPONSE_STATUSES"
                      :mark="markForItem(item)"
                      @set="(status) => setItemResponse(item, status)"
                    />
                    <button type="button" class="ghost small" v-if="item.clinical_procedure" @click="openClinicalProcedure({ name: item.clinical_procedure })">
                      {{ __("Open Procedure") }}
                    </button>
                    <button type="button" class="primary small" :disabled="Boolean(item.todo)" @click="createFollowupTask(item)">
                      {{ item.todo ? __("Task Created") : __("Create Task") }}
                    </button>
                    <button type="button" class="ghost small" v-if="item.todo" @click="openTodo(item.todo)">
                      {{ __("Open Task") }}
                    </button>
                  </footer>
                </article>
              </div>

              <div v-else class="followup-empty-state">
                {{ __("Follow-up items will appear for monitored lesions, biopsies, worsening marks, missing photos, product gaps, and next-session reminders.") }}
              </div>
            </section>
          </div>
        </div>
      </section>
        </main>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue"
import ProcedurePanel from "./components/ProcedurePanel.vue"
import AssessmentPanel from "./components/assessment/AssessmentPanel.vue"
import PrescriptionPanel from "./components/PrescriptionPanel.vue"
import ConsentPanel from "./components/ConsentPanel.vue"
import DermaEncounterHeader from "./components/DermaEncounterHeader.vue"
import PhotosPanel from "./components/photos/PhotosPanel.vue"
import DegradedSectionNotice from "./components/DegradedSectionNotice.vue"
import MarkResponseChips from "./components/MarkResponseChips.vue"
import { openDermaAnnotationStudio } from "./annotation/DermaAnnotationStudio.jsx"
import { allowedBodyTemplates } from "../shared/allowed_body_templates.js"
import { procedureDisplayName } from "../shared/procedure_label.js"
import { useBrokenImages } from "../shared/broken_images.js"
import { nameDialogControls } from "../shared/dialog_a11y.js"

const __ = window.__ || ((txt) => txt)

function escapeHtml(value) {
  const text = String(value ?? "")
  const frappeEscape = window.frappe?.utils?.escape_html
  if (frappeEscape) return frappeEscape(text)
  return text.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char])
}

const props = defineProps({
  context: { type: Object, default: () => ({}) },
})

const STATUS_PILLS = [
  { key: "Draft", label: __("Draft") },
  { key: "In Progress", label: __("In Progress") },
  { key: "Completed", label: __("Completed") },
  { key: "Cancelled", label: __("Cancelled") },
]

const MARK_RESPONSE_STATUSES = ["Improving", "Stable", "Worse", "Resolved", "Monitoring"]

// Readiness is the server's; the chart only says which engine an item came from.
const READINESS_INVENTORY = "inventory"
const READINESS_FOLLOWUP = "followup"
const ENFORCEMENT_WARN = "Warn"
const ENFORCEMENT_BLOCK = "Block"
const EMPTY_READINESS = { items: [], blockers: [], enforcement: ENFORCEMENT_WARN }

const SECTION_TABS = [
  { key: "assessment", label: __("Assessment"), hint: __("Notes") },
  { key: "procedures", label: __("Procedures"), hint: __("Treatment") },
  { key: "photos", label: __("Photos"), hint: __("Compare") },
  { key: "prescriptions", label: __("Prescription"), hint: __("Rx") },
  { key: "consent", label: __("Consent"), hint: __("Forms") },
  { key: "review", label: __("Review"), hint: __("Sign-off") },
]

const SECTION_KEYS = SECTION_TABS.map((section) => section.key)
const DEFAULT_SECTION = "assessment"

// Stored preferences from the five-tab layout, so a returning user is not stranded.
const SECTION_ALIASES = {
  clinical: "assessment",
  encounter: "assessment",
  chart: "assessment",
  notes: "assessment",
  procedure: "procedures",
  consents: "consent",
}

// Chart sections degrade independently on the server; these are the context_errors
// labels (api.py get_patient_derma_chart) that make a tab unreliable.
const SECTION_CONTEXT_LABELS = {
  procedures: ["procedures"],
  photos: ["photo sets", "previous photo sets"],
  review: ["visit timeline", "readiness"],
}

const DERMA_SECTION_STORAGE_KEY = "do_derma_chart_last_section"
const DERMA_USER_SETTINGS_DOCTYPE = "Derma Chart"

const data = ref({})
const loading = ref(false)
const loadError = ref("")
const syncingBillables = ref(false)
const completingSession = ref(false)
const patientPickerHost = ref(null)
const { isBroken, markBroken } = useBrokenImages()
// A completion the clinician has started but not yet confirmed. Guards re-entry without
// claiming the button's busy label.
const completionPending = ref(false)
const selectedTemplate = ref(null)
const activeProcedureName = ref("")
const selectedBodyTemplate = ref(null)
const activeWorkspaceTab = ref("procedure_history")
const activeSection = ref(loadStoredDermaSection())
const selectedMarkName = ref("")
const selectedTimelineVisitKey = ref("")
const chartOverlayMode = ref("today")
const selectedPriceList = ref("")
const defaultPriceList = ref("")
const sessionProvider = ref("")
const sessionDate = ref("")
const sessionCategory = ref("")
const pastAppointment = ref("")
const sectionPreferenceHydrated = ref(false)
const sectionChosenByUser = ref(false)

const assessmentPanel = reactive({
  loading: false,
  saving: false,
  editing: false,
  error: "",
  encounter: "",
  docstatus: null,
  mode: "Structured",
  isFilled: false,
  availableModes: ["Structured"],
  layout: [],
  values: {},
  soapLayout: [],
  soapValues: {},
  contextValues: {},
})

const prescriptionPanel = reactive({ loading: false, saving: false, error: "", encounter: "", rows: [] })
const anesthesiaPanel = reactive({ loading: false, saving: false, error: "", encounter: "", rows: [] })
const consentPanel = reactive({
  loading: false,
  saving: false,
  sending: false,
  error: "",
  encounter: "",
  consents: [],
  previewHtml: "",
  previewLoading: false,
  resetKey: 0,
})

const loadedTabs = reactive({
  assessment: false,
  prescriptions: false,
  anesthesia: false,
  consents: false,
})

// Controls whose integration is unfinished stay hidden until Derma Settings turns
// them on. An unloaded chart hides them too, so nothing renders before we know.
const featureToggles = computed(() => data.value.settings || {})
const patient = computed(() => data.value.patient || {})
const appointment = computed(() => data.value.appointment || {})
const encounter = computed(() => data.value.encounter || {})
const isEncounterLocked = computed(() => Number(encounter.value.docstatus ?? 0) !== 0)
const procedureTemplates = computed(() => data.value.procedure_templates || [])
const procedures = computed(() => data.value.procedures || [])
const bodyTemplates = computed(() => (data.value.body_templates || []).map(normalizeBodyTemplate))
const categories = computed(() => data.value.categories || [])
const annotations = computed(() => data.value.annotations || [])
const encounterAnnotations = computed(() => data.value.encounter_annotations || [])
const procedureAnnotations = computed(() => data.value.procedure_annotations || {})
const marks = computed(() => data.value.marks || [])
const previousMarks = computed(() => data.value.previous_marks || [])
const lastVisitMarks = computed(() => {
  const latest = previousMarks.value.find((mark) => mark.encounter)?.encounter
  return latest ? previousMarks.value.filter((mark) => mark.encounter === latest) : []
})
const photoSets = computed(() => data.value.photo_sets || [])
const previousPhotoSets = computed(() => data.value.previous_photo_sets || [])
const visitTimeline = computed(() => data.value.visit_timeline || [])
const readiness = computed(() => data.value.readiness || EMPTY_READINESS)
const readinessItems = computed(() => readiness.value.items || [])
const readinessBlockers = computed(() => readiness.value.blockers || [])
const readinessEnforcement = computed(() => readiness.value.enforcement || ENFORCEMENT_WARN)
const followupItems = computed(() => readinessItems.value.filter((item) => item.source === READINESS_FOLLOWUP))
const inventoryReadiness = computed(() => readinessItems.value.filter((item) => item.source === READINESS_INVENTORY))
const activeProcedure = computed(() => {
  if (!activeProcedureName.value) return null
  return procedures.value.find((row) => row.name === activeProcedureName.value || row.clinical_procedure === activeProcedureName.value) || null
})
const activeProcedureTreatments = computed(() => activeProcedure.value?.derma_treatments || [])
const activeProcedureTreatment = computed(() => activeProcedureTreatments.value[0] || null)
const activeProcedureTreatmentName = computed(() => activeProcedureTreatment.value?.name || "")
const activeProcedureAnnotations = computed(() => {
  const name = activeProcedure.value?.name || activeProcedureName.value
  return name ? (procedureAnnotations.value[name] || []) : []
})
const contextReady = computed(() => Boolean(patient.value.name || props.context?.patient || props.context?.encounter || props.context?.appointment))
const hasSessionContext = computed(() => Boolean(encounter.value.name))
const currentPractitionerName = computed(() => encounter.value.practitioner_name || appointment.value.practitioner_name || sessionProvider.value || "")
const priceLists = computed(() => selectedPriceList.value ? [selectedPriceList.value] : [])
const anesthesiaRecorded = computed(() => anesthesiaPanel.rows.length > 0)
const procedureCount = computed(() => procedures.value.length)
const followupBlockers = computed(() => readinessBlockers.value.filter((item) => item.source === READINESS_FOLLOWUP))
const inventoryBlockers = computed(() => readinessBlockers.value.filter((item) => item.source === READINESS_INVENTORY))
const followupStats = computed(() => ({
  high: followupItems.value.filter((item) => item.severity === "high").length,
  blockers: followupBlockers.value.length,
  todos: followupItems.value.filter((item) => item.todo).length,
}))
const inventoryStats = computed(() => ({
  ready: inventoryReadiness.value.filter((item) => item.status === "ready").length,
  warnings: inventoryReadiness.value.filter((item) => item.status === "warning").length,
  blockers: inventoryBlockers.value.length,
}))
const readinessSummaryText = computed(() => {
  if (!readinessItems.value.length) return __("Nothing outstanding for this session")
  if (!readinessBlockers.value.length) {
    return __("{0} item(s), none blocking").replace("{0}", readinessItems.value.length)
  }
  return __("{0} blocker(s) of {1} item(s)")
    .replace("{0}", readinessBlockers.value.length)
    .replace("{1}", readinessItems.value.length)
})
function readinessSourceLabel(source) {
  return source === READINESS_INVENTORY ? __("Inventory") : __("Follow-up")
}

// Says which field a readiness line was built from, so the clinician knows where to fix it.
const CONTRIBUTOR_LABELS = { dose: __("dose"), consumable: __("materials") }

function readinessContributorLabel(item) {
  return (item.contributors || []).map((source) => CONTRIBUTOR_LABELS[source] || source).join(" + ")
}

/**
 * The tiles an inventory card can show, each one a label with a value behind it. A metric
 * nobody recorded is left out: a tile showing only its unit ("Nos", "available") reads as
 * debris on a card whose whole job is to say what is missing.
 */
function inventoryMetrics(item) {
  const metrics = []
  // formatNumber(null) reads as "0", which is a dose nobody recorded shown as one they did.
  if (item.dose !== null && item.dose !== undefined && item.dose !== "") {
    metrics.push({
      label: __("dose"),
      value: [formatNumber(item.dose), item.dose_unit].filter(Boolean).join(" "),
    })
  }
  if (item.available_qty !== null && item.available_qty !== undefined) {
    metrics.push({ label: __("available"), value: formatNumber(item.available_qty) })
  }
  if (item.marks?.length) metrics.push({ label: __("marks"), value: String(item.marks.length) })
  if (item.contributors?.length) {
    metrics.push({ label: __("recorded in"), value: readinessContributorLabel(item) })
  }
  return metrics
}
const selectedTemplateLabel = computed(() => selectedTemplate.value?.template || selectedTemplate.value?.name || __("No procedure selected"))
const patientAllergyText = computed(() => {
  return patient.value.custom_allergies || patient.value.allergies || patient.value.allergy || ""
})
const insuranceStatusLabel = computed(() => {
  return appointment.value.insurance_status || appointment.value.custom_insurance_status || appointment.value.custom_payment_type || appointment.value.payment_type || __("Self Pay")
})
const encounterAlertItems = computed(() => {
  const alerts = []
  if (patientAllergyText.value) {
    alerts.push({
      key: "allergy",
      label: __("Allergy Alert"),
      detail: patientAllergyText.value,
      tone: "danger",
    })
  }
  if (selectedTemplate.value?.custom_derma_consent_required && !consentPanel.consents.length) {
    alerts.push({
      key: "consent",
      label: __("Consent Required"),
      detail: selectedTemplateLabel.value,
      tone: "warning",
    })
  }
  if (requiresBeforeAfterPhotos.value && !procedurePhotoSets.value.length) {
    alerts.push({
      key: "photos",
      label: __("Photo Required"),
      detail: __("Upload procedure evidence before completion."),
      tone: "warning",
    })
  }
  for (const item of inventoryBlockers.value.slice(0, 2)) {
    alerts.push({
      key: `inventory-${item.key || item.product_item || item.product_name}`,
      label: __("Inventory Blocker"),
      detail: item.message || item.product_name || item.product_item,
      tone: "warning",
      tab: "inventory",
    })
  }
  for (const item of followupBlockers.value.slice(0, 2)) {
    alerts.push({
      key: `followup-${item.key || item.title}`,
      label: item.title || __("Follow-up"),
      detail: item.detail || item.location || "",
      tone: item.severity === "high" ? "danger" : "warning",
      tab: "followup",
    })
  }
  return alerts
})
const groupedProcedures = computed(() => {
  const groups = new Map()
  for (const row of procedures.value.map(normalizeProcedureRow)) {
    const key = row.procedure_date || row.start_date || row.date || "No Date"
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        procedure_date: key === "No Date" ? "" : key,
        timestamp: rowTimestamp(row),
        items: [],
      })
    }
    groups.get(key).items.push(row)
  }
  return Array.from(groups.values())
})

const consentProcedureOptions = computed(() =>
  procedures.value.map((row) => {
    const value = row.name
    const label = procedureDisplayName(row)
    const description = [row.status, row.derma_category || row.category, row.body_region || row.region_label]
      .filter(Boolean)
      .join(" · ")
    return {
      value,
      label,
      description,
      clinical_procedure: row.name,
      procedure_template: row.procedure_template,
      display_name: label,
    }
  })
)

const assessmentEditableOnSubmitFields = computed(() => {
  const layout = assessmentPanel.mode === "SOAP" ? assessmentPanel.soapLayout : assessmentPanel.layout
  return (layout || []).filter((row) => row.allow_on_submit).map((row) => row.fieldname).filter(Boolean)
})

const visibleMarks = computed(() => {
  const templateName = selectedTemplate.value?.name
  const bodyTemplate = selectedBodyTemplate.value?.name
  return marks.value
    .filter((mark) => (!templateName || mark.procedure_template === templateName) && (!bodyTemplate || mark.body_template === bodyTemplate))
    .sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0))
})

const selectedMark = computed(() => marks.value.find((mark) => mark.name === selectedMarkName.value) || null)

const selectedTimelineVisit = computed(() => visitTimeline.value.find((visit) => visit.key === selectedTimelineVisitKey.value) || visitTimeline.value[0] || null)

const procedurePhotoSets = computed(() => {
  const procedure = activeProcedure.value?.name
  if (!procedure) return []
  const treatmentNames = new Set(activeProcedureTreatments.value.map((row) => row.name).filter(Boolean))
  return photoSets.value.filter(
    (set) => set.clinical_procedure === procedure || (set.treatment_entry && treatmentNames.has(set.treatment_entry))
  )
})

// The requirement belongs to the procedure being charted, not to whatever template
// the picker happens to be showing.
const activeProcedureTemplate = computed(() => {
  const name = activeProcedure.value?.procedure_template
  return procedureTemplates.value.find((row) => row.name === name) || selectedTemplate.value
})

const requiresBeforeAfterPhotos = computed(() =>
  Boolean(activeProcedure.value && activeProcedureTemplate.value?.custom_derma_before_after_photo_required)
)

watch(
  () => props.context,
  (context) => {
    if (context?.patient || context?.appointment || context?.encounter) load(context)
  },
  { immediate: true, deep: true }
)

watch(
  () => activeWorkspaceTab.value,
  (tab) => ensureWorkspaceTab(tab)
)

// The empty state is where the eye lands, so the search lives there rather than only in
// the sidebar it used to point at.
watch(
  () => contextReady.value,
  (ready) => {
    if (ready) return
    nextTick(mountPatientPicker)
  },
  { immediate: true }
)

function mountPatientPicker() {
  const host = patientPickerHost.value
  if (!host || !window.frappe?.ui?.form?.make_control) return
  host.innerHTML = ""
  const control = frappe.ui.form.make_control({
    parent: host,
    df: {
      fieldtype: "Link",
      fieldname: "patient",
      options: "Patient",
      label: __("Patient"),
      placeholder: __("Search patients"),
      only_select: 1,
      change: () => {
        const chosen = control.get_value()
        if (chosen) load({ patient: chosen })
      },
    },
    render_input: true,
  })
}

watch(
  () => visibleMarks.value.map((mark) => mark.name).join(","),
  () => {
    if (selectedMarkName.value && !visibleMarks.value.some((mark) => mark.name === selectedMarkName.value)) {
      selectedMarkName.value = ""
    }
  }
)

/** The single owner of the "which tab" invariant: anything unrecognised lands on Assessment. */
function normalizeDermaSection(section) {
  if (SECTION_KEYS.includes(section)) return section
  return SECTION_ALIASES[section] || DEFAULT_SECTION
}

function storedUserSettingsSection() {
  try {
    const settings = window.frappe?.get_user_settings?.(DERMA_USER_SETTINGS_DOCTYPE) || {}
    return settings.last_section || settings.last_mode || ""
  } catch (error) {
    // User settings may not be bootstrapped yet; localStorage still answers.
    return ""
  }
}

function storedLocalSection() {
  try {
    return window.localStorage?.getItem(DERMA_SECTION_STORAGE_KEY) || ""
  } catch (error) {
    return ""
  }
}

function loadStoredDermaSection() {
  return normalizeDermaSection(storedUserSettingsSection() || storedLocalSection())
}

function persistDermaSection(section) {
  const nextSection = normalizeDermaSection(section)
  try {
    window.localStorage?.setItem(DERMA_SECTION_STORAGE_KEY, nextSection)
  } catch (error) {
    // Non-critical preference persistence.
  }
  try {
    window.frappe?.model?.user_settings?.save?.(DERMA_USER_SETTINGS_DOCTYPE, "last_section", nextSection)
  } catch (error) {
    // User settings may be unavailable in tests or early boot.
  }
}

/**
 * Settings resolve after the first load. Never move a practitioner off a tab they
 * already picked - the stored preference only seeds the very first render.
 */
async function hydrateDermaSectionPreference() {
  if (sectionPreferenceHydrated.value) return
  sectionPreferenceHydrated.value = true
  if (sectionChosenByUser.value) return
  try {
    const response = await window.frappe?.model?.user_settings?.get?.(DERMA_USER_SETTINGS_DOCTYPE)
    const savedSection = response?.last_section || response?.last_mode
    if (savedSection) activeSection.value = normalizeDermaSection(savedSection)
  } catch (error) {
    // The local fallback selected during setup remains valid.
  }
}

async function setActiveSection(section, tab = "") {
  sectionChosenByUser.value = true
  activeSection.value = normalizeDermaSection(section)
  if (tab) activeWorkspaceTab.value = tab
  persistDermaSection(activeSection.value)
  await ensureSectionData(activeSection.value, tab)
}

async function ensureSectionData(section = activeSection.value, tab = activeWorkspaceTab.value) {
  const normalized = normalizeDermaSection(section)
  if (normalized === "assessment") {
    if (!contextReady.value) return
    await loadAssessment()
    return
  }
  if (normalized === "prescriptions") {
    await loadPrescriptionPanel()
    return
  }
  if (normalized === "consent") {
    await loadConsentPanel()
    return
  }
  if (normalized === "review") {
    await ensureWorkspaceTab(tab || activeWorkspaceTab.value)
  }
}

function isSectionDegraded(section) {
  const labels = SECTION_CONTEXT_LABELS[section] || []
  const failed = data.value.context_errors || []
  return labels.some((label) => failed.includes(label))
}

async function load(context = props.context) {
  loading.value = true
  loadError.value = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.get_patient_derma_chart",
      args: {
        patient_id: context?.patient,
        appointment: context?.appointment,
        encounter: context?.encounter,
      },
    })
    data.value = response.message || {}
    syncSessionState()
	    if (selectedTemplate.value?.name && !procedureTemplates.value.some((row) => row.name === selectedTemplate.value.name)) {
	      clearTemplate()
	    }
	    if (activeProcedureName.value && !procedures.value.some((row) => row.name === activeProcedureName.value || row.clinical_procedure === activeProcedureName.value)) {
	      activeProcedureName.value = ""
	    }
	    ensureSelectedBodyTemplate()
    if (selectedMarkName.value && !marks.value.some((mark) => mark.name === selectedMarkName.value)) selectedMarkName.value = ""
    Object.keys(loadedTabs).forEach((key) => (loadedTabs[key] = false))
    await hydrateDermaSectionPreference()
    await ensureSectionData(activeSection.value, activeWorkspaceTab.value)
    // The Assessment tab decoration (tick + format toggle) must render on every
    // tab, so the assessment payload cannot stay lazy. loadAssessment guards on
    // loadedTabs and catches internally.
    if (contextReady.value) loadAssessment()
    if (encounter.value.name) await loadConsentPanel(true)
  } catch (error) {
    loadError.value = error?.message || __("Unable to load derma chart.")
  } finally {
    loading.value = false
  }
}

function syncSessionState() {
  sessionProvider.value = encounter.value.practitioner || appointment.value.practitioner || sessionProvider.value || ""
  sessionDate.value = encounter.value.encounter_date || appointment.value.appointment_date || sessionDate.value || ""
  sessionCategory.value = appointment.value.custom_appointment_category || appointment.value.appointment_type || encounter.value.appointment_type || sessionCategory.value || ""
  pastAppointment.value = appointment.value.custom_past_appointment || pastAppointment.value || ""
}

function refresh() {
  return load(props.context)
}

function uploadPhotos() {
  if (!patient.value.name || !encounter.value.name) {
    frappe.msgprint(__("A patient encounter is required before uploading photos."))
    return
  }
  if (!window.frappe?.ui?.FileUploader) {
    frappe.msgprint(__("File uploads are unavailable in this session. Reload the page and try again."))
    return
  }
  const uploaded = []
  const uploader = new frappe.ui.FileUploader({
    allow_multiple: true,
    restrictions: { allowed_file_types: ["image/*"] },
    on_success(file) {
      if (file?.file_url) uploaded.push(file.file_url)
    },
  })
  // FileUploader takes no close callback, so the batch is saved when its dialog hides.
  if (!uploader.dialog) {
    frappe.msgprint(__("File uploads are unavailable in this session. Reload the page and try again."))
    return
  }
  uploader.dialog.onhide = () => {
    if (!uploaded.length) return
    createPhotoSetFromImages(uploaded.splice(0))
  }
}

async function createPhotoSetFromImages(images) {
  const response = await frappe.call({
    method: "do_derma.api.create_photo_set",
    args: {
      values: {
        patient: patient.value.name,
	        appointment: appointment.value.name,
	        encounter: encounter.value.name,
	        clinical_procedure: activeProcedure.value?.name || "",
	        chart_mark: selectedMark.value?.name,
	        body_view: selectedMark.value?.body_view || selectedBodyTemplate.value?.title || "",
	        body_region: selectedMark.value?.body_region || selectedBodyTemplate.value?.template_type || "",
	        treatment_entry: activeProcedureTreatmentName.value || selectedMark.value?.treatment_entry || "",
	        notes: activeProcedure.value?.name ? `Linked to Clinical Procedure ${activeProcedure.value.name}` : selectedMark.value ? `Linked to chart mark ${selectedMark.value.name}` : "",
	        photos: images.map((image) => ({
	          image,
	          view: selectedMark.value?.body_view || selectedBodyTemplate.value?.title || "",
	          body_region: selectedMark.value?.body_region || selectedBodyTemplate.value?.template_type || "",
	          treatment_entry: activeProcedureTreatmentName.value || selectedMark.value?.treatment_entry || "",
	        })),
      },
    },
  })
  if (response.message?.name) {
    data.value = {
      ...data.value,
      photo_sets: [response.message, ...photoSets.value.filter((set) => set.name !== response.message.name)],
      marks: selectedMark.value?.name
        ? marks.value.map((mark) => (mark.name === selectedMark.value.name ? { ...mark, photo_set: response.message.name } : mark))
        : marks.value,
    }
	    frappe.show_alert({ message: __("Photos linked to chart"), indicator: "green" })
	    await refresh()
	  }
	}

async function retagPhoto({ photo, stage }) {
  if (!photo || !stage) return
  const response = await frappe.call({
    method: "do_derma.api.update_photo_stage",
    args: { photo, stage },
  })
  if (response.message?.name) {
    frappe.show_alert({ message: __("Photo stage updated"), indicator: "green" })
    await refresh()
  }
}

async function deletePhoto({ photo }) {
  if (!photo) return
  const confirmed = await new Promise((resolve) => {
    frappe.confirm(
      __("Delete this photo? This cannot be undone."),
      () => resolve(true),
      () => resolve(false)
    )
  })
  if (!confirmed) return
  await frappe.call({ method: "do_derma.api.delete_photo", args: { photo } })
  frappe.show_alert({ message: __("Photo deleted"), indicator: "green" })
  await refresh()
}

function selectTimelineVisit(visit) {
  if (!visit?.key) return
  selectedTimelineVisitKey.value = visit.key
}

function overlayTimelineVisit(visit = selectedTimelineVisit.value) {
  if (!visit?.key) return
  selectedTimelineVisitKey.value = visit.key
  chartOverlayMode.value = "history"
  const firstTemplate = (visit.marks || []).find((mark) => mark.body_template)?.body_template
  if (firstTemplate) {
    const template = bodyTemplates.value.find((row) => row.name === firstTemplate)
    if (template) loadBodyTemplate(template)
  }
  frappe.show_alert({ message: __("Previous visit marks overlaid"), indicator: "blue" })
}

function clearTimelineOverlay() {
  selectedTimelineVisitKey.value = ""
  chartOverlayMode.value = "today"
}

function openClinicalProcedure(procedure) {
  const name = procedure?.clinical_procedure || procedure?.name
  if (!name) return
  const row = procedures.value.find((item) => item.name === name || item.clinical_procedure === name) || procedure || {}
  frappe.msgprint({
    title: row.title || row.template_label || row.procedure_template || __("Clinical Procedure"),
    message: [
      row.name ? `<p><b>${__("Procedure")}:</b> ${escapeHtml(row.name)}</p>` : "",
      row.status ? `<p><b>${__("Status")}:</b> ${escapeHtml(row.status)}</p>` : "",
      row.derma_category ? `<p><b>${__("Category")}:</b> ${escapeHtml(row.derma_category)}</p>` : "",
      row.derma_detail_text || row.notes ? `<p>${escapeHtml(row.derma_detail_text || row.notes)}</p>` : "",
    ].filter(Boolean).join(""),
    indicator: "blue",
  })
}

function handleEncounterAlert(alert) {
  if (!alert) return
  if (alert.key === "consent") {
    setActiveSection("consent")
    return
  }
  if (alert.key === "photos") {
    uploadPhotos()
    return
  }
  if (alert.tab) {
    setActiveSection(alert.tab === "inventory" ? "review" : "photos")
  }
}

function openItem(itemCode) {
  if (itemCode) frappe.msgprint({ title: __("Inventory Item"), message: escapeHtml(itemCode), indicator: "blue" })
}

function markForItem(item) {
  const markName = item?.mark || item?.marks?.[0]
  return marks.value.find((row) => row.name === markName) || null
}

async function setItemResponse(item, status) {
  const mark = markForItem(item)
  if (!mark) {
    frappe.msgprint(__("This item is not linked to a current chart mark."))
    return
  }
  selectMark(mark)
  await updateSelectedMarkStatus(status)
}

async function createFollowupTask(item) {
  if (!item?.mark) return
  const response = await frappe.call({
    method: "do_derma.api.create_followup_todo",
    args: {
      payload: {
        mark: item.mark,
        title: item.title,
        description: `${item.title}\n${item.detail || ""}`.trim(),
        due_date: item.due_date,
        severity: item.severity,
      },
    },
  })
  if (response.message?.name) {
    frappe.show_alert({ message: __("Follow-up task created"), indicator: "green" })
    // Whether the new task downgrades the blocker is the server's call, so re-read it.
    await refresh()
  }
}

function openTodo(name) {
  if (name) frappe.msgprint({ title: __("Follow-up Task"), message: escapeHtml(name), indicator: "blue" })
}

function clearTemplate() {
  selectedTemplate.value = null
  activeProcedureName.value = ""
  selectedMarkName.value = ""
}

function formatNumber(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value || ""
  return Number.isInteger(parsed) ? String(parsed) : parsed.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")
}

function markLabel(mark) {
  const sequence = mark.sequence ? `#${mark.sequence}` : mark.name
  return `${sequence} ${mark.category || selectedTemplate.value?.custom_derma_category || __("Mark")}`
}

function markDetail(mark) {
  const bits = [
    mark.body_view || selectedBodyTemplate.value?.title,
    mark.dose ? `${formatNumber(mark.dose)} ${mark.dose_unit || ""}`.trim() : "",
    mark.product_name,
    mark.status,
  ].filter(Boolean)
  return bits.join(" · ") || mark.name
}

async function ensureWorkspaceTab(tab, force = false) {
  if (tab === "assessment") return loadAssessment(force)
  if (tab === "prescriptions") return loadPrescriptionPanel(force)
  if (tab === "anesthesia") return loadAnesthesiaPanel(force)
  if (tab === "consents") return loadConsentPanel(force)
}

async function createProcedure() {
  if (!hasSessionContext.value) {
    frappe.msgprint(__("This visit needs a Patient Encounter before a procedure can be created."))
    return
  }
  const options = procedureTemplates.value.map((row) => ({ label: row.template || row.name, value: row.name }))
  if (!options.length) {
    frappe.msgprint(__("No derma procedure templates are configured."))
    return
  }
  const dialog = new frappe.ui.Dialog({
    title: __("New Procedure"),
    fields: [
      { fieldname: "procedure_template", fieldtype: "Select", label: __("Procedure Template"), options, reqd: 1 },
      { fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
    ],
    primary_action_label: __("Create"),
    primary_action: async (values) => {
      dialog.hide()
      const template = procedureTemplates.value.find((row) => row.name === values.procedure_template)
      const response = await frappe.call({
        method: "do_derma.api.create_derma_chart_procedure",
        args: {
          payload: {
            patient: patient.value.name,
            appointment: appointment.value.name,
            encounter: encounter.value.name,
            procedure_template: values.procedure_template,
            category: template?.custom_derma_category,
            notes: values.notes,
          },
        },
      })
      const created = response.message?.clinical_procedure?.name
      if (created) {
        activeProcedureName.value = created
        frappe.show_alert({ message: __("Clinical Procedure created"), indicator: "green" })
      }
      await refresh()
    },
  })
  dialog.show()
  nameDialogControls(dialog)
}

async function copyMarksFromLastVisit() {
  const candidates = lastVisitMarks.value
  if (!candidates.length) {
    frappe.msgprint(__("This patient has no marks on an earlier visit."))
    return
  }
  const dialog = new frappe.ui.Dialog({
    title: __("Copy marks from last visit"),
    fields: [
      {
        fieldname: "marks",
        fieldtype: "MultiCheck",
        label: __("Marks"),
        columns: 1,
        options: candidates.map((mark) => ({
          label: `${markLabel(mark)} — ${markDetail(mark)}`,
          value: mark.name,
          checked: 1,
        })),
      },
    ],
    primary_action_label: __("Copy"),
    primary_action: async ({ marks: selected }) => {
      if (!selected?.length) {
        frappe.msgprint(__("Select at least one mark to copy."))
        return
      }
      dialog.hide()
      const response = await frappe.call({
        method: "do_derma.api.carry_forward_marks",
        args: {
          marks: selected,
          patient: patient.value.name,
          encounter: encounter.value.name,
          appointment: appointment.value.name,
        },
      })
      const copied = response.message?.marks?.length || 0
      frappe.show_alert({
        message: __("{0} mark(s) copied to this visit").replace("{0}", copied),
        indicator: copied ? "green" : "orange",
      })
      await refresh()
    },
  })
  dialog.show()
  nameDialogControls(dialog)
}

function upsertMark(mark) {
  const next = marks.value.filter((row) => row.name !== mark.name)
  next.push(mark)
  data.value = { ...data.value, marks: next }
}

function selectMark(mark) {
  if (!mark?.name) return
  selectTemplateForMark(mark)
  selectedMarkName.value = mark.name
}

function selectTemplateForMark(mark) {
  if (mark.procedure_template && mark.procedure_template !== selectedTemplate.value?.name) {
    const template = procedureTemplates.value.find((row) => row.name === mark.procedure_template)
    if (template) selectedTemplate.value = template
  }
}

async function updateSelectedMarkStatus(status) {
  if (!selectedMark.value) return
  const response = await frappe.call({
    method: "do_derma.api.save_chart_mark",
    args: {
      values: {
        name: selectedMark.value.name,
        patient: patient.value.name,
        appointment: appointment.value.name || selectedMark.value.appointment,
        encounter: encounter.value.name || selectedMark.value.encounter,
        status,
      },
    },
  })
  if (response.message?.name) {
    upsertMark(response.message)
    await refreshVisitSummary()
    frappe.show_alert({ message: __("Mark status updated"), indicator: "green" })
  }
}

async function refreshVisitSummary() {
  if (!encounter.value.name && !patient.value.name) return
  const response = await frappe.call({
    method: "do_derma.api.generate_visit_summary",
    args: { encounter: encounter.value.name, patient: patient.value.name },
  })
  data.value = { ...data.value, visit_summary: response.message || "" }
}

function openAnnotationHistory(annotation) {
  openAnnotationReviewDialog(annotation)
}

/** Output image beside its annotation details, with a print path. Shown after
 * every save and when a saved thumbnail is opened. `annotation_data` is
 * server-stored HTML whose values were escaped at generation time. */
function openAnnotationReviewDialog(annotation) {
  if (!annotation) return
  const preview = annotationPreview(annotation)
  const legend = annotation.annotation_data || ""
  const dialog = new frappe.ui.Dialog({
    title: `${annotationTemplateLabel(annotation)} · ${formatDate(annotation.creation || annotation.modified)}`,
    size: "extra-large",
    fields: [{ fieldname: "review", fieldtype: "HTML" }],
    primary_action_label: __("Print"),
    primary_action: () => printAnnotationReview(annotation),
    secondary_action_label: __("Close"),
    secondary_action: () => dialog.hide(),
    on_hide: () => dialog.$wrapper.remove(),
  })
  dialog.fields_dict.review.$wrapper.html(`
    <div class="derma-annotation-review" data-test="annotation-review">
      <div class="derma-annotation-review-image">
        ${preview ? `<img src="${escapeHtml(preview)}" alt="">` : `<p>${__("No preview image available.")}</p>`}
      </div>
      <div class="derma-annotation-review-data">
        ${legend || `<p class="panel-muted">${__("No annotation details.")}</p>`}
      </div>
    </div>
  `)
  dialog.show()
  nameDialogControls(dialog)
  dialog.$wrapper.find(".modal-dialog").css("max-width", "92vw")
}

function printAnnotationReview(annotation) {
  const preview = annotationPreview(annotation)
  const legend = annotation.annotation_data || ""
  const label = annotationTemplateLabel(annotation)
  const patientName = patient.value.patient_name || patient.value.name || ""
  // This document is hand-written HTML in a window with no autoescaping, so every
  // interpolated value is escaped here. `legend` is server-generated, escaped at generation.
  const title = escapeHtml([patientName, label].filter(Boolean).join(" - "))
  const printWindow = window.open("", "_blank")
  if (!printWindow) {
    frappe.show_alert({ message: __("Allow pop-ups to print the annotation."), indicator: "orange" })
    return
  }
  printWindow.document.write(`<!doctype html>
    <html><head><title>${title}</title></head>
    <body style="font-family:sans-serif;margin:24px;">
      <h2 style="margin:0 0 4px;">${escapeHtml(patientName)}</h2>
      <p style="margin:0 0 16px;color:#475569;font-size:13px;">${escapeHtml(annotationIdentityLine(annotation))}</p>
      ${preview ? `<img src="${escapeHtml(preview)}" style="max-width:100%;max-height:70vh;" alt="">` : ""}
      <div style="margin-top:16px;">${legend}</div>
    </body></html>`)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => printWindow.print(), 350)
}

function annotationPreview(annotation) {
  return annotation?.image || annotation?.preview_image || annotation?.annotation_image || annotation?.file_url || ""
}

/** Never the docname: a hash tells a clinician nothing, and "Drawing" is honest. */
function annotationTemplateLabel(annotation) {
  return (
    annotation?.custom_derma_body_template_title ||
    annotation?.annotation_template ||
    annotation?.title ||
    __("Drawing")
  )
}

/** Who and when, for a sheet that ends up in a paper file. Escaped by the caller. */
function annotationIdentityLine(annotation) {
  return [
    patient.value.name ? `${__("MRN")}: ${patient.value.name}` : "",
    annotationTemplateLabel(annotation),
    formatDate(annotation?.creation || annotation?.modified),
    currentPractitionerName.value,
    encounter.value.name,
  ]
    .filter(Boolean)
    .join(" · ")
}

function loadBodyTemplate(template = selectedBodyTemplate.value) {
  if (!template) return
  selectedBodyTemplate.value = template
}

function openAnnotationStudio(anchor = {}) {
  if (!encounter.value.name) {
    frappe.msgprint(__("A Patient Encounter is required before saving annotation."))
    return
  }
  const clinicalProcedure = anchor.clinicalProcedure || ""
  openDermaAnnotationStudio({
    context: {
      patient: patient.value.name,
      patientName: patient.value.patient_name || patient.value.name,
      patientSex: patient.value.sex || "",
      encounter: encounter.value.name,
      appointment: appointment.value.name || props.context?.appointment,
      clinicalProcedure,
      procedureLabel: anchor.procedureLabel || "",
      // The Clinical Procedure Template behind the anchor: the studio filters its
      // procedures drawer to that template's category and titles the header with it.
      procedureTemplate: anchor.procedureTemplate || "",
    },
    bodyTemplates: bodyTemplates.value,
    procedureTemplates: procedureTemplates.value,
    // `annotation: null` is an explicit "start a fresh drawing" - only an
    // absent key falls back to resuming the anchor's newest one.
    annotation:
      anchor.annotation !== undefined ? anchor.annotation : latestAnnotationForAnchor(clinicalProcedure),
    marks: marksForAnchor(clinicalProcedure),
    onSaved: async (saved) => {
      await refresh()
      openAnnotationReviewDialog(saved)
    },
    // Discarding deletes the marks and photos the studio placed, so the tabs behind it are stale.
    onClose: async (result) => {
      if (result?.marksChanged || result?.photosChanged) await refresh()
    },
  })
}

/**
 * Only ever resume a drawing that belongs to this anchor. `encounter_annotations` falls back to
 * the patient's previous visits when this encounter has none (api.py `_load_derma_annotation_context`),
 * which is what the Previous Annotations strip wants and what resume must never accept - saving
 * with that annotation_name would overwrite the earlier visit's drawing.
 */
function latestAnnotationForAnchor(clinicalProcedure) {
  if (clinicalProcedure) return (procedureAnnotations.value[clinicalProcedure] || [])[0] || null
  return encounterAnnotations.value.find((row) => row.source_name === encounter.value.name) || null
}

/**
 * Same guard, applied per row: the strip also lists earlier visits' drawings, and resuming one
 * would overwrite it on save. Those stay review-only.
 */
function isResumableAnnotation(annotation) {
  return Boolean(annotation?.source_name) && annotation.source_name === encounter.value.name
}

/**
 * A mark promoted to a procedure belongs on that procedure's canvas only. Rendering it
 * on the consultation canvas would re-point its `annotation` link to the consultation
 * drawing on the next save (api.py _sync_chart_marks_for_annotation, stamp backlink).
 */
function marksForAnchor(clinicalProcedure) {
  if (!clinicalProcedure) return marks.value.filter((mark) => !mark.clinical_procedure)
  return marks.value.filter((mark) => mark.clinical_procedure === clinicalProcedure)
}

function annotateProcedure(row) {
  const clinicalProcedure = row?.clinical_procedure || row?.name || ""
  if (!clinicalProcedure || String(clinicalProcedure).startsWith("local-")) {
    frappe.msgprint(__("Save the procedure before annotating it."))
    return
  }
  const procedureTemplate = row.procedure_template || ""
  const procedureLabel = row.display_name || procedureTemplate || clinicalProcedure
  const anchor = { clinicalProcedure, procedureLabel, procedureTemplate }
  const existing = procedureAnnotations.value[clinicalProcedure] || []
  if (!existing.length) {
    openAnnotationStudio({ ...anchor, annotation: null })
    return
  }
  openProcedureAnnotationPicker({ ...anchor, annotations: existing })
}

async function deleteAnnotation(annotation, doctype, docname) {
  frappe.confirm(__("Delete this drawing permanently?"), async () => {
    try {
      await frappe.call({
        method: "do_derma.api.delete_derma_annotation",
        args: { annotation_name: annotation.name, doctype, docname },
      })
      await refresh()
    } catch (error) {
      frappe.show_alert({ message: error.message || __("Unable to delete annotation"), indicator: "red" })
    }
  })
}

/** A procedure can hold several drawings: resume one deliberately, or start fresh. */
function openProcedureAnnotationPicker({ clinicalProcedure, procedureLabel, procedureTemplate, annotations }) {
  const anchor = { clinicalProcedure, procedureLabel, procedureTemplate }
  const dialog = new frappe.ui.Dialog({
    title: `${__("Annotations")} · ${procedureLabel}`,
    size: "large",
    fields: [{ fieldname: "annotation_list", fieldtype: "HTML" }],
    primary_action_label: __("New Annotation"),
    primary_action: () => {
      dialog.hide()
      openAnnotationStudio({ ...anchor, annotation: null })
    },
    // Frappe keeps hidden modals in the DOM; a re-opened picker would stack a
    // second copy of every data-test hook.
    on_hide: () => dialog.$wrapper.remove(),
  })
  const cards = annotations
    .map((annotation, index) => {
      const preview = annotationPreview(annotation)
      return `
        <div class="derma-annotation-pick">
          <div class="derma-annotation-pick-row">
            <span class="derma-annotation-pick-preview">
              ${preview ? `<img src="${escapeHtml(preview)}" alt="" loading="lazy">` : `<span>${__("No preview")}</span>`}
            </span>
            <span class="derma-annotation-pick-meta">
              <b>${escapeHtml(annotationTemplateLabel(annotation))}</b>
              <small>${escapeHtml(formatDate(annotation.creation || annotation.modified))}</small>
            </span>
            <button type="button" class="btn btn-sm btn-default" data-test="annotation-picker-edit" data-index="${index}">
              ${__("Edit")}
            </button>
            ${!isEncounterLocked.value ? `<button type="button" class="btn btn-sm btn-danger" data-test="annotation-picker-delete" data-delete-index="${index}">${__("Delete")}</button>` : ""}
          </div>
          ${annotation.annotation_data ? `<div class="derma-annotation-pick-data">${annotation.annotation_data}</div>` : ""}
        </div>
      `
    })
    .join("")
  const $wrapper = dialog.fields_dict.annotation_list.$wrapper
  $wrapper.html(`<div class="derma-annotation-pick-list" data-test="annotation-picker">${cards}</div>`)
  $wrapper.find('[data-test="annotation-picker-edit"]').on("click", (event) => {
    const index = Number(event.currentTarget.getAttribute("data-index"))
    dialog.hide()
    openAnnotationStudio({ ...anchor, annotation: annotations[index] || null })
  })
  $wrapper.find('[data-test="annotation-picker-delete"]').on("click", (event) => {
    const index = Number(event.currentTarget.getAttribute("data-delete-index"))
    const target = annotations[index]
    frappe.confirm(__("Delete this drawing permanently?"), async () => {
      try {
        await frappe.call({
          method: "do_derma.api.delete_derma_annotation",
          args: { annotation_name: target.name, doctype: "Clinical Procedure", docname: clinicalProcedure },
        })
        dialog.hide()
        await refresh()
      } catch (error) {
        frappe.show_alert({ message: error.message || __("Unable to delete annotation"), indicator: "red" })
      }
    })
  })
  dialog.show()
  nameDialogControls(dialog)
}

async function loadAssessment(force = false) {
  if (!force && loadedTabs.assessment) return
  assessmentPanel.loading = true
  assessmentPanel.error = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_assessment", args: contextArgs() })
    applyAssessmentResponse(response.message || {})
    loadedTabs.assessment = true
  } catch (error) {
    assessmentPanel.error = error?.message || __("Unable to load assessment.")
  } finally {
    assessmentPanel.loading = false
  }
}

function applyAssessmentResponse(message) {
  assessmentPanel.encounter = message.encounter || ""
  assessmentPanel.docstatus = message.docstatus
  assessmentPanel.mode = message.mode || "Structured"
  assessmentPanel.isFilled = Boolean(message.is_filled)
  assessmentPanel.availableModes = message.available_modes || ["Structured"]
  assessmentPanel.layout = message.layout || []
  assessmentPanel.values = message.values || {}
  assessmentPanel.soapLayout = message.soap_layout || []
  assessmentPanel.soapValues = message.soap_values || {}
  assessmentPanel.contextValues = message.context_values || {}
  assessmentPanel.editing = false
}

async function saveAssessment({ payload, mode }) {
  assessmentPanel.saving = true
  try {
    const response = await frappe.call({
      method: "do_derma.api.set_derma_assessment",
      args: { ...contextArgs(), payload, mode },
    })
    applyAssessmentResponse(response.message || {})
    frappe.show_alert({ message: __("Assessment saved"), indicator: "green" })
  } finally {
    assessmentPanel.saving = false
  }
}

// Only the active tab offers the switch: an inactive Assessment tab keeps its
// plain hint, so a navigation click can never land on a format segment.
const assessmentModeToggleVisible = computed(
  () =>
    activeSection.value === "assessment" &&
    Boolean(assessmentPanel.encounter) &&
    (assessmentPanel.availableModes || []).length > 1
)

const assessmentModeLocked = computed(() => Number(assessmentPanel.docstatus ?? 0) !== 0)

const ASSESSMENT_MODE_SHORT_LABELS = { SOAP: "SOAP", Structured: "Structured" }

function assessmentModeShortLabel(mode) {
  return __(ASSESSMENT_MODE_SHORT_LABELS[mode] || mode)
}

function assessmentValueHasContent(value) {
  if (value === null || value === undefined) return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === "string") return Boolean(value.trim())
  return true
}

function assessmentModeHasContent(mode) {
  const source = mode === "SOAP" ? assessmentPanel.soapValues : assessmentPanel.values
  return Object.values(source || {}).some(assessmentValueHasContent)
}

function requestAssessmentModeChange(target) {
  if (assessmentModeLocked.value || assessmentPanel.saving || assessmentPanel.loading) return
  if (!target || target === assessmentPanel.mode) return
  // Leaving an empty format is consequence-free; leaving a written one gets
  // one deliberate confirmation. Nothing is deleted either way (stamp_mode).
  if (!assessmentModeHasContent(assessmentPanel.mode) || !window.frappe?.confirm) {
    setAssessmentMode(target)
    return
  }
  const label = target === "SOAP" ? __("SOAP Note") : __("Structured Assessment")
  window.frappe.confirm(
    __("Switch this visit to {0}? Nothing you have written is deleted.").replace("{0}", label),
    () => setAssessmentMode(target)
  )
}

async function setAssessmentMode(mode) {
  assessmentPanel.saving = true
  try {
    const response = await frappe.call({
      method: "do_derma.api.set_derma_assessment_mode",
      args: { ...contextArgs(), mode },
    })
    applyAssessmentResponse(response.message || {})
    assessmentPanel.editing = true
  } catch (error) {
    assessmentPanel.error = error?.message || __("Unable to change the documentation format.")
  } finally {
    assessmentPanel.saving = false
  }
}

async function loadPrescriptionPanel(force = false) {
  if (!force && loadedTabs.prescriptions) return
  prescriptionPanel.loading = true
  prescriptionPanel.error = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_prescriptions", args: contextArgs() })
    prescriptionPanel.encounter = response.message?.encounter || encounter.value.name || ""
    prescriptionPanel.rows = response.message?.drug_prescription || []
    loadedTabs.prescriptions = true
  } catch (error) {
    prescriptionPanel.error = error?.message || __("Unable to load prescriptions.")
  } finally {
    prescriptionPanel.loading = false
  }
}

async function savePrescriptionPanel(rows) {
  prescriptionPanel.saving = true
  try {
    const response = await frappe.call({ method: "do_derma.api.set_derma_prescriptions", args: { ...contextArgs(), payload: rows } })
    prescriptionPanel.encounter = response.message?.encounter || prescriptionPanel.encounter
    prescriptionPanel.rows = response.message?.drug_prescription || []
    frappe.show_alert({ message: __("Prescriptions saved"), indicator: "green" })
  } finally {
    prescriptionPanel.saving = false
  }
}

async function loadAnesthesiaPanel(force = false) {
  if (!force && loadedTabs.anesthesia) return
  anesthesiaPanel.loading = true
  anesthesiaPanel.error = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_anesthesia", args: contextArgs() })
    anesthesiaPanel.encounter = response.message?.encounter || encounter.value.name || ""
    anesthesiaPanel.rows = response.message?.anesthesia || []
    loadedTabs.anesthesia = true
  } catch (error) {
    anesthesiaPanel.error = error?.message || __("Unable to load anesthesia.")
  } finally {
    anesthesiaPanel.loading = false
  }
}

async function loadConsentPanel(force = false) {
  if (!force && loadedTabs.consents) return
  consentPanel.loading = true
  consentPanel.error = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_consents", args: contextArgs() })
    consentPanel.encounter = encounter.value.name || ""
    consentPanel.consents = response.message || []
    loadedTabs.consents = true
  } catch (error) {
    consentPanel.error = error?.message || __("Unable to load consents.")
  } finally {
    consentPanel.loading = false
  }
}

async function requestConsentPreview(payload) {
  const procedureItems = buildConsentProcedureItems(payload?.procedure_selection)
  consentPanel.previewLoading = true
  consentPanel.error = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.render_derma_consent_preview",
      args: { payload: { ...payload, ...contextArgs(), procedure_items: procedureItems } },
    })
    const raw = response.message?.rendered_html || ""
    consentPanel.previewHtml = frappe?.utils?.unescape_html ? frappe.utils.unescape_html(raw) : raw
  } catch (error) {
    consentPanel.error = error?.message || __("Unable to render consent preview.")
  } finally {
    consentPanel.previewLoading = false
  }
}

async function createConsentFromPanel(payload) {
  const procedureItems = buildConsentProcedureItems(payload?.procedure_selection)
  consentPanel.saving = true
  consentPanel.error = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.create_derma_consent",
      args: { payload: { ...payload, ...contextArgs(), procedure_items: procedureItems } },
    })
    if (response.message?.name) openSignedConsent({ name: response.message.name })
    loadedTabs.consents = false
    await loadConsentPanel(true)
    consentPanel.previewHtml = ""
    consentPanel.resetKey += 1
    frappe.show_alert({ message: __("Consent created."), indicator: "green" })
  } catch (error) {
    consentPanel.error = error?.message || __("Unable to create consent.")
  } finally {
    consentPanel.saving = false
  }
}

function buildConsentProcedureItems(selection = []) {
  const selected = Array.isArray(selection) ? selection : []
  return consentProcedureOptions.value
    .filter((row) => selected.includes(row.value))
    .map((row) => ({
      clinical_procedure: row.clinical_procedure || row.value,
      procedure_template: row.procedure_template || null,
      display_name: row.display_name || row.label || row.value,
    }))
}

function unsupportedRemoteConsentMessage() {
  frappe.msgprint({
    title: __("Remote Consent"),
    message: __("Remote WhatsApp consent signing is not configured for the derma chart yet. Create the consent here, then send it from the standard consent workflow if needed."),
    indicator: "orange",
  })
}

function sendConsentViaWhatsApp() {
  unsupportedRemoteConsentMessage()
}

function resendConsentViaWhatsApp() {
  unsupportedRemoteConsentMessage()
}

function cancelRemoteConsent() {
  unsupportedRemoteConsentMessage()
}

async function openSignedConsent(row) {
  const name = row?.name || row
  if (!name) return
  const dialog = new frappe.ui.Dialog({
    title: row?.consent_form_template || __("Consent Form"),
    size: "large",
    fields: [{ fieldname: "body", fieldtype: "HTML" }],
  })
  dialog.show()
  nameDialogControls(dialog)
  dialog.fields_dict.body.$wrapper.html(`<p>${__("Loading...")}</p>`)
  try {
    const response = await frappe.call({
      method: "do_derma.api.get_derma_consent_html",
      args: { name },
    })
    const result = response.message || {}
    const meta = escapeHtml(consentMetaText({ ...row, ...result }))
    dialog.fields_dict.body.$wrapper.html(
      `<p class="text-muted">${meta}</p><div class="consent-rendered-html">${result.rendered_html || __("No rendered content available.")}</div>`
    )
  } catch (err) {
    dialog.fields_dict.body.$wrapper.html(
      `<p class="text-danger">${escapeHtml(err?.message || __("Unable to load this consent."))}</p>`
    )
  }
}

function consentMetaText(row = {}) {
  return [row.status, row.signed_by, row.signed_on].filter(Boolean).join(" · ")
}

function blockerListHtml(blockers) {
  return blockers
    .map((item) => `<li><b>${escapeHtml(item.title)}</b>: ${escapeHtml(item.detail || item.location || "")}</li>`)
    .join("")
}

function askToProceedPastBlockers(blockers) {
  return new Promise((resolve) => {
    frappe.confirm(
      `<p>${__("This session has {0} unresolved blocker(s).").replace("{0}", blockers.length)}</p><ul>${blockerListHtml(blockers)}</ul><p>${__("Complete it anyway?")}</p>`,
      () => resolve(true),
      () => resolve(false),
    )
  })
}

function askForOverrideReason(blockers) {
  return new Promise((resolve) => {
    const dialog = new frappe.ui.Dialog({
      title: __("Complete With Unresolved Blockers"),
      fields: [
        {
          fieldtype: "HTML",
          options: `<p>${__("These blockers must be recorded before this session can be completed.")}</p><ul>${blockerListHtml(blockers)}</ul>`,
        },
        {
          fieldname: "override_reason",
          fieldtype: "Small Text",
          label: __("Reason"),
          reqd: 1,
        },
      ],
      primary_action_label: __("Complete Session"),
      primary_action: ({ override_reason }) => {
        const reason = (override_reason || "").trim()
        if (!reason) return
        // Resolve before hiding: onhide is the cancel path and would answer first.
        resolve(reason)
        dialog.hide()
      },
    })
    dialog.$wrapper.attr("data-test", "readiness-override-dialog")
    dialog.onhide = () => resolve(null)
    dialog.show()
    nameDialogControls(dialog)
  })
}

/** The reason to complete with, or null when the clinician backed out. */
async function overrideReasonForCompletion() {
  const blockers = readinessBlockers.value
  if (!blockers.length) return ""
  if (readinessEnforcement.value === ENFORCEMENT_BLOCK) return askForOverrideReason(blockers)
  return (await askToProceedPastBlockers(blockers)) ? "" : null
}

async function syncBillablesForSession() {
  if (!hasSessionContext.value || syncingBillables.value) return
  syncingBillables.value = true
  try {
    const response = await frappe.call({
      method: "do_derma.api.sync_derma_billables",
      args: contextArgs(),
    })
    const result = response.message || {}
    frappe.show_alert({
      message: __("Synced {0} billing item(s) to the appointment.").replace("{0}", result.added ?? 0),
      indicator: "green",
    })
    await refresh()
  } catch (err) {
    frappe.msgprint({
      title: __("Sync Failed"),
      message: err?.message || __("Unable to sync billables for this session."),
      indicator: "red",
    })
  } finally {
    syncingBillables.value = false
  }
}

async function completeSession() {
  if (!encounter.value.name || completionPending.value) return
  // Claimed before the dialog, not after it: a second click while the clinician is
  // typing a reason would otherwise open a second dialog and complete twice. The button
  // only says "Completing..." once the confirm is answered - while the dialog is open
  // nothing is running yet.
  completionPending.value = true
  try {
    const overrideReason = await overrideReasonForCompletion()
    if (overrideReason === null) return
    completingSession.value = true
    await submitSessionCompletion(overrideReason)
  } finally {
    completingSession.value = false
    completionPending.value = false
  }
}

async function submitSessionCompletion(overrideReason) {
  try {
    const response = await frappe.call({
      method: "do_derma.api.complete_derma_session",
      args: { ...contextArgs(), override_reason: overrideReason },
    })
    const result = response.message || {}
    frappe.show_alert({
      message: result.encounter_submitted
        ? __("Encounter completed and submitted.")
        : __("Session billing synced."),
      indicator: "green",
    })
  } catch (err) {
    frappe.msgprint({
      title: __("Unable to Complete Session"),
      message: err?.message || __("Something went wrong while completing this session."),
      indicator: "red",
    })
  }
  // Either way the server has the last word on readiness, so re-read it: a refusal
  // means this chart's copy was stale, and the next attempt must prompt on the new one.
  await refresh()
}

function contextArgs() {
  return {
    encounter: encounter.value.name || props.context?.encounter,
    appointment: appointment.value.name || props.context?.appointment,
    patient: patient.value.name || props.context?.patient,
  }
}

function ensureSelectedBodyTemplate(force = false) {
  if (!bodyTemplates.value.length) {
    selectedBodyTemplate.value = null
    return
  }
  const stillAvailable = selectedBodyTemplate.value?.name && bodyTemplates.value.some((row) => row.name === selectedBodyTemplate.value.name)
  if (!force && stillAvailable) return

  const allowed = allowedBodyTemplates(selectedTemplate.value)
  const isAllowed = (row) => allowed.includes(String(row.name).toLowerCase())
  const gender = preferredTemplateGender()
  const genderMatch = (row) => row.gender === gender
  const categoryDefault = selectedTemplate.value?.derma_category_defaults?.default_body_template || categorySettings(selectedTemplate.value?.custom_derma_category)?.default_body_template
  selectedBodyTemplate.value =
    bodyTemplates.value.find((row) => row.name === categoryDefault && genderMatch(row)) ||
    bodyTemplates.value.find((row) => row.name === categoryDefault) ||
    bodyTemplates.value.find((row) => isAllowed(row) && genderMatch(row)) ||
    bodyTemplates.value.find((row) => isAllowed(row)) ||
    preferredBodyTemplate("Body") ||
    preferredBodyTemplate("Face") ||
    bodyTemplates.value.find((row) => row.image && genderMatch(row)) ||
    bodyTemplates.value.find((row) => row.image) ||
    bodyTemplates.value[0] ||
    null
}

function preferredBodyTemplate(templateType = "Body") {
  const gender = preferredTemplateGender()
  const type = String(templateType || "").toLowerCase()
  const rows = bodyTemplates.value.filter((row) => row.image && String(row.template_type || "").toLowerCase() === type)
  if (!rows.length) return null
  const frontMatch = (row) => /front/i.test([row.name, row.title, row.view_key].filter(Boolean).join(" "))
  return (
    rows.find((row) => row.gender === gender && frontMatch(row)) ||
    rows.find((row) => row.gender === gender) ||
    rows.find(frontMatch) ||
    rows[0]
  )
}

function categorySettings(category) {
  if (!category) return null
  return categories.value.find((row) => row.name === category || row.title === category) || null
}

function normalizeBodyTemplate(template) {
  return {
    ...template,
    gender: template.gender || preferredTemplateGender(),
    is_standard: Number(template.is_standard ?? 1),
    image: template.image || "",
    regions: normalizeTemplateRegions(template.regions),
    default_for_categories: template.default_for_categories || [],
  }
}

function normalizeTemplateRegions(regions) {
  if (Array.isArray(regions)) return regions
  if (!regions) return []
  try {
    const parsed = JSON.parse(regions)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function preferredTemplateGender() {
  const sex = String(patient.value.sex || "").toLowerCase()
  if (sex.startsWith("female")) return "Female"
  if (sex.startsWith("male")) return "Male"
  return "Female"
}

function normalizeProcedureRow(row) {
  const date = row.start_date || row.procedure_date || row.creation?.slice?.(0, 10) || ""
  return {
    ...row,
    clinical_procedure: row.name,
    display_name: procedureDisplayName(row),
    procedure: procedureDisplayName(row),
    procedure_date: date,
    date,
    tooth: row.derma_category || row.custom_derma_category || row.procedure_template || "Derma",
    // derma_detail_text is a computed summary, never a note: pre-filling it here
    // once let Save Note write that summary into the procedure note. The derma
    // note (editable) outranks the core notes field (set_only_once, legacy).
    notes: row.custom_derma_notes || row.notes || "",
    note_sentence_template:
      procedureTemplates.value.find((template) => template.name === row.procedure_template)
        ?.custom_derma_note_template || "",
    price_list: row.custom_derma_price_list || "",
    price_override: row.custom_derma_price_override ?? null,
    no_charge: Boolean(row.custom_derma_no_charge),
    price_override_reason: row.custom_derma_price_override_reason || "",
    surface_profile: "none",
    render_style: "derma",
  }
}

function rowTimestamp(row) {
  const value = row.procedure_date || row.start_date || row.date
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatDate(value) {
  if (!value) return ""
  return window.frappe?.datetime?.str_to_user?.(value) || String(value).slice(0, 10)
}

</script>

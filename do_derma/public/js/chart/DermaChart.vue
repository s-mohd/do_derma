<template>
  <div class="dental-chart-page derma-chart-page">
    <div v-if="!contextReady" class="chart-empty-state">
      <h3>{{ __("Select a patient") }}</h3>
      <p>{{ __("Use the health sidebar to select a patient, then open Derma Chart.") }}</p>
    </div>

    <div v-else-if="loading && !patient.name" class="chart-loading-skeleton" role="status" :aria-label="__('Loading derma chart')">
      <div class="skeleton-block skeleton-header"></div>
      <div class="skeleton-block skeleton-tabs"></div>
      <div class="skeleton-grid">
        <div class="skeleton-block skeleton-main"></div>
        <div class="skeleton-block skeleton-side"></div>
      </div>
    </div>

    <div v-else-if="loadError && !patient.name" class="chart-error-state">
      <h3>{{ __("Unable to load Derma Chart") }}</h3>
      <p>{{ loadError }}</p>
      <button type="button" class="primary" @click="refresh">{{ __("Retry") }}</button>
    </div>

    <template v-else>
      <div v-if="loadError" class="chart-error-banner" role="alert">
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
        @refresh="refresh"
        @complete="completeSession"
      />

      <section class="derma-section-bar">
        <nav class="derma-section-tabs" :aria-label="__('Derma encounter sections')">
          <button
            v-for="section in SECTION_TABS"
            :key="section.key"
            type="button"
            :class="{ active: activeSection === section.key }"
            @click="setActiveSection(section.key)"
          >
            <span>{{ section.label }}</span>
            <small>{{ section.hint }}</small>
          </button>
        </nav>
        <div class="derma-section-actions">
          <button type="button" class="ghost" @click="openAnnotationStudio">
            <span aria-hidden="true">✎</span>
            {{ __("Annotate") }}
          </button>
          <button type="button" class="ghost" @click="uploadPhotos('Visit')">
            <span aria-hidden="true">▧</span>
            {{ __("Upload Photo") }}
          </button>
        </div>
      </section>

      <section class="derma-console-grid">
        <main class="derma-console-main">
          <template v-if="activeSection === 'clinical'">
            <div class="clinical-notes-grid">
              <section class="clinical-soap-stack">
                <AssessmentPanel
                  :layout="assessmentPanel.layout"
                  :values="assessmentPanel.values"
                  :context-values="assessmentPanel.contextValues"
                  :loading="assessmentPanel.loading"
                  :saving="assessmentPanel.saving"
                  :error="assessmentPanel.error"
                  :has-encounter="Boolean(assessmentPanel.encounter)"
                  :encounter-name="assessmentPanel.encounter"
                  :docstatus="assessmentPanel.docstatus"
                  :edit-mode="assessmentPanel.editing"
                  :allow-on-submit-fields="assessmentEditableOnSubmitFields"
                  @request-edit="assessmentPanel.editing = true"
                  @save="saveAssessment"
                  @refresh="() => loadAssessment(true)"
                />
                <section class="chart-annotation-history encounter-annotation-history">
                  <header>
                    <div>
                      <strong>{{ __("Previous Annotations") }}</strong>
                      <small>{{ annotations.length ? __("{0} saved drawing(s)").replace("{0}", annotations.length) : __("No saved drawings yet") }}</small>
                    </div>
                    <button type="button" class="ghost small" @click="openAnnotationStudio">{{ __("Annotate") }}</button>
                  </header>
                  <div v-if="annotations.length" class="chart-annotation-list">
                    <button
                      v-for="annotation in annotations.slice(0, 8)"
                      :key="annotation.name"
                      type="button"
                      @click="openAnnotationHistory(annotation)"
                    >
                      <span class="chart-annotation-preview">
                        <img v-if="annotationPreview(annotation)" :src="annotationPreview(annotation)" :alt="annotation.name" loading="lazy" />
                        <span v-else>{{ __("No preview") }}</span>
                      </span>
                      <b>{{ annotationTemplateLabel(annotation) }}</b>
                      <small>{{ formatDate(annotation.creation || annotation.modified) }}</small>
                    </button>
                  </div>
                  <p v-else class="panel-muted">{{ __("Saved encounter drawings will appear here.") }}</p>
                </section>
              </section>
            </div>
          </template>

          <template v-else-if="activeSection === 'photos'">
            <section class="section-panel photo-section-panel">
              <header>
                <div>
                  <strong>{{ __("Photos & Comparison") }}</strong>
                  <small>{{ activeProcedure ? __("Photos will link to the active procedure.") : __("Photos will save as encounter evidence.") }}</small>
                </div>
                <button type="button" class="primary small" @click="uploadPhotos(activeProcedure ? 'Procedure' : 'Visit')">{{ __("Upload Photo") }}</button>
              </header>
              <DermaEvidencePanel
                :active-procedure="activeProcedure"
                :annotation-count="currentAnnotationHistory.length"
                :photo-set-count="relevantPhotoSets.length"
                :summary="procedureArtifactText"
                :photo-summary="photoPanelSummary"
                :photo-compare="photoCompare"
                :photo-sets="relevantPhotoSets"
                :selected-photo-set-name="selectedPhotoSetName"
                :allow-upload="true"
                @upload="uploadPhotos(activeProcedure ? 'Procedure' : 'Visit')"
                @select-photo-set="(name) => (selectedPhotoSetName = name)"
              />
            </section>
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
            @refresh="() => loadConsentPanel(true)"
            @request-preview="requestConsentPreview"
            @create="createConsentFromPanel"
            @send-whatsapp="sendConsentViaWhatsApp"
            @open-consent="openSignedConsent"
            @resend-consent="resendConsentViaWhatsApp"
            @cancel-consent="cancelRemoteConsent"
          />

          <section v-else class="workspace-shell review-shell">
        <div class="workspace-tabview">
          <div class="workspace-content review-section-stack">
            <ProcedurePanel
              :status-pills="STATUS_PILLS"
              :groups="groupedProcedures"
              :total-count="procedureCount"
              :doctor-name="currentPractitionerName"
              :price-lists="priceLists"
              :default-price-list="defaultPriceList"
              :sync-disabled="!hasSessionContext || syncingBillables"
              :complete-disabled="!hasSessionContext || completingSession"
              :anesthesia-recorded="anesthesiaRecorded"
              :read-only="isEncounterLocked"
              @refresh="refresh"
              @activate-procedure="activateProcedure"
              @sync-billables="syncBillablesForSession"
              @complete-session="completeSession"
            />

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
                    <span v-if="visit.preview_image" class="timeline-preview">
                      <img :src="visit.preview_image" :alt="visit.date || visit.key" loading="lazy" />
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
                      <button type="button" class="ghost small" @click="compareTimelineVisit(selectedTimelineVisit)">
                        {{ __("Compare with Today") }}
                      </button>
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
                      <img v-if="set.preview_image" :src="set.preview_image" :alt="set.set_type || set.name" loading="lazy" />
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

            <section class="derma-compare-workspace">
              <header>
                <div>
                  <strong>{{ __("Before / After Compare") }}</strong>
                  <small>{{ comparePhotoOptions.length ? __("{0} image(s) available").replace("{0}", comparePhotoOptions.length) : __("Upload or link photos to compare progress") }}</small>
                </div>
                <div class="compare-actions">
                  <button type="button" class="ghost small" @click="swapCompareImages" :disabled="!compareLeftImage || !compareRightImage">
                    {{ __("Swap") }}
                  </button>
                  <button type="button" class="ghost small" @click="uploadPhotos('Visit')">
                    {{ __("Upload Today") }}
                  </button>
                </div>
              </header>

              <div class="compare-filter-row">
                <label>
                  <span>{{ __("Category") }}</span>
                  <select v-model="compareCategoryFilter">
                    <option value="all">{{ __("All") }}</option>
                    <option v-for="category in compareCategories" :key="category" :value="category">{{ category }}</option>
                  </select>
                </label>
                <label>
                  <span>{{ __("Photo Type") }}</span>
                  <select v-model="compareTypeFilter">
                    <option value="all">{{ __("All") }}</option>
                    <option v-for="type in comparePhotoTypes" :key="type" :value="type">{{ type }}</option>
                  </select>
                </label>
                <label>
                  <span>{{ __("Left") }}</span>
                  <select v-model="compareLeftId">
                    <option value="">{{ __("Auto") }}</option>
                    <option v-for="photo in filteredComparePhotoOptions" :key="photo.id" :value="photo.id">{{ photo.label }}</option>
                  </select>
                </label>
                <label>
                  <span>{{ __("Right") }}</span>
                  <select v-model="compareRightId">
                    <option value="">{{ __("Auto") }}</option>
                    <option v-for="photo in filteredComparePhotoOptions" :key="photo.id" :value="photo.id">{{ photo.label }}</option>
                  </select>
                </label>
              </div>

              <div class="compare-viewer">
                <figure>
                  <div class="compare-image-frame">
                    <img v-if="compareLeftImage" :src="compareLeftImage.image" :alt="compareLeftImage.label" />
                    <span v-else>{{ __("No previous image") }}</span>
                  </div>
                  <figcaption>
                    <strong>{{ compareLeftImage?.label || __("Previous") }}</strong>
                    <small>{{ compareLeftImage?.meta || __("Select a previous/before photo") }}</small>
                  </figcaption>
                </figure>

                <figure>
                  <div class="compare-image-frame">
                    <img v-if="compareRightImage" :src="compareRightImage.image" :alt="compareRightImage.label" />
                    <span v-else>{{ __("No current image") }}</span>
                  </div>
                  <figcaption>
                    <strong>{{ compareRightImage?.label || __("Today") }}</strong>
                    <small>{{ compareRightImage?.meta || __("Select a current/after photo") }}</small>
                  </figcaption>
                </figure>
              </div>

              <div class="compare-bottom-row">
                <section class="compare-response-panel">
                  <header>
                    <strong>{{ __("Clinical Response") }}</strong>
                    <small>{{ selectedMark ? markLabel(selectedMark) : __("Select a chart mark to save response") }}</small>
                  </header>
                  <div class="response-chip-row">
                    <button
                      v-for="status in COMPARE_RESPONSE_STATUSES"
                      :key="status"
                      type="button"
                      :class="{ active: compareResponseStatus === status || selectedMark?.status === status }"
                      @click="setCompareResponse(status)"
                    >
                      {{ status }}
                    </button>
                  </div>
                </section>

                <section class="compare-photo-list">
                  <header>
                    <strong>{{ __("Photo Sets") }}</strong>
                    <small>{{ filteredComparePhotoOptions.length }} {{ __("matching image(s)") }}</small>
                  </header>
                  <div>
                    <button
                      v-for="photo in filteredComparePhotoOptions.slice(0, 8)"
                      :key="photo.id"
                      type="button"
                      :class="{ active: photo.id === compareLeftImage?.id || photo.id === compareRightImage?.id }"
                      @click="chooseComparePhoto(photo)"
                    >
                      <img :src="photo.image" :alt="photo.label" loading="lazy" />
                      <span>
                        <b>{{ photo.label }}</b>
                        <small>{{ photo.meta }}</small>
                      </span>
                    </button>
                  </div>
                </section>
              </div>
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
                    <span>
                      <b>{{ formatNumber(item.dose) }}</b>
                      <small>{{ item.dose_unit || __("qty") }}</small>
                    </span>
                    <span>
                      <b>{{ item.available_qty === null || item.available_qty === undefined ? __("n/a") : formatNumber(item.available_qty) }}</b>
                      <small>{{ __("available") }}</small>
                    </span>
                    <span>
                      <b>{{ item.marks?.length || 0 }}</b>
                      <small>{{ __("marks") }}</small>
                    </span>
                  </div>
                  <p>{{ item.message }}</p>
                  <footer>
                    <button type="button" class="ghost small" :disabled="!item.marks?.length" @click="selectInventoryMark(item)">
                      {{ __("Select Mark") }}
                    </button>
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
                  <footer>
                    <button type="button" class="ghost small" :disabled="!item.mark" @click="selectFollowupMark(item)">
                      {{ __("Select Mark") }}
                    </button>
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

        <aside class="derma-console-side">
          <DermaQuickActionsPanel
            :active-procedure="activeProcedure"
            :can-annotate="bodyTemplates.length > 0"
            :allow-evidence="true"
            :alerts="encounterAlertItems"
            @new-procedure="openAnnotationStudio"
            @prescription="setActiveSection('prescriptions')"
            @upload-photos="uploadPhotos('Visit')"
            @annotate="openAnnotationStudio"
            @consent="setActiveSection('consent')"
            @followup="setActiveSection('clinical')"
            @alert-action="handleEncounterAlert"
          />

          <DermaEvidencePanel
            :active-procedure="null"
            :annotation-count="annotations.length"
            :photo-set-count="relevantPhotoSets.length"
            :summary="procedureArtifactText"
            :photo-summary="photoPanelSummary"
            :photo-compare="photoCompare"
            :photo-sets="relevantPhotoSets"
            :selected-photo-set-name="selectedPhotoSetName"
            :allow-upload="true"
            @upload="uploadPhotos('Visit')"
            @select-photo-set="(name) => (selectedPhotoSetName = name)"
          />

          <section class="encounter-snapshot-panel compact">
            <header>
              <div>
                <strong>{{ __("Visit Summary") }}</strong>
                <small>{{ __("Current encounter status") }}</small>
              </div>
            </header>
            <div class="encounter-stat-row">
              <span><b>{{ procedureCount }}</b><small>{{ __("procedures") }}</small></span>
              <span><b>{{ photoSets.length }}</b><small>{{ __("photo sets") }}</small></span>
              <span><b>{{ followupItems.length }}</b><small>{{ __("follow-ups") }}</small></span>
            </div>
            <div class="encounter-recent-list">
              <button
                v-for="procedure in procedures.slice(0, 3)"
                :key="procedure.name"
                type="button"
                @click="activateProcedure(procedure)"
              >
                <b>{{ procedure.title || procedure.template_label || procedure.procedure_template || procedure.name }}</b>
                <small>{{ [procedure.status, procedure.derma_category, procedure.procedure_date || procedure.start_date].filter(Boolean).join(' · ') }}</small>
              </button>
              <p v-if="!procedures.length" class="panel-muted">{{ __("No procedure activity yet.") }}</p>
            </div>
          </section>
        </aside>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue"
import ProcedurePanel from "./components/ProcedurePanel.vue"
import AssessmentPanel from "./components/AssessmentPanel.vue"
import PrescriptionPanel from "./components/PrescriptionPanel.vue"
import ConsentPanel from "./components/ConsentPanel.vue"
import DermaEncounterHeader from "./components/DermaEncounterHeader.vue"
import DermaQuickActionsPanel from "./components/DermaQuickActionsPanel.vue"
import DermaEvidencePanel from "./components/DermaEvidencePanel.vue"
import { openDermaAnnotationStudio } from "./annotation/DermaAnnotationStudio.jsx"

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

const MARK_STATUSES = ["Active", "Monitoring", "Improving", "Stable", "Worse", "Resolved", "Biopsied", "Excised", "Archived"]
const COMPARE_RESPONSE_STATUSES = ["Improving", "Stable", "Worse", "Resolved", "Monitoring"]

const SECTION_TABS = [
  { key: "clinical", label: __("Clinical Notes"), hint: __("SOAP") },
  { key: "photos", label: __("Photos"), hint: __("Compare") },
  { key: "prescriptions", label: __("Prescription"), hint: __("Rx") },
  { key: "consent", label: __("Consent"), hint: __("Forms") },
  { key: "review", label: __("Review"), hint: __("History") },
]

const DERMA_SECTION_STORAGE_KEY = "do_derma_chart_last_section"
const DERMA_USER_SETTINGS_DOCTYPE = "Derma Chart"

const data = ref({})
const loading = ref(false)
const loadError = ref("")
const syncingBillables = ref(false)
const completingSession = ref(false)
const selectedTemplate = ref(null)
const activeProcedureName = ref("")
const selectedBodyTemplate = ref(null)
const activeWorkspaceTab = ref("procedure_history")
const activeSection = ref(loadStoredDermaSection())
const chartMode = ref("perio")
const chartExpanded = ref(false)
const excalidrawRef = ref(null)
const procedureSaving = ref(false)
const annotationSaving = ref(false)
const markSaving = ref(false)
const summarySaving = ref(false)
const selectedMarkName = ref("")
const selectedMarkNames = ref([])
const selectedPreviousMarkNames = ref([])
const selectedPhotoSetName = ref("")
const selectedTimelineVisitKey = ref("")
const compareLeftId = ref("")
const compareRightId = ref("")
const compareCategoryFilter = ref("all")
const compareTypeFilter = ref("all")
const compareResponseStatus = ref("")
const chartOverlayMode = ref("today")
const selectedPriceList = ref("")
const defaultPriceList = ref("")
const sessionProvider = ref("")
const sessionAssistant = ref("")
const sessionDate = ref("")
const sessionCategory = ref("")
const pastAppointment = ref("")
const treatmentCase = ref("")
const sectionPreferenceHydrated = ref(false)

const procedureDraft = reactive({
  notes: "",
  product_item: "",
  product_name: "",
  dose: "",
  lot_no: "",
  settings: "",
  variables: {},
})

const assessmentPanel = reactive({
  loading: false,
  saving: false,
  editing: false,
  error: "",
  encounter: "",
  docstatus: null,
  layout: [],
  values: {},
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

const patient = computed(() => data.value.patient || {})
const appointment = computed(() => data.value.appointment || {})
const encounter = computed(() => data.value.encounter || {})
const isEncounterLocked = computed(() => Number(encounter.value.docstatus ?? 0) !== 0)
const procedureTemplates = computed(() => data.value.procedure_templates || [])
const procedures = computed(() => data.value.procedures || [])
const bodyTemplates = computed(() => (data.value.body_templates || []).map(normalizeBodyTemplate))
const templateSets = computed(() => data.value.template_sets || [])
const categories = computed(() => data.value.categories || [])
const annotations = computed(() => data.value.annotations || [])
const procedureAnnotations = computed(() => data.value.procedure_annotations || {})
const marks = computed(() => data.value.marks || [])
const previousMarks = computed(() => data.value.previous_marks || [])
const photoSets = computed(() => data.value.photo_sets || [])
const previousPhotoSets = computed(() => data.value.previous_photo_sets || [])
const visitTimeline = computed(() => data.value.visit_timeline || [])
const followupItems = computed(() => data.value.followup_items || [])
const inventoryReadiness = computed(() => data.value.inventory_readiness || [])
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
const latestAnnotation = computed(() => activeProcedureAnnotations.value[0] || data.value.latest_annotation || annotations.value[0] || null)
const currentAnnotationHistory = computed(() => annotations.value)
const visitSummary = computed(() => data.value.visit_summary || data.value.narrative || "")
const contextReady = computed(() => Boolean(patient.value.name || props.context?.patient || props.context?.encounter || props.context?.appointment))
const hasSessionContext = computed(() => Boolean(encounter.value.name))
const canCreateProcedure = computed(() => Boolean(selectedTemplate.value?.name && patient.value.name && encounter.value.name))
const currentPractitionerName = computed(() => encounter.value.practitioner_name || appointment.value.practitioner_name || sessionProvider.value || "")
const practitioners = computed(() => currentPractitionerName.value ? [{ name: sessionProvider.value, practitioner_name: currentPractitionerName.value }] : [])
const priceLists = computed(() => selectedPriceList.value ? [selectedPriceList.value] : [])
const anesthesiaTypes = computed(() => ["Local", "Topical", "Nerve Block", "Other"])
const anesthesiaRecorded = computed(() => anesthesiaPanel.rows.length > 0)
const procedureCount = computed(() => procedures.value.length)
const followupBlockers = computed(() => followupItems.value.filter((item) => item.blocking && !item.todo))
const inventoryBlockers = computed(() => inventoryReadiness.value.filter((item) => item.blocking))
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
const summaryMetaLabel = computed(() => {
  const parts = [
    marks.value.length ? __("{0} mark(s)").replace("{0}", marks.value.length) : "",
    procedures.value.length ? __("{0} procedure(s)").replace("{0}", procedures.value.length) : "",
    photoSets.value.length ? __("{0} photo set(s)").replace("{0}", photoSets.value.length) : "",
  ].filter(Boolean)
  return parts.join(" · ") || __("Updates from structured derma chart data")
})

const modeDisabled = computed(() => ({
  conditions: "",
  perio: "",
  overview: __("Derma overview will be added after the chart fork is stable."),
}))

const selectedTemplateLabel = computed(() => selectedTemplate.value?.template || selectedTemplate.value?.name || __("No procedure selected"))
const selectedTemplateHint = computed(() => {
  if (!selectedTemplate.value) return __("Select a derma procedure from the palette, then draw on the chart.")
  const bits = [
    selectedTemplate.value.custom_derma_category,
    selectedTemplate.value.custom_derma_marker_behavior,
    selectedTemplate.value.custom_derma_consent_required ? __("consent required") : "",
    selectedTemplate.value.custom_derma_before_after_photo_required ? __("photos required") : "",
  ].filter(Boolean)
  return bits.join(" · ") || __("Procedure is armed for this encounter.")
})
const selectedRegionLabel = computed(() => procedureDraft.variables?.region_label || procedureDraft.variables?.body_region || selectedMark.value?.region_label || selectedMark.value?.body_region || "")
const activeProcedureLabel = computed(() => activeProcedure.value?.title || activeProcedure.value?.template_label || activeProcedure.value?.procedure_template || activeProcedure.value?.name || "")
const activeProcedureMeta = computed(() => {
  const parts = [
    activeProcedure.value?.status,
    activeProcedure.value?.derma_category,
    activeProcedureTreatment.value?.body_view || activeProcedureTreatment.value?.body_region,
  ].filter(Boolean)
  return parts.join(" · ") || __("Draft procedure")
})
const procedureArtifactText = computed(() => {
  if (!activeProcedure.value) {
    const parts = [
      annotations.value.length ? __("{0} drawing(s)").replace("{0}", annotations.value.length) : "",
      photoSets.value.length ? __("{0} photo set(s)").replace("{0}", photoSets.value.length) : "",
    ].filter(Boolean)
    return parts.join(" · ") || __("Encounter evidence")
  }
  const parts = [
    activeProcedureAnnotations.value.length ? __("{0} drawing(s)").replace("{0}", activeProcedureAnnotations.value.length) : "",
    relevantPhotoSets.value.length ? __("{0} photo set(s)").replace("{0}", relevantPhotoSets.value.length) : "",
  ].filter(Boolean)
  return parts.join(" · ") || activeProcedure.value.derma_artifact_text || __("No evidence yet")
})
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
  if (selectedTemplate.value?.custom_derma_before_after_photo_required && activeProcedure.value && !relevantPhotoSets.value.length) {
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
const defaultFullBodyTemplate = computed(() => preferredBodyTemplate("Body"))
const currentChartViewLabel = computed(() => selectedBodyTemplate.value?.title || selectedBodyTemplate.value?.name || __("Full Body Chart"))
const currentChartViewHint = computed(() => {
  if (!selectedBodyTemplate.value?.name) return __("Patient atlas will load automatically when a body image is configured.")
  return [selectedBodyTemplate.value.gender, selectedBodyTemplate.value.template_type, selectedBodyTemplate.value.view_key].filter(Boolean).join(" / ")
})
const currentViewMarkCount = computed(() => {
  const templateName = selectedBodyTemplate.value?.name
  return marks.value.filter((mark) => !templateName || mark.body_template === templateName).length
})
const hasActiveChartWork = computed(() => Boolean(selectedTemplate.value || selectedMark.value || visibleMarks.value.length || selectedProcedureMarks.value.length))

const procedureVariables = computed(() => {
  const fields = selectedTemplate.value?.derma_variables || []
  return fields.map((field) => ({
    ...field,
    options: Array.isArray(field.options)
      ? field.options
      : String(field.options || "")
          .split("\n")
          .map((row) => row.trim())
          .filter(Boolean),
  }))
})

const missingRequiredFieldNames = computed(() => missingRequiredVariableFields().map((field) => field.fieldname))

const treatmentSetLabel = computed(() => {
  const category = selectedTemplate.value?.custom_derma_category || __("No procedure")
  const gender = preferredTemplateGender()
  const configured = templateSets.value.find((row) => {
    const categories = row.procedure_category_list || []
    return row.gender === gender && (!categories.length || categories.includes(category))
  })
  if (configured) return configured.title
  if (["Botox", "Filler", "Laser", "Acne", "Scar", "Pigmentation"].includes(category)) return __("Aesthetic Face Set")
  if (["Lesion", "Biopsy"].includes(category)) return __("Full Skin Exam Set")
  return category
})

const readinessItems = computed(() => {
  const template = selectedTemplate.value || {}
  const missing = missingRequiredVariables()
  const hasConsent = !template.custom_derma_consent_required || consentPanel.consents.length > 0
  const inventoryIssues = selectedInventoryBlockingCount()
  const hasInventory = !template.custom_derma_product_tracking_required || (hasInventoryEvidence() && !inventoryIssues)
  return [
    {
      key: "fields",
      label: __("Required fields"),
      state: missing.length ? "warning" : "ready",
      detail: missing.length ? missing.join(", ") : __("Complete"),
      action: missing.length ? __("Fill") : "",
      blocking: true,
    },
    {
      key: "consent",
      label: __("Consent"),
      state: hasConsent ? "ready" : "warning",
      detail: template.custom_derma_consent_required ? (hasConsent ? __("Signed/linked") : __("Required")) : __("Not required"),
      action: hasConsent ? "" : __("Open"),
      blocking: Boolean(template.custom_derma_consent_required),
    },
    {
      key: "photos",
      label: __("Photos"),
      state: "ready",
      detail: template.custom_derma_before_after_photo_required ? __("Required after draft procedure") : __("Optional after draft procedure"),
      action: "",
      blocking: false,
    },
    {
      key: "inventory",
      label: __("Inventory"),
      state: hasInventory ? "ready" : "warning",
      detail: template.custom_derma_product_tracking_required
        ? (inventoryIssues ? __("{0} blocker(s)").replace("{0}", inventoryIssues) : hasInventory ? __("Product and lot captured") : __("Product and lot needed"))
        : __("No product tracking"),
      action: hasInventory ? "" : __("Fill"),
      blocking: Boolean(template.custom_derma_product_tracking_required),
    },
  ]
})

const readinessBlockers = computed(() => readinessItems.value.filter((item) => item.blocking && item.state !== "ready"))

const categoryGroups = computed(() => {
  const map = new Map()
  for (const template of procedureTemplates.value) {
    const label = template.custom_derma_category || template.item_group || __("Derma")
    const id = label.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "derma"
    if (!map.has(id)) {
      map.set(id, { id, label, color: template.custom_derma_marker_color || categoryColor(label), image: "" })
    }
  }
  return Array.from(map.values())
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
    const label = row.title || row.template_label || row.procedure_template || row.name
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

const assessmentEditableOnSubmitFields = computed(() =>
  (assessmentPanel.layout || []).filter((row) => row.allow_on_submit).map((row) => row.fieldname).filter(Boolean)
)

const visibleMarks = computed(() => {
  const templateName = selectedTemplate.value?.name
  const bodyTemplate = selectedBodyTemplate.value?.name
  return marks.value
    .filter((mark) => (!templateName || mark.procedure_template === templateName) && (!bodyTemplate || mark.body_template === bodyTemplate))
    .sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0))
})

const selectedMark = computed(() => marks.value.find((mark) => mark.name === selectedMarkName.value) || null)

const visiblePreviousMarks = computed(() => {
  const bodyTemplate = selectedBodyTemplate.value?.name
  const templateName = selectedTemplate.value?.name
  const rows = previousMarks.value.filter((mark) => {
    if (selectedTimelineVisitKey.value && timelineKeyForRow(mark) !== selectedTimelineVisitKey.value) return false
    if (bodyTemplate && mark.body_template !== bodyTemplate) return false
    if (templateName && mark.procedure_template && mark.procedure_template !== templateName) return false
    if (chartOverlayMode.value === "history" && ["Resolved", "Archived"].includes(mark.status)) return false
    return true
  })
  if (chartOverlayMode.value !== "previous") return rows
  const latestEncounter = rows.find((mark) => mark.encounter)?.encounter
  return latestEncounter ? rows.filter((mark) => mark.encounter === latestEncounter) : rows
})

const canvasMarks = computed(() => {
  const current = marks.value.map((mark) => ({ ...mark, _history: false }))
  if (chartOverlayMode.value === "today") return current
  const history = visiblePreviousMarks.value.map((mark) => ({
    ...mark,
    _history: true,
    _history_mode: chartOverlayMode.value,
  }))
  return [...history, ...current]
})

const historyPanelTitle = computed(() => {
  if (selectedTimelineVisitKey.value) return __("Selected Visit")
  if (chartOverlayMode.value === "previous") return __("Previous Visit")
  return __("Active History")
})

const selectedTimelineVisit = computed(() => visitTimeline.value.find((visit) => visit.key === selectedTimelineVisitKey.value) || visitTimeline.value[0] || null)

const relevantPhotoSets = computed(() => {
  if (activeProcedure.value?.name) {
    const treatmentNames = new Set(activeProcedureTreatments.value.map((row) => row.name).filter(Boolean))
    return photoSets.value
      .filter((set) =>
        set.clinical_procedure === activeProcedure.value.name ||
        (set.treatment_entry && treatmentNames.has(set.treatment_entry))
      )
      .map((set) => ({ ...set, _period: "today" }))
  }
  const selected = selectedMark.value
  const bodyView = selected?.body_view || selectedBodyTemplate.value?.title || selectedBodyTemplate.value?.name
  const bodyRegion = selected?.body_region || selected?.body_template || selectedBodyTemplate.value?.template_type
  const current = photoSets.value.filter((set) => photoSetMatchesContext(set, selected, bodyView, bodyRegion)).map((set) => ({ ...set, _period: "today" }))
  const previous = previousPhotoSets.value.filter((set) => photoSetMatchesContext(set, selected, bodyView, bodyRegion)).map((set) => ({ ...set, _period: "previous" }))
  return [...current, ...previous]
})

const selectedPhotoSet = computed(() => {
  return relevantPhotoSets.value.find((set) => set.name === selectedPhotoSetName.value) || relevantPhotoSets.value[0] || null
})

const photoCompare = computed(() => {
  const current = photoSets.value.find((set) => photoSetImages(set).length && relevantPhotoSets.value.some((row) => row.name === set.name)) || null
  const previous = previousPhotoSets.value.find((set) => photoSetImages(set).length && relevantPhotoSets.value.some((row) => row.name === set.name)) || null
  const selectedImages = selectedPhotoSet.value ? photoSetImages(selectedPhotoSet.value) : []
  const beforeImage = previous ? photoSetImages(previous)[0] : selectedImages.find((photo) => String(photo.photo_type || "").toLowerCase() === "before")
  const afterImage = current ? photoSetImages(current)[0] : selectedImages.find((photo) => ["after", "visit", "procedure"].includes(String(photo.photo_type || "").toLowerCase())) || selectedImages[0]
  return {
    before: beforeImage ? { image: beforeImage.image, label: previous ? `${__("Previous")} · ${formatDate(previous.creation)}` : beforeImage.photo_type || __("Before") } : null,
    after: afterImage ? { image: afterImage.image, label: current ? `${__("Today")} · ${formatDate(current.creation)}` : afterImage.photo_type || __("Today") } : null,
  }
})

const photoPanelSummary = computed(() => {
  if (activeProcedure.value?.name) {
    const count = relevantPhotoSets.value.reduce((total, set) => total + photoSetImages(set).length, 0)
    return `${count} ${__("procedure image(s)")}`
  }
  const currentCount = photoSets.value.reduce((total, set) => total + photoSetImages(set).length, 0)
  const previousCount = previousPhotoSets.value.reduce((total, set) => total + photoSetImages(set).length, 0)
  return `${currentCount} ${__("today")} · ${previousCount} ${__("previous")}`
})

const comparePhotoOptions = computed(() => {
  const rows = []
  const sets = [
    ...previousPhotoSets.value.map((set) => ({ ...set, _period: "previous" })),
    ...photoSets.value.map((set) => ({ ...set, _period: "today" })),
  ]
  for (const set of sets) {
    const photos = photoSetImages(set)
    const linkedMark = findMarkForPhotoSet(set)
    photos.forEach((photo, index) => {
      const type = photo.photo_type || set.set_type || __("Visit")
      const date = formatDate(set.creation || set.modified)
      const location = set.body_view || set.body_region || linkedMark?.body_view || linkedMark?.body_region || ""
      rows.push({
        id: `${set.name}-${photo.name || index}`,
        image: photo.image,
        photo,
        set,
        period: set._period,
        type,
        category: linkedMark?.category || "",
        visit_key: timelineKeyForRow(set),
        label: `${set._period === "today" ? __("Today") : __("Previous")} · ${type}`,
        meta: [date, location, linkedMark?.category].filter(Boolean).join(" · "),
      })
    })
  }
  return rows
})

const compareCategories = computed(() => {
  const categories = new Set(comparePhotoOptions.value.map((photo) => photo.category).filter(Boolean))
  for (const mark of [...marks.value, ...previousMarks.value]) {
    if (mark.category) categories.add(mark.category)
  }
  return [...categories].sort()
})

const comparePhotoTypes = computed(() => [...new Set(comparePhotoOptions.value.map((photo) => photo.type).filter(Boolean))].sort())

const filteredComparePhotoOptions = computed(() => {
  return comparePhotoOptions.value.filter((photo) => {
    if (compareCategoryFilter.value !== "all" && photo.category !== compareCategoryFilter.value) return false
    if (compareTypeFilter.value !== "all" && photo.type !== compareTypeFilter.value) return false
    if (selectedTimelineVisitKey.value && photo.period === "previous" && photo.visit_key !== selectedTimelineVisitKey.value) return false
    return true
  })
})

const compareLeftImage = computed(() => {
  if (compareLeftId.value) return comparePhotoOptions.value.find((photo) => photo.id === compareLeftId.value) || null
  return (
    filteredComparePhotoOptions.value.find((photo) => photo.period === "previous") ||
    filteredComparePhotoOptions.value.find((photo) => String(photo.type || "").toLowerCase() === "before") ||
    null
  )
})

const compareRightImage = computed(() => {
  if (compareRightId.value) return comparePhotoOptions.value.find((photo) => photo.id === compareRightId.value) || null
  return (
    filteredComparePhotoOptions.value.find((photo) => photo.period === "today" && photo.id !== compareLeftImage.value?.id) ||
    filteredComparePhotoOptions.value.find((photo) => ["after", "visit", "procedure"].includes(String(photo.type || "").toLowerCase()) && photo.id !== compareLeftImage.value?.id) ||
    filteredComparePhotoOptions.value.find((photo) => photo.id !== compareLeftImage.value?.id) ||
    null
  )
})

function findMarkForPhotoSet(set) {
  if (!set?.name) return null
  return [...marks.value, ...previousMarks.value].find((mark) => mark.photo_set === set.name || (set.treatment_entry && mark.treatment_entry === set.treatment_entry)) || null
}

function hasRequiredPhotoEvidence() {
  if (selectedProcedureMarks.value.some((mark) => mark.photo_set)) return true
  if (!selectedProcedureMarks.value.length) {
    return photoSets.value.some((set) => photoSetImages(set).length && photoSetMatchesContext(set, selectedMark.value, selectedBodyTemplate.value?.title, selectedBodyTemplate.value?.template_type))
  }
  return selectedProcedureMarks.value.some((mark) =>
    photoSets.value.some((set) => photoSetImages(set).length && photoSetMatchesContext(set, mark, mark.body_view, mark.body_region || mark.body_template))
  )
}

function hasInventoryEvidence() {
  return Boolean(draftOrSelectedMarkValue("product_item", "item", "item_code", "product_name", "product", "injectable") && draftOrSelectedMarkValue("lot_no", "lot"))
}

function selectedInventoryBlockingCount() {
  const names = new Set(selectedProcedureMarks.value.map((mark) => mark.name))
  if (!names.size && selectedMark.value?.name) names.add(selectedMark.value.name)
  if (!names.size) return 0
  return inventoryBlockers.value.filter((item) => (item.marks || []).some((name) => names.has(name))).length
}

function draftOrSelectedMarkValue(...keys) {
  const draft = normalizeProcedureDraft()
  for (const key of keys) {
    const normalizedKey = normalizeVariableKey(key)
    if (draft[normalizedKey]) return draft[normalizedKey]
    const value = variableValue(draft.variables, key)
    if (value) return value
  }
  for (const mark of selectedProcedureMarks.value) {
    for (const key of keys) {
      const value = markValueForField(mark, key)
      if (value !== undefined && value !== null && value !== "") return value
    }
  }
  return ""
}

const selectedProcedureMarks = computed(() => {
  const names = new Set(selectedMarkNames.value)
  return marks.value.filter((mark) => {
    if (!names.has(mark.name) || mark.clinical_procedure) return false
    if (selectedTemplate.value?.name && mark.procedure_template && mark.procedure_template !== selectedTemplate.value.name) return false
    return true
  })
})

const selectedMarksLabel = computed(() => {
  if (!selectedMarkNames.value.length) return markTotalsLabel.value
  return `${selectedProcedureMarks.value.length} ${__("selected")} · ${markTotalsLabel.value}`
})

const batchDoseTotal = computed(() => {
  const rows = selectedProcedureMarks.value
  const total = rows.reduce((sum, mark) => sum + Number(mark.dose || 0), 0)
  const unit = rows.find((mark) => mark.dose_unit)?.dose_unit || selectedTemplateDoseUnit()
  return {
    value: total ? formatNumber(total) : "0",
    label: unit || __("dose"),
  }
})

const batchSelectionSummary = computed(() => {
  if (!selectedProcedureMarks.value.length) return __("Select draft marks to create a procedure.")
  const categories = new Set(selectedProcedureMarks.value.map((mark) => mark.category).filter(Boolean))
  const views = new Set(selectedProcedureMarks.value.map((mark) => mark.body_view || mark.body_template).filter(Boolean))
  return `${selectedProcedureMarks.value.length} ${__("mark(s)")} · ${[...categories].join(", ") || __("Procedure")} · ${[...views].slice(0, 2).join(", ")}`
})

const createProcedureLabel = computed(() => {
  const count = selectedProcedureMarks.value.length
  if (count > 1) return __("Add Procedure ({0} marks)").replace("{0}", count)
  return __("Add Procedure")
})

const markTotalsLabel = computed(() => {
  if (!visibleMarks.value.length) return __("No marks")
  const category = selectedTemplate.value?.custom_derma_category || visibleMarks.value[0]?.category || __("Marks")
  const doseTotal = visibleMarks.value.reduce((total, mark) => total + Number(mark.dose || 0), 0)
  if (doseTotal) {
    const unit = visibleMarks.value.find((mark) => mark.dose_unit)?.dose_unit || ""
    return `${visibleMarks.value.length} ${__("marks")} · ${formatNumber(doseTotal)} ${unit}`.trim()
  }
  return `${visibleMarks.value.length} ${category}`
})

const chartTotals = computed(() => {
  const rows = marks.value || []
  const units = rows.reduce((total, mark) => total + (String(mark.dose_unit || "").toLowerCase().includes("unit") ? Number(mark.dose || 0) : 0), 0)
  const ml = rows.reduce((total, mark) => total + (String(mark.dose_unit || "").toLowerCase() === "ml" ? Number(mark.dose || 0) : 0), 0)
  const biopsies = rows.filter((mark) => String(mark.category || "").toLowerCase().includes("biopsy")).length
  return [
    { key: "marks", value: rows.length, label: __("marks") },
    { key: "units", value: units ? formatNumber(units) : "0", label: __("Botox units") },
    { key: "ml", value: ml ? formatNumber(ml) : "0", label: __("Filler ml") },
    { key: "biopsy", value: biopsies, label: __("biopsies") },
  ]
})

const chartTotalsLabel = computed(() => {
  if (!marks.value.length) return __("No structured marks yet")
  const categories = new Set(marks.value.map((mark) => mark.category).filter(Boolean))
  return `${marks.value.length} ${__("marks")} · ${categories.size || 1} ${__("categories")}`
})

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

watch(
  () => visibleMarks.value.map((mark) => mark.name).join(","),
  () => {
    if (selectedMarkName.value && !visibleMarks.value.some((mark) => mark.name === selectedMarkName.value)) {
      selectedMarkName.value = ""
    }
  }
)

watch(
  () => chartMode.value,
  async (mode) => {
    if (mode === "perio" && selectedBodyTemplate.value) {
      await nextTick()
      await excalidrawRef.value?.loadTemplateImage?.(selectedBodyTemplate.value)
    }
  }
)

watch(
  () => chartExpanded.value,
  () => {
    refitChartAfterLayout()
  }
)

function normalizeDermaSection(section) {
  if (section === "procedure" || section === "procedures") return "review"
  if (section === "encounter" || section === "chart" || section === "notes") return "clinical"
  if (section === "consents") return "consent"
  if (["clinical", "photos", "prescriptions", "consent", "review"].includes(section)) return section
  return "clinical"
}

function loadStoredDermaSection() {
  const fallback = "clinical"
  try {
    const settings = window.frappe?.get_user_settings?.(DERMA_USER_SETTINGS_DOCTYPE) || {}
    return normalizeDermaSection(settings.last_section || settings.last_mode)
  } catch (error) {
    // Local fallback keeps the chart usable if user settings are not bootstrapped.
  }
  try {
    const localSection = window.localStorage?.getItem(DERMA_SECTION_STORAGE_KEY)
    return normalizeDermaSection(localSection)
  } catch (error) {
    return fallback
  }
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

async function hydrateDermaSectionPreference() {
  if (sectionPreferenceHydrated.value) return
  sectionPreferenceHydrated.value = true
  try {
    const response = await window.frappe?.model?.user_settings?.get?.(DERMA_USER_SETTINGS_DOCTYPE)
    const savedSection = normalizeDermaSection(response?.last_section || response?.last_mode)
    if (savedSection !== activeSection.value) {
      activeSection.value = savedSection
    }
  } catch (error) {
    // The local fallback selected during setup remains valid.
  }
}

async function setActiveSection(section, tab = "") {
  activeSection.value = normalizeDermaSection(section)
  if (tab) activeWorkspaceTab.value = tab
  persistDermaSection(activeSection.value)
  await ensureSectionData(activeSection.value, tab)
}

async function ensureSectionData(section = activeSection.value, tab = activeWorkspaceTab.value) {
  const normalized = normalizeDermaSection(section)
  if (normalized === "clinical") {
    if (!patient.value.name && !props.context?.patient && !props.context?.encounter && !props.context?.appointment) return
    await Promise.all([loadAssessment(), loadPrescriptionPanel()])
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
    selectedMarkNames.value = selectedMarkNames.value.filter((name) => marks.value.some((mark) => mark.name === name))
    selectedPreviousMarkNames.value = selectedPreviousMarkNames.value.filter((name) => previousMarks.value.some((mark) => mark.name === name))
    if (selectedPhotoSetName.value && !relevantPhotoSets.value.some((set) => set.name === selectedPhotoSetName.value)) selectedPhotoSetName.value = ""
    Object.keys(loadedTabs).forEach((key) => (loadedTabs[key] = false))
    await hydrateDermaSectionPreference()
    await ensureSectionData(activeSection.value, activeWorkspaceTab.value)
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

function photoSetImages(set) {
  return (set?.photos || []).filter((photo) => photo?.image)
}

function photoSetMatchesContext(set, mark, bodyView, bodyRegion) {
  if (!set) return false
  if (!mark && !bodyView && !bodyRegion) return true
  if (mark?.treatment_entry && set.treatment_entry && set.treatment_entry === mark.treatment_entry) return true
  if (mark?.photo_set && set.name === mark.photo_set) return true
  if (bodyView && set.body_view && set.body_view === bodyView) return true
  if (bodyRegion && set.body_region && set.body_region === bodyRegion) return true
  return !set.body_view && !set.body_region && !set.treatment_entry
}

function openPhotoSetForm() {
  if (selectedPhotoSet.value?.name) {
    frappe.msgprint({
      title: __("Photo Set"),
      message: `<p><b>${selectedPhotoSet.value.name}</b></p><p>${__("Use Upload Photo to add more encounter or procedure evidence without leaving this page.")}</p>`,
      indicator: "blue",
    })
    return
  }
  frappe.msgprint(__("Use Upload Photo to create a photo set from this encounter page."))
}

function uploadPhotos(photoType = "Visit") {
  if (!patient.value.name || !encounter.value.name) {
    frappe.msgprint(__("A patient encounter is required before uploading photos."))
    return
  }
  if (!window.frappe?.ui?.FileUploader) {
    openPhotoSetForm()
    return
  }
  const uploaded = []
  new frappe.ui.FileUploader({
    allow_multiple: true,
    restrictions: { allowed_file_types: ["image/*"] },
    on_success(file) {
      if (file?.file_url) uploaded.push(file.file_url)
    },
    on_close: async () => {
      if (!uploaded.length) return
      await createPhotoSetFromImages(uploaded, photoType)
    },
  })
}

async function createPhotoSetFromImages(images, photoType = "Visit") {
  const response = await frappe.call({
    method: "do_derma.api.create_photo_set",
    args: {
      values: {
        patient: patient.value.name,
	        appointment: appointment.value.name,
	        encounter: encounter.value.name,
	        clinical_procedure: activeProcedure.value?.name || "",
	        chart_mark: selectedMark.value?.name,
	        set_type: photoType === "Before" || photoType === "After" ? "Before/After" : photoType,
	        body_view: selectedMark.value?.body_view || selectedBodyTemplate.value?.title || "",
	        body_region: selectedMark.value?.body_region || selectedBodyTemplate.value?.template_type || "",
	        treatment_entry: activeProcedureTreatmentName.value || selectedMark.value?.treatment_entry || "",
	        notes: activeProcedure.value?.name ? `Linked to Clinical Procedure ${activeProcedure.value.name}` : selectedMark.value ? `Linked to chart mark ${selectedMark.value.name}` : "",
	        photos: images.map((image) => ({
	          image,
	          photo_type: photoType,
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
	    selectedPhotoSetName.value = response.message.name
	    frappe.show_alert({ message: __("Photos linked to chart"), indicator: "green" })
	    await refresh()
	  }
	}

function setChartOverlayMode(mode) {
  chartOverlayMode.value = mode || "today"
  if (chartOverlayMode.value === "today") {
    selectedPreviousMarkNames.value = []
    selectedTimelineVisitKey.value = ""
  }
}

function selectTimelineVisit(visit) {
  if (!visit?.key) return
  selectedTimelineVisitKey.value = visit.key
}

function overlayTimelineVisit(visit = selectedTimelineVisit.value) {
  if (!visit?.key) return
  selectedTimelineVisitKey.value = visit.key
  selectedPreviousMarkNames.value = (visit.marks || []).map((mark) => mark.name).filter(Boolean)
  chartOverlayMode.value = "history"
  const firstTemplate = (visit.marks || []).find((mark) => mark.body_template)?.body_template
  if (firstTemplate) {
    const template = bodyTemplates.value.find((row) => row.name === firstTemplate)
    if (template) loadBodyTemplate(template)
  }
  frappe.show_alert({ message: __("Previous visit marks overlaid"), indicator: "blue" })
}

function compareTimelineVisit(visit = selectedTimelineVisit.value) {
  if (!visit?.key) return
  selectedTimelineVisitKey.value = visit.key
  compareLeftId.value = ""
  compareRightId.value = ""
  setActiveSection("photos")
}

function clearTimelineOverlay() {
  selectedTimelineVisitKey.value = ""
  selectedPreviousMarkNames.value = []
  chartOverlayMode.value = "today"
}

function timelineKeyForRow(row) {
  return row?.encounter || row?.appointment || String(row?.creation || row?.modified || "").slice(0, 10) || "Unlinked"
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

function openEncounter() {
  if (!encounter.value.name) return
  frappe.msgprint({
    title: __("Encounter"),
    message: `<p><b>${escapeHtml(encounter.value.name)}</b></p><p>${__("This encounter can be completed from this page without opening the form.")}</p>`,
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
    uploadPhotos(activeProcedure.value ? "Procedure" : "Visit")
    return
  }
  if (alert.tab) {
    setActiveSection(alert.tab === "compare" ? "photos" : "review")
  }
}

function activateProcedure(procedure) {
  const name = procedure?.clinical_procedure || procedure?.name
  if (!name) return
  activeProcedureName.value = name
  const templateName = procedure.procedure_template
  const template = procedureTemplates.value.find((row) => row.name === templateName)
  if (template) {
    selectedTemplate.value = template
    initializeProcedureVariables(template)
  }
  applyProcedureToDraft(procedure)
  ensureSelectedBodyTemplate(true)
  chartMode.value = "perio"
  setActiveSection("review")
  frappe.show_alert({ message: __("Procedure selected for review"), indicator: "blue" })
}

function openItem(itemCode) {
  if (itemCode) frappe.msgprint({ title: __("Inventory Item"), message: escapeHtml(itemCode), indicator: "blue" })
}

function chooseComparePhoto(photo) {
  if (!photo?.id) return
  if (!compareLeftId.value || compareLeftId.value === photo.id) {
    compareLeftId.value = photo.id
    return
  }
  compareRightId.value = photo.id
}

function swapCompareImages() {
  const left = compareLeftImage.value?.id || ""
  const right = compareRightImage.value?.id || ""
  compareLeftId.value = right
  compareRightId.value = left
}

async function setCompareResponse(status) {
  compareResponseStatus.value = status
  if (!selectedMark.value) {
    frappe.msgprint(__("Select a chart mark before saving the clinical response."))
    return
  }
  await updateSelectedMarkStatus(status)
}

function selectTemplateRegion(region) {
  const name = region?.part_name || region?.partName || region?.region_label || region?.body_region
  if (!name) return
  procedureDraft.variables = {
    ...(procedureDraft.variables || {}),
    body_region: name,
    region_label: region?.part_name || region?.partName || name,
  }
  frappe.show_alert({ message: __("Region selected: {0}").replace("{0}", name), indicator: "blue" })
}

function selectInventoryMark(item) {
  const markName = item?.marks?.[0]
  const mark = marks.value.find((row) => row.name === markName)
  if (!mark) {
    frappe.msgprint(__("This inventory row is not linked to a current chart mark."))
    return
  }
  selectMark(mark)
  setActiveSection("review")
}

function selectFollowupMark(item) {
  const mark = marks.value.find((row) => row.name === item?.mark)
  if (!mark) {
    frappe.msgprint(__("This follow-up item is not linked to a current chart mark."))
    return
  }
  selectMark(mark)
  setActiveSection("review")
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
    data.value = {
      ...data.value,
      followup_items: followupItems.value.map((row) => (row.key === item.key ? { ...row, todo: response.message.name } : row)),
    }
    frappe.show_alert({ message: __("Follow-up task created"), indicator: "green" })
  }
}

function openTodo(name) {
  if (name) frappe.msgprint({ title: __("Follow-up Task"), message: escapeHtml(name), indicator: "blue" })
}

function selectTemplate(template) {
  activeProcedureName.value = ""
  selectedTemplate.value = template
  activeWorkspaceTab.value = "procedure_history"
  setActiveSection("review")
  if (template?.custom_derma_note_template && !procedureDraft.notes) {
    procedureDraft.notes = template.custom_derma_note_template
  }
  initializeProcedureVariables(template)
  ensureSelectedBodyTemplate(true)
}

function clearTemplate() {
  selectedTemplate.value = null
  activeProcedureName.value = ""
  selectedMarkName.value = ""
  selectedMarkNames.value = []
  chartMode.value = "perio"
  resetProcedureDraft()
}

function startNewProcedure() {
  openAnnotationStudio()
}

function resetProcedureDraft() {
  procedureDraft.notes = ""
  procedureDraft.product_item = ""
  procedureDraft.product_name = ""
  procedureDraft.dose = ""
  procedureDraft.lot_no = ""
  procedureDraft.settings = ""
  procedureDraft.variables = {}
}

function initializeProcedureVariables(template = selectedTemplate.value) {
  const next = {}
  const category = template?.custom_derma_category || ""
  for (const field of template?.derma_variables || []) {
    next[field.fieldname] = procedureDraft.variables?.[field.fieldname] ?? procedureDefaultValue(field, category)
  }
  procedureDraft.variables = next
}

function procedureDefaultValue(field, category) {
  const key = normalizeVariableKey(field.fieldname)
  const categoryKey = String(category || "").toLowerCase()
  if (key === "dose_unit" && categoryKey === "botox") return "Units"
  if (key === "dose_unit" && categoryKey === "filler") return "ml"
  if (key === "dose_unit" && categoryKey === "laser") return "passes"
  if (key === "status") return "Active"
  return ""
}

function missingRequiredVariables() {
  return procedureVariables.value
    .filter((field) => field.required && !hasProcedureVariableValue(field.fieldname))
    .map((field) => field.label || field.fieldname)
}

function missingRequiredVariableFields() {
  return procedureVariables.value.filter((field) => field.required && !hasProcedureVariableValue(field.fieldname))
}

async function focusRequiredProcedureFields() {
  await setActiveSection("review")
  await nextTick()
  const firstMissing = document.querySelector(".derma-procedure-fields .missing input, .derma-procedure-fields .missing select, .derma-procedure-fields .missing textarea")
  firstMissing?.scrollIntoView?.({ behavior: "smooth", block: "center" })
  firstMissing?.focus?.()
}

async function handleReadinessItem(item) {
  if (!item || item.state === "ready") return
  if (["fields", "inventory"].includes(item.key)) {
    await focusRequiredProcedureFields()
    return
  }
  if (item.key === "consent") {
    await setActiveSection("consent")
    return
  }
  if (item.key === "photos") {
    uploadPhotos("Visit")
    return
  }
  if (item.key === "image") {
    ensureSelectedBodyTemplate(true)
    if (selectedBodyTemplate.value) loadBodyTemplate(selectedBodyTemplate.value)
    return
  }
  if (item.key === "mark") {
    frappe.show_alert({ message: __("Click the drawing surface to place a chart mark."), indicator: "blue" })
  }
}

function frappeFieldtype(fieldtype) {
  if (fieldtype === "Small Text") return "Small Text"
  if (fieldtype === "Select") return "Select"
  if (fieldtype === "Float") return "Float"
  if (fieldtype === "Int") return "Int"
  if (fieldtype === "Date") return "Date"
  if (fieldtype === "Check") return "Check"
  return "Data"
}

function hasProcedureVariableValue(fieldname) {
  const value = procedureDraft.variables?.[fieldname]
  return value !== undefined && value !== null && value !== ""
}

function normalizeProcedureDraft() {
  const variables = procedureDraft.variables || {}
  return {
    notes: procedureDraft.notes,
    product_item: procedureDraft.product_item || variableValue(variables, "product_item", "item", "item_code"),
    product_name: procedureDraft.product_name || variableValue(variables, "product_name", "product", "injectable"),
    dose: procedureDraft.dose || variableValue(variables, "dose", "units", "ml", "quantity"),
    dose_unit: variableValue(variables, "dose_unit") || (variableValue(variables, "units") ? "Units" : variableValue(variables, "ml") ? "ml" : ""),
    lot_no: procedureDraft.lot_no || variableValue(variables, "lot_no", "lot"),
    expiry_date: variableValue(variables, "expiry_date", "expiry"),
    device: variableValue(variables, "device"),
    settings: procedureDraft.settings || procedureSettings(variables),
    variables,
  }
}

function variableValue(variables, ...keys) {
  const normalized = {}
  for (const [key, value] of Object.entries(variables || {})) {
    normalized[normalizeVariableKey(key)] = value
  }
  for (const key of keys) {
    const value = normalized[normalizeVariableKey(key)]
    if (value !== undefined && value !== null && value !== "") return value
  }
  return ""
}

function selectedTemplateDoseUnit() {
  const category = String(selectedTemplate.value?.custom_derma_category || "").toLowerCase()
  if (category.includes("botox")) return "Units"
  if (category.includes("filler")) return "ml"
  if (category.includes("laser")) return "passes"
  return ""
}

function procedureSettings(variables) {
  const ignored = new Set(["product_item", "item", "item_code", "product_name", "product", "injectable", "lot_no", "lot", "expiry_date", "expiry", "dose", "dose_unit", "units", "ml", "quantity", "body_region", "region_label", "site"])
  return Object.entries(variables || {})
    .filter(([key, value]) => value !== undefined && value !== null && value !== "" && !ignored.has(normalizeVariableKey(key)))
    .map(([key, value]) => `${labelizeVariableKey(key)}: ${value}`)
    .join("; ")
}

function normalizeVariableKey(key) {
  return String(key || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

function labelizeVariableKey(key) {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function numericValue(value) {
  if (value === undefined || value === null || value === "") return ""
  const parsed = Number(value)
  if (Number.isFinite(parsed)) return parsed
  const match = String(value).match(/-?\d+(\.\d+)?/)
  return match ? Number(match[0]) : ""
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

async function setActiveWorkspaceTab(tab) {
  activeWorkspaceTab.value = tab
  await ensureWorkspaceTab(tab)
}

async function ensureWorkspaceTab(tab, force = false) {
  if (tab === "assessment") return loadAssessment(force)
  if (tab === "prescriptions") return loadPrescriptionPanel(force)
  if (tab === "anesthesia") return loadAnesthesiaPanel(force)
  if (tab === "consents") return loadConsentPanel(force)
}

async function createProcedure() {
  if (!canCreateProcedure.value) {
    frappe.msgprint(__("Select a procedure template and make sure this visit has an encounter."))
    return
  }
  const missing = missingRequiredVariables()
  if (missing.length) {
    await focusRequiredProcedureFields()
    frappe.show_alert({
      message: __("Complete required procedure details first."),
      indicator: "orange",
    })
    return
  }
  if (selectedTemplate.value?.custom_derma_consent_required && !loadedTabs.consents) {
    await loadConsentPanel(true)
  }
  const blockers = readinessBlockers.value.filter((item) => item.key !== "fields" || missingRequiredVariables().length)
  if (blockers.length) {
    frappe.msgprint({
      title: __("Procedure is not ready"),
      message: blockers.map((item) => `${item.label}: ${item.detail}`).join("<br>"),
      indicator: "orange",
    })
    return
  }
  procedureSaving.value = true
  try {
    const response = await frappe.call({
      method: "do_derma.api.create_derma_chart_procedure",
      args: {
        payload: buildProcedurePayload(),
      },
    })
    const procedureName = response.message?.clinical_procedure?.name
    if (procedureName) {
      activeProcedureName.value = procedureName
      chartMode.value = "perio"
      setActiveSection("review")
      frappe.show_alert({ message: __("Clinical Procedure created"), indicator: "green" })
    }
    selectedMarkNames.value = []
    selectedMarkName.value = ""
    await refresh()
  } finally {
    procedureSaving.value = false
  }
}

function buildProcedurePayload() {
  const draft = normalizeProcedureDraft()
  const variables = draft.variables || {}
  return {
    patient: patient.value.name,
    appointment: appointment.value.name,
    encounter: encounter.value.name,
    procedure_template: selectedTemplate.value?.name,
    category: selectedTemplate.value?.custom_derma_category,
    body_template: selectedBodyTemplate.value?.name,
    body_view: selectedBodyTemplate.value?.title || selectedBodyTemplate.value?.name,
    body_region: variableValue(variables, "body_region", "site") || selectedBodyTemplate.value?.template_type || "",
    region_label: variableValue(variables, "region_label") || selectedRegionLabel.value || "",
    notes: draft.notes,
    product_item: draft.product_item,
    product_name: draft.product_name,
    dose: numericValue(draft.dose),
    dose_unit: draft.dose_unit,
    lot_no: draft.lot_no,
    expiry_date: draft.expiry_date,
    device: draft.device,
    settings: draft.settings,
    procedure_variables: variables,
  }
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
  if (!mark.clinical_procedure && !selectedMarkNames.value.includes(mark.name)) {
    selectedMarkNames.value = [mark.name]
  }
  applyMarkToDraft(mark)
  excalidrawRef.value?.selectMark?.(mark.name)
}

function selectTemplateForMark(mark) {
  if (mark.procedure_template && mark.procedure_template !== selectedTemplate.value?.name) {
    const template = procedureTemplates.value.find((row) => row.name === mark.procedure_template)
    if (template) {
      selectedTemplate.value = template
      initializeProcedureVariables(template)
    }
  }
}

async function updateSelectedMarkStatus(status) {
  if (!selectedMark.value) return
  markSaving.value = true
  try {
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
      applyMarkToDraft(response.message)
      await refreshVisitSummary()
      frappe.show_alert({ message: __("Mark status updated"), indicator: "green" })
    }
  } finally {
    markSaving.value = false
  }
}

function applyMarkToDraft(mark) {
  procedureDraft.notes = mark.note || procedureDraft.notes || ""
  const next = { ...(procedureDraft.variables || {}) }
  for (const field of procedureVariables.value) {
    const value = markValueForField(mark, field.fieldname)
    if (value !== undefined && value !== null && value !== "") next[field.fieldname] = value
  }
  procedureDraft.variables = next
}

function markValueForField(mark, fieldname) {
  const key = normalizeVariableKey(fieldname)
  const map = {
    product_item: mark.product_item,
    item: mark.product_item,
    item_code: mark.product_item,
    product_name: mark.product_name,
    product: mark.product_name,
    injectable: mark.product_name,
    dose: mark.dose,
    units: mark.dose,
    ml: mark.dose,
    quantity: mark.dose,
    dose_unit: mark.dose_unit,
    lot_no: mark.lot_no,
    lot: mark.lot_no,
    expiry_date: mark.expiry_date,
    expiry: mark.expiry_date,
    device: mark.device,
    settings: mark.settings,
    passes: mark.passes,
    plane: mark.plane,
    technique: mark.technique,
    lesion_id: mark.lesion_id,
    body_region: mark.body_region,
    region_label: mark.region_label,
    site: mark.body_region,
    diagnosis: mark.diagnosis,
    severity: mark.severity,
    status: mark.status,
  }
  return map[key]
}

async function refreshVisitSummary() {
  if (!encounter.value.name && !patient.value.name) return
  const response = await frappe.call({
    method: "do_derma.api.generate_visit_summary",
    args: { encounter: encounter.value.name, patient: patient.value.name },
  })
  data.value = { ...data.value, visit_summary: response.message || "" }
}

async function copySummaryToAssessment() {
  if (!visitSummary.value) return
  summarySaving.value = true
  try {
    if (!loadedTabs.assessment) await loadAssessment(true)
    const fieldname = assessmentSummaryField()
    if (!fieldname) {
      frappe.msgprint(__("No editable text field was found in the encounter assessment tab."))
      return
    }
    const current = assessmentPanel.values?.[fieldname] || ""
    const nextValue = current && !String(current).includes(visitSummary.value)
      ? `${current}\n\n${visitSummary.value}`
      : visitSummary.value
    await saveAssessment({ [fieldname]: nextValue })
    activeWorkspaceTab.value = "assessment"
    assessmentPanel.editing = true
    frappe.show_alert({ message: __("Derma summary copied to assessment"), indicator: "green" })
  } finally {
    summarySaving.value = false
  }
}

function assessmentSummaryField() {
  const rows = assessmentPanel.layout || []
  const writableTextRows = rows.filter((row) => {
    if (!row.fieldname || !row.is_value_field || row.read_only || row.is_table) return false
    return ["Text", "Small Text", "Long Text", "Text Editor", "Markdown Editor"].includes(row.fieldtype)
  })
  const preferred = writableTextRows.find((row) => /assessment|summary|note|plan|objective|subjective/i.test(`${row.fieldname} ${row.label}`))
  return (preferred || writableTextRows[0] || {}).fieldname || ""
}

async function saveAnnotation() {
  if (!encounter.value.name) {
    frappe.msgprint(__("A Patient Encounter is required before saving the drawing."))
    return
  }
  if (!excalidrawRef.value?.exportScene) {
    frappe.msgprint(__("The drawing surface is still loading."))
    return
  }
  annotationSaving.value = true
  try {
    const scene = await excalidrawRef.value.exportScene()
    if (!scene?.file_data) {
      frappe.msgprint(__("Draw something before saving the annotation."))
      return
    }
    const linkedProcedure = activeProcedure.value?.name || ""
	    await frappe.call({
	      method: "do_derma.api.save_derma_annotation",
	      args: {
	        payload: {
	          patient: patient.value.name,
	          encounter: encounter.value.name,
	          clinical_procedure: linkedProcedure,
	          doctype: linkedProcedure ? "Clinical Procedure" : "Patient Encounter",
	          docname: linkedProcedure || encounter.value.name,
	          annotation_template: "",
	          body_template: selectedBodyTemplate.value?.name,
	          body_template_title: selectedBodyTemplate.value?.title,
	          body_template_image: selectedBodyTemplate.value?.image,
	          annotation_type: "Free Drawing",
	          encounter_type: "Treatment",
	          json_text: scene.json_text,
	          file_data: scene.file_data,
	        },
      },
    })
    frappe.show_alert({ message: linkedProcedure ? __("Procedure drawing saved") : __("Encounter drawing saved"), indicator: "green" })
    await refresh()
  } finally {
    annotationSaving.value = false
  }
}

async function loadAnnotation(annotation) {
  if (!annotation) return
  data.value = { ...data.value, latest_annotation: annotation }
  await nextTick()
  excalidrawRef.value?.loadAnnotation?.(annotation)
}

async function openAnnotationHistory(annotation) {
  if (!annotation) return
  const preview = annotationPreview(annotation)
  frappe.msgprint({
    title: annotationTemplateLabel(annotation),
    message: `
      <div class="derma-annotation-preview-dialog">
        ${preview ? `<img src="${escapeHtml(preview)}" alt="">` : `<p>${__("No preview image available.")}</p>`}
        ${annotation.annotation_data ? `<div class="derma-annotation-preview-data">${annotation.annotation_data}</div>` : ""}
      </div>
    `,
    indicator: "blue",
  })
}

function annotationPreview(annotation) {
  return annotation?.image || annotation?.preview_image || annotation?.annotation_image || annotation?.file_url || ""
}

function annotationTemplateLabel(annotation) {
  return annotation?.annotation_template || annotation?.title || annotation?.name || __("Annotation")
}

async function carryForwardLatestAnnotation() {
  if (!latestAnnotation.value) return
  await loadAnnotation(latestAnnotation.value)
  frappe.show_alert({ message: __("Previous drawing loaded for review"), indicator: "blue" })
}

async function loadBodyTemplate(template = selectedBodyTemplate.value) {
  if (!template) return
  const isSameTemplate = selectedBodyTemplate.value?.name === template.name
  selectedBodyTemplate.value = template
  await nextTick()
  if (chartMode.value === "perio" && isSameTemplate) {
    refitChartAfterLayout()
  }
}

function toggleChartExpanded() {
  chartExpanded.value = !chartExpanded.value
}

async function refitChartAfterLayout() {
  await nextTick()
  window.setTimeout(() => excalidrawRef.value?.resetView?.(), 80)
  window.setTimeout(() => excalidrawRef.value?.resetView?.(), 260)
  window.setTimeout(() => excalidrawRef.value?.resetView?.(), 520)
}

async function setDefaultBodyTemplate(template) {
  const category = selectedTemplate.value?.custom_derma_category
  if (!category || !template?.name) {
    frappe.msgprint(__("Select a procedure and chart image before setting a default."))
    return
  }
  const response = await frappe.call({
    method: "do_derma.api.set_derma_category_default_template",
    args: { category, body_template: template.name },
  })
  const updatedCategory = response.message?.category || {}
  const updatedTemplate = response.message?.body_template || {}
  data.value = {
    ...data.value,
    categories: categories.value.map((row) =>
      row.name === category || row.title === category
        ? { ...row, default_body_template: template.name }
        : row
    ),
    body_templates: bodyTemplates.value.map((row) => {
      const defaults = new Set(row.default_for_categories || [])
      defaults.delete(category)
      if (row.name === template.name) defaults.add(category)
      return {
        ...row,
        ...(row.name === template.name ? updatedTemplate : {}),
        default_for_categories: [...defaults],
      }
    }),
    procedure_templates: procedureTemplates.value.map((row) =>
      row.custom_derma_category === category
        ? {
            ...row,
            derma_category_defaults: {
              ...(row.derma_category_defaults || {}),
              ...(updatedCategory || {}),
              default_body_template: template.name,
            },
          }
        : row
    ),
  }
  frappe.show_alert({ message: __("Default chart image updated"), indicator: "green" })
}

function openTemplateLibrary() {
  frappe.msgprint(__("Chart image administration should open in an in-page manager. For now, standard templates can be maintained from Derma Body Template setup."))
}

function newBodyTemplate({ gender, templateType } = {}) {
  frappe.msgprint(
    __("New chart image setup should be handled from the template manager. Suggested values: {0} / {1}.")
      .replace("{0}", gender || preferredTemplateGender())
      .replace("{1}", templateType || selectedBodyTemplate.value?.template_type || "Face")
  )
}

function openBodyTemplateDesigner(template = selectedBodyTemplate.value) {
  if (!template?.name) return
  frappe.msgprint({
    title: __("Chart Image"),
    message: `<p><b>${escapeHtml(template.title || template.name)}</b></p><p>${__("Region editing should open as an in-page manager in a later cleanup.")}</p>`,
    indicator: "blue",
  })
}

async function startAnnotationMode() {
  openAnnotationStudio()
}

function openAnnotationStudio() {
  if (!encounter.value.name) {
    frappe.msgprint(__("A Patient Encounter is required before saving annotation."))
    return
  }
  openDermaAnnotationStudio({
    context: {
      patient: patient.value.name,
      encounter: encounter.value.name,
      appointment: appointment.value.name || props.context?.appointment,
    },
    bodyTemplates: bodyTemplates.value,
    procedureTemplates: procedureTemplates.value,
    onSaved: async () => {
      await refresh()
    },
  })
}

async function loadAssessment(force = false) {
  if (!force && loadedTabs.assessment) return
  assessmentPanel.loading = true
  assessmentPanel.error = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_assessment", args: contextArgs() })
    const message = response.message || {}
    assessmentPanel.encounter = message.encounter || ""
    assessmentPanel.docstatus = message.docstatus
    assessmentPanel.layout = message.layout || []
    assessmentPanel.values = message.values || {}
    assessmentPanel.contextValues = message.context_values || {}
    assessmentPanel.editing = false
    loadedTabs.assessment = true
  } catch (error) {
    assessmentPanel.error = error?.message || __("Unable to load assessment.")
  } finally {
    assessmentPanel.loading = false
  }
}

async function saveAssessment(payload) {
  assessmentPanel.saving = true
  try {
    const response = await frappe.call({ method: "do_derma.api.set_derma_assessment", args: { ...contextArgs(), payload } })
    const message = response.message || {}
    assessmentPanel.encounter = message.encounter || assessmentPanel.encounter
    assessmentPanel.docstatus = message.docstatus
    assessmentPanel.layout = message.layout || assessmentPanel.layout
    assessmentPanel.values = message.values || {}
    assessmentPanel.contextValues = message.context_values || {}
    assessmentPanel.editing = false
    frappe.show_alert({ message: __("Assessment saved"), indicator: "green" })
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

async function saveAnesthesiaPanel(rows) {
  anesthesiaPanel.saving = true
  try {
    const response = await frappe.call({ method: "do_derma.api.set_derma_anesthesia", args: { ...contextArgs(), payload: rows } })
    anesthesiaPanel.encounter = response.message?.encounter || anesthesiaPanel.encounter
    anesthesiaPanel.rows = response.message?.anesthesia || []
    frappe.show_alert({ message: __("Anesthesia saved"), indicator: "green" })
  } finally {
    anesthesiaPanel.saving = false
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

function sessionBlockers() {
  return [
    ...inventoryBlockers.value.map((item) => ({
      title: item.product_name || item.product_item || __("Inventory"),
      detail: item.message,
    })),
    ...followupBlockers.value,
  ]
}

function showBlockers(blockers) {
  const message = blockers
    .slice(0, 6)
    .map((item) => `<li>${item.title}: ${item.detail || item.location || ""}</li>`)
    .join("")
  frappe.msgprint({
    title: __("Encounter Blockers"),
    message: `<p>${__("There are unresolved derma blockers.")}</p><ul>${message}</ul>`,
    indicator: "orange",
  })
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
  if (!encounter.value.name || completingSession.value) return
  const blockers = sessionBlockers()
  if (blockers.length) {
    showBlockers(blockers)
    return
  }
  completingSession.value = true
  try {
    const response = await frappe.call({
      method: "do_derma.api.complete_derma_session",
      args: contextArgs(),
    })
    const result = response.message || {}
    frappe.show_alert({
      message: result.encounter_submitted
        ? __("Encounter completed and submitted.")
        : __("Session billing synced."),
      indicator: "green",
    })
    await refresh()
  } catch (err) {
    frappe.msgprint({
      title: __("Unable to Complete Session"),
      message: err?.message || __("Something went wrong while completing this session."),
      indicator: "red",
    })
  } finally {
    completingSession.value = false
  }
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

  const allowed = String(selectedTemplate.value?.custom_derma_allowed_body_templates || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
  const gender = preferredTemplateGender()
  const genderMatch = (row) => row.gender === gender
  const categoryDefault = selectedTemplate.value?.derma_category_defaults?.default_body_template || categorySettings(selectedTemplate.value?.custom_derma_category)?.default_body_template
  selectedBodyTemplate.value =
    bodyTemplates.value.find((row) => row.name === categoryDefault && genderMatch(row)) ||
    bodyTemplates.value.find((row) => row.name === categoryDefault) ||
    bodyTemplates.value.find((row) => (allowed.includes(row.name) || allowed.includes(row.title)) && genderMatch(row)) ||
    bodyTemplates.value.find((row) => allowed.includes(row.name) || allowed.includes(row.title)) ||
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
    display_name: row.title || row.template_label || row.procedure_template || row.name,
    procedure: row.title || row.procedure_template,
    procedure_date: date,
    date,
    tooth: row.derma_category || row.custom_derma_category || row.procedure_template || "Derma",
    notes: row.notes || row.custom_derma_notes || row.derma_detail_text || "",
    surface_profile: "none",
    render_style: "derma",
  }
}

function applyProcedureToDraft(procedure) {
  const treatment = (procedure?.derma_treatments || [])[0] || {}
  const variables = parseProcedureVariables(treatment.variables_json)
  procedureDraft.notes = treatment.notes || procedure.notes || procedure.custom_derma_notes || procedureDraft.notes || ""
  procedureDraft.product_item = treatment.product_item || ""
  procedureDraft.product_name = treatment.product_name || ""
  procedureDraft.dose = treatment.dose || ""
  procedureDraft.lot_no = treatment.lot_no || ""
  procedureDraft.settings = treatment.settings || ""
  procedureDraft.variables = {
    ...(procedureDraft.variables || {}),
    ...variables,
  }
  if (treatment.body_view || treatment.body_region) {
    const template = bodyTemplates.value.find((row) => row.title === treatment.body_view || row.name === treatment.body_view || row.template_type === treatment.body_region)
    if (template) selectedBodyTemplate.value = template
  }
}

function parseProcedureVariables(value) {
  if (!value) return {}
  if (typeof value === "object") return value
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
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

function categoryColor(label = "") {
  const key = label.toLowerCase()
  if (key.includes("botox")) return "#2563eb"
  if (key.includes("filler")) return "#16a34a"
  if (key.includes("laser")) return "#dc2626"
  if (key.includes("biopsy")) return "#ca8a04"
  if (key.includes("lesion")) return "#ea580c"
  if (key.includes("pigment")) return "#92400e"
  if (key.includes("scar")) return "#7c3aed"
  return "#0f766e"
}
</script>

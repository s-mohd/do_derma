<template>
  <section class="procedure-panel" data-test="procedure-panel">
    <div class="procedure-primary-toolbar">
      <label class="history-search">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input
          v-model.trim="searchQuery"
          type="search"
          :placeholder="__('Search procedure, code, area, doctor, note')"
        />
      </label>

      <select v-model="sortKey" class="procedure-sort" data-test="procedure-sort" :aria-label="__('Sort')">
        <option value="newest">{{ __("Newest first") }}</option>
        <option value="oldest">{{ __("Oldest first") }}</option>
        <option value="tooth">{{ __("Area") }}</option>
        <option value="procedure">{{ __("Procedure A-Z") }}</option>
        <option value="price_desc">{{ __("Price high-low") }}</option>
        <option value="doctor">{{ __("Doctor") }}</option>
        <option value="status">{{ __("Status") }}</option>
      </select>

      <button
        type="button"
        class="ghost small filter-toggle-btn"
        data-test="procedure-filters-toggle"
        :class="{ active: advancedFiltersOpen || hasSecondaryFilters }"
        @click="advancedFiltersOpen = !advancedFiltersOpen"
      >
        <i class="fa-solid fa-filter"></i>
        <span>{{ __("Filters") }}</span>
        <span v-if="activeSecondaryFilterCount" class="filter-count">{{ activeSecondaryFilterCount }}</span>
      </button>

      <button v-if="hasActiveFilters" type="button" class="ghost small clear-filters-btn" @click="clearHistoryFilters">
        {{ __("Clear") }}
      </button>

      <div class="panel-actions">
        <Teleport defer to="#chart-section-actions">
          <button
            type="button"
            class="ghost small"
            data-test="procedure-copy-marks"
            :disabled="readOnly || !previousMarkCount"
            :title="previousMarkCount ? '' : __('This patient has no marks on an earlier visit.')"
            @click="emit('copy-marks')"
          >
            {{ __("Copy marks from last visit") }}
          </button>
          <button
            type="button"
            class="ghost small"
            data-test="procedure-new-consent"
            :disabled="readOnly || !totalCount"
            @click="emit('new-consent')"
          >
            {{ __("New Consent") }}
          </button>
          <button
            type="button"
            class="primary small"
            data-test="procedure-new"
            :disabled="readOnly"
            @click="emit('new-procedure')"
          >
            {{ __("New Procedure") }}
          </button>
        </Teleport>
        <span v-if="readOnly" class="chart-pill" data-tone="neutral">{{ __("Read only") }}</span>
        <span v-if="anesthesiaRecorded" class="chart-pill" data-tone="caution">{{ __("Anesthesia recorded") }}</span>
      </div>
    </div>

    <div class="status-filter-row">
      <button
        class="chart-pill"
        :aria-pressed="activeStatus === 'all' ? 'true' : 'false'"
        type="button"
        @click="setFilter('all')"
      >
        {{ __("All") }}
        <span v-if="allRows.length" class="pill-count">{{ allRows.length }}</span>
      </button>
      <button
        v-for="pill in statusPills"
        :key="pill.key"
        class="chart-pill"
        :aria-pressed="activeStatus === pill.key ? 'true' : 'false'"
        type="button"
        @click="setFilter(pill.key)"
      >
        {{ pill.label }}
        <span v-if="statusCounts[pill.key]" class="pill-count">{{ statusCounts[pill.key] }}</span>
      </button>
      <div class="attention-chips" aria-live="polite">
        <button
          v-for="chip in attentionChips"
          :key="chip.key"
          type="button"
          class="chart-pill"
          data-tone="caution"
          :data-test="`procedure-attention-${chip.key}`"
          :aria-pressed="isAttentionActive(chip.key) ? 'true' : 'false'"
          @click="toggleAttention(chip.key)"
        >
          {{ chip.label }}
          <span class="pill-count">{{ chip.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="advancedFiltersOpen" class="procedure-history-controls">
      <label class="history-filter-control">
        <span>{{ __("Area") }}</span>
        <select v-model="toothFilter">
          <option value="all">{{ __("All") }}</option>
          <option v-for="tooth in toothOptions" :key="tooth" :value="tooth">{{ tooth }}</option>
        </select>
      </label>
      <label class="history-filter-control">
        <span>{{ __("Doctor") }}</span>
        <select v-model="doctorFilter">
          <option value="all">{{ __("All") }}</option>
          <option v-for="doctor in doctorOptions" :key="doctor" :value="doctor">{{ doctor }}</option>
        </select>
      </label>
      <label class="history-filter-control">
        <span>{{ __("Date") }}</span>
        <select v-model="dateFilter">
          <option value="all">{{ __("All time") }}</option>
          <option value="today">{{ __("Today") }}</option>
          <option value="30">{{ __("Last 30 days") }}</option>
          <option value="90">{{ __("Last 90 days") }}</option>
          <option value="undated">{{ __("No date") }}</option>
        </select>
      </label>
      <label v-if="enableLabCases" class="history-filter-control" data-test="procedure-lab-filter">
        <span>{{ __("Lab") }}</span>
        <select v-model="labFilter">
          <option value="all">{{ __("All") }}</option>
          <option value="follow_up">{{ __("Follow-up") }}</option>
          <option value="linked">{{ __("Linked") }}</option>
          <option value="suggested">{{ __("Suggested") }}</option>
          <option value="missing">{{ __("Needs case") }}</option>
          <option value="ready">{{ __("Ready") }}</option>
          <option value="overdue">{{ __("Overdue") }}</option>
        </select>
      </label>
      <label class="history-filter-control">
        <span>{{ __("Notes") }}</span>
        <select v-model="noteFilter">
          <option value="all">{{ __("All") }}</option>
          <option value="has_note">{{ __("Has note") }}</option>
          <option value="missing_note">{{ __("Missing note") }}</option>
        </select>
      </label>
      <label class="history-filter-control">
        <span>{{ __("Billing") }}</span>
        <select v-model="billingFilter">
          <option value="all">{{ __("All") }}</option>
          <option value="review">{{ __("Needs review") }}</option>
          <option value="override">{{ __("Override") }}</option>
          <option value="no_charge">{{ __("No charge") }}</option>
          <option value="insurance">{{ __("Insurance") }}</option>
          <option value="billable">{{ __("Billable") }}</option>
        </select>
      </label>
    </div>

    <div
      class="procedure-table-wrapper"
      v-if="filteredGroups.length"
      ref="tableWrapperEl"
      @scroll.passive="handleHistoryScroll"
    >
      <table class="procedure-table">
        <colgroup>
          <col class="col-status" />
          <col class="col-procedure" />
          <col class="col-details" />
          <col class="col-price" />
          <col class="col-doctor" />
          <col class="col-actions" />
        </colgroup>
        <thead>
          <tr>
            <th>{{ __("Status") }}</th>
            <th>{{ __("Procedure") }}</th>
            <th>{{ __("Details") }}</th>
            <th>{{ __("Price") }}</th>
            <th>{{ __("Doctor") }}</th>
            <th>{{ __("Actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="group in filteredGroups" :key="group.key">
            <tr class="procedure-date-row">
              <td colspan="6">{{ formatGroupLabel(group) }}</td>
            </tr>
            <template v-for="row in group.items" :key="row.name">
            <tr @dblclick="handleRowDoubleClick(row, $event)">
              <td class="status-cell">
                <div class="cell-stack">
                  <span class="chart-pill" :data-tone="statusTone(row.status)">
                    {{ row.status || "Draft" }}
                  </span>
                  <button
                    v-if="row.consents?.length"
                    type="button"
                    class="chart-pill"
                    data-tone="ok"
                    data-test="procedure-consent-badge"
                    @click.stop="emit('open-consents', row)"
                  >
                    {{ consentBadgeLabel(row.consents) }}
                  </button>
                  <button
                    v-else-if="row.consent_required && row.docstatus !== 2"
                    type="button"
                    class="chart-pill"
                    data-tone="danger"
                    data-test="procedure-consent-needed"
                    :disabled="readOnly"
                    @click.stop="emit('new-consent', row)"
                  >
                    {{ __("Consent needed") }}
                  </button>
                </div>
              </td>
              <td class="procedure-cell">
                <div class="cell-stack">
                  <button
                    v-if="getProcedureName(row)"
                    type="button"
                    class="procedure-open-link"
                    :title="__('Open Clinical Procedure')"
                    @click.stop="openProcedure(row)"
                  >
                    {{ row.display_name || row.procedure_template || "-" }}
                  </button>
                  <span v-else>{{ row.display_name || row.procedure_template || "-" }}</span>
                  <span v-if="getProcedureMeta(row)" class="procedure-meta">{{ getProcedureMeta(row) }}</span>
                </div>
              </td>
              <td>
                <div class="details-cell">
                  <button
                    v-if="row.derma_detail_text"
                    type="button"
                    class="chart-pill detail-text"
                    data-tone="accent"
                    :title="row.derma_detail_text"
                    @click.stop="openProcedure(row)"
                  >
                    <i class="fa-solid fa-notes-medical"></i>
                    <span>{{ row.derma_detail_text }}</span>
                  </button>
                  <button
                    v-else-if="enableLabCases && rowAllowsSurfaces(row)"
                    type="button"
                    class="chart-pill"
                    data-test="procedure-edit-surfaces"
                    :disabled="!isEditable(row)"
                    @click="isEditable(row) ? $emit('edit-surfaces', row) : null"
                  >
                    <i class="fa-solid fa-layer-group"></i>
                    <span>{{ formatSurfaceText(row) || __("Details") }}</span>
                  </button>
                  <span v-else class="chart-pill detail-empty">
                    <i class="fa-solid fa-layer-group"></i>
                    <span>{{ __("No details") }}</span>
                  </span>

                  <template v-if="enableLabCases && row.lab_case_name">
                    <button
                      class="chart-pill"
                      :data-tone="labCaseTone(row.lab_case_status)"
                      type="button"
                      data-test="procedure-open-lab-case"
                      @click="$emit('open-lab-case', row)"
                    >
                      <i class="fa-solid fa-flask"></i>
                      <span>{{ row.lab_case_status || __("Lab linked") }}</span>
                    </button>
                  </template>
                  <template v-else-if="enableLabCases && row.lab_case_recommended && isEditable(row)">
                    <button
                      class="chart-pill"
                      data-tone="caution"
                      type="button"
                      data-test="procedure-create-lab-case"
                      @click="$emit('create-lab-case', row)"
                    >
                      <i class="fa-solid fa-flask"></i>
                      <span>{{ __("Create lab") }}</span>
                    </button>
                  </template>

                  <span v-if="rowIsInsurance(row)" class="chart-pill" data-tone="info">
                    <i class="fa-solid fa-shield-halved"></i>
                    <span>{{ __("Insurance") }}</span>
                  </span>
                  <button
                    v-if="consumableOwners(row).length"
                    type="button"
                    class="chart-pill"
                    data-test="procedure-toggle-consumables"
                    :aria-expanded="isConsumablesOpen(row)"
                    :title="__('Materials consumed')"
                    @click.stop="toggleConsumables(row)"
                  >
                    <i class="fa-solid fa-box-open"></i>
                    <span>{{ __("Materials") }} ({{ consumableCount(row) }})</span>
                  </button>
                  <!-- Offered even when empty: the studio only records these alongside a
                       drawing, so a procedure that needs no drawing has no other way in. -->
                  <button
                    v-if="row.derma_captures_variables_per_procedure"
                    type="button"
                    class="chart-pill"
                    data-test="procedure-edit-variables"
                    :title="__('Recorded once for the whole procedure')"
                    :disabled="readOnly"
                    @click.stop="$emit('edit-procedure-variables', row)"
                  >
                    <i class="fa-solid fa-sliders"></i>
                    <span>{{ row.derma_procedure_variables_text || __("Add details") }}</span>
                  </button>
                  <span v-if="row.derma_artifact_text" class="chart-pill" data-tone="info">
                    <i class="fa-regular fa-images"></i>
                    <span>{{ row.derma_artifact_text }}</span>
                  </span>
                </div>
              </td>
              <td class="price-cell">
                <div class="price-stack">
                  <div v-if="isEditable(row) && !rowIsInsurance(row)" class="override-picker" @keydown.escape.stop="closeOverrideList">
                    <button
                      type="button"
                      class="price-trigger"
                      data-test="procedure-price"
                      :data-row="row.name"
                      :aria-expanded="overrideListOpenRow === row.name ? 'true' : 'false'"
                      :aria-controls="`price-editor-${row.name}`"
                      :title="__('Change price')"
                      @click.stop="overrideListOpenRow === row.name ? closeOverrideList() : openOverrideList(row)"
                    >
                      {{ formatCurrency(displayPrice(row)) || "—" }}
                    </button>
                    <div v-if="overrideListOpenRow === row.name" :id="`price-editor-${row.name}`" class="override-popover">
                      <input
                        type="number"
                        class="inline-input"
                        :placeholder="__('Override')"
                        :value="edits[row.name]?.price ?? row.price_override ?? ''"
                        @change="updatePriceManual(row, $event.target.value)"
                        @keydown.enter.prevent="closeOverrideList(); $event.target.blur()"
                      />
                      <button
                        v-for="pl in getPriceListOptions(row)"
                        :key="pl"
                        type="button"
                        class="override-option"
                        @mousedown.prevent="setOverrideFromPriceList(row, pl)"
                      >
                        {{ pl }}
                      </button>
                      <div class="override-popover-footer">
                        <button
                          type="button"
                          class="ghost small no-charge-btn"
                          :title="__('Mark as no charge')"
                          @click.stop="closeOverrideList(); markNoCharge(row)"
                        >
                          {{ __("No charge") }}
                        </button>
                        <button
                          v-if="hasAnyOverride(row)"
                          type="button"
                          class="ghost small reset-btn"
                          :title="__('Clear override')"
                          @click.stop="closeOverrideList(); clearPriceOverride(row)"
                        >
                          {{ __("Reset") }}
                        </button>
                      </div>
                    </div>
                  </div>
                  <span v-else class="price-amount">{{ formatCurrency(displayPrice(row)) || "—" }}</span>
                  <span v-if="displayPriceList(row)" class="price-meta">{{ displayPriceList(row) }}</span>
                  <span v-if="isNoCharge(row)" class="chart-pill" data-tone="neutral">{{ __("No charge") }}</span>
                  <span v-else-if="hasAnyOverride(row)" class="chart-pill" data-tone="caution">{{ __("Override") }}</span>
                  <span
                    v-if="isRowSaving(row)"
                    class="chart-spinner"
                    role="status"
                    data-test="procedure-row-saving"
                    :aria-label="__('Saving the price')"
                  ></span>
                </div>
              </td>
              <td>{{ row.practitioner_name || row.practitioner || "—" }}</td>
              <td class="row-actions">
                <button
                  v-if="isEditable(row) || getRowNoteRawValue(row)"
                  class="icon-btn"
                  type="button"
                  data-test="procedure-note"
                  :title="getRowNoteRawValue(row) ? undefined : noteLabel(row)"
                  :aria-label="noteLabel(row)"
                  :aria-describedby="notePreview?.row === row.name ? 'procedure-note-preview' : undefined"
                  @click.stop="hideNotePreview(); openProcedureNoteDialog(row)"
                  @mouseenter="showNotePreview(row, $event)"
                  @focus="showNotePreview(row, $event)"
                  @mouseleave="hideNotePreview"
                  @blur="hideNotePreview"
                  @keydown.escape="hideNotePreview"
                >
                  <i :class="isEditable(row) ? 'fa-regular fa-note-sticky' : 'fa-regular fa-eye'"></i>
                  <span v-if="getRowNoteRawValue(row)" class="note-dot"></span>
                </button>
                <button
                  v-if="getProcedureName(row)"
                  class="icon-btn"
                  type="button"
                  data-test="procedure-annotate"
                  :disabled="readOnly || Number(row.docstatus || 0) > 0"
                  :title="annotateLabel(row)"
                  :aria-label="annotateLabel(row)"
                  @click="$emit('annotate-procedure', row)"
                >
                  <i class="fa-regular fa-pen-to-square"></i>
                  <span v-if="Number(row.annotation_count || 0)" class="icon-badge">{{ row.annotation_count }}</span>
                </button>
                <button
                  v-if="canReopen && !readOnly && Number(row.docstatus || 0) === 1"
                  class="icon-btn"
                  type="button"
                  data-test="procedure-reopen"
                  :disabled="Boolean(row.submitted_invoice)"
                  :title="row.submitted_invoice ? __('Billed on {0}. Cancel the invoice before reopening.').replace('{0}', row.submitted_invoice) : __('Reopen procedure')"
                  :aria-label="__('Reopen procedure')"
                  @click="$emit('reopen-procedure', row)"
                >
                  <i class="fa-solid fa-lock-open"></i>
                </button>
                <button
                  v-if="isEditable(row)"
                  class="icon-btn danger"
                  type="button"
                  data-test="procedure-delete"
                  :title="__('Delete procedure')"
                  :aria-label="__('Delete procedure')"
                  @click="deleteRow(row)"
                >
                  <i class="fa-regular fa-trash-can"></i>
                </button>
                <span v-if="!getProcedureName(row) && !isEditable(row)" class="text-muted">—</span>
              </td>
            </tr>
            <tr v-if="isConsumablesOpen(row)" class="consumables-row" data-test="procedure-consumables-row">
              <td colspan="6">
                <ConsumablesEditor
                  v-for="owner in consumableOwners(row)"
                  :key="owner.name"
                  :owner-doctype="owner.doctype"
                  :owner-name="owner.name"
                  :label="owner.label"
                  :rows="consumablesOf(owner.source).consumables"
                  :removed="consumablesOf(owner.source).removed_consumables"
                  :defaults="consumablesOf(owner.source).default_consumables"
                  :read-only="readOnly || !owner.editable"
                  :saving="!!savingConsumables[owner.name]"
                  :error="consumableErrors[owner.name] || ''"
                  @change="saveConsumables(owner, $event)"
                />
              </td>
            </tr>
            </template>
          </template>
        </tbody>
      </table>
      <div class="procedure-load-more-row" v-if="totalFilteredRows > 0">
        <span class="text-muted">{{ displayedRows }} / {{ totalFilteredRows }} procedures</span>
        <div class="load-controls">
          <button v-if="hasMoreRows" class="ghost small" type="button" @click="loadMoreRows">
            {{ __("Load more") }}
          </button>
          <label class="history-load-selector">
            <span>{{ __("Load") }}</span>
            <select v-model.number="rowBatchSize">
              <option v-for="size in ROW_BATCH_OPTIONS" :key="size" :value="size">{{ size }}</option>
            </select>
          </label>
        </div>
      </div>
    </div>

    <div v-else class="procedure-empty">
      <strong>{{ emptyStateTitle }}</strong>
      <span>{{ emptyStateMessage }}</span>
      <button v-if="hasActiveFilters" type="button" class="ghost small" @click="clearHistoryFilters">
        {{ __("Clear filters") }}
      </button>
    </div>

    <div
      v-if="notePreview"
      id="procedure-note-preview"
      class="note-preview"
      role="tooltip"
      data-test="procedure-note-preview"
      :style="notePreviewStyle"
    >
      <span class="chart-label">{{ notePreview.title }}</span>
      <p>{{ notePreview.text }}</p>
    </div>

    <div v-if="enableBillingSync" class="invoice-footer">
      <button
        type="button"
        class="invoice-btn ghost"
        data-test="procedure-sync-billables"
        :class="{ disabled: syncDisabled || readOnly }"
        :disabled="syncDisabled || readOnly"
        @click="$emit('sync-billables')"
      >
        {{ __("Sync Billables") }} ({{ totalCount }})
      </button>
    </div>

  </section>
</template>

<script setup>
import { computed, ref, onBeforeUnmount, onMounted, watch, nextTick } from "vue"
import ConsumablesEditor from "./consumables/ConsumablesEditor.vue"
import { procedureDisplayName } from "../../shared/procedure_label.js"
import { nameDialogControls } from "../../shared/dialog_a11y.js"
import { runDialogAction } from "../../shared/dialog_progress.js"
import { htmlToPlainText, serverErrorText } from "../../shared/error_text.js"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  statusPills: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  totalCount: { type: Number, default: 0 },
  doctorName: { type: String, default: "" },
  priceLists: { type: Array, default: () => [] },
  defaultPriceList: { type: String, default: "" },
  syncDisabled: { type: Boolean, default: false },
  anesthesiaRecorded: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
  previousMarkCount: { type: Number, default: 0 },
  enableLabCases: { type: Boolean, default: false },
  enableBillingSync: { type: Boolean, default: false },
  canReopen: { type: Boolean, default: false },
})

const emit = defineEmits([
  "refresh",
  "sync-billables",
  "annotate-procedure",
  "edit-procedure-variables",
  "new-procedure",
  "copy-marks",
  "edit-surfaces",
  "create-lab-case",
  "open-lab-case",
  "reopen-procedure",
  "new-consent",
  "open-consents",
])

const advancedFiltersOpen = ref(false)
const activeStatus = ref("all")
const searchQuery = ref("")
const toothFilter = ref("all")
const doctorFilter = ref("all")
const dateFilter = ref("all")
const labFilter = ref("all")
const noteFilter = ref("all")
const billingFilter = ref("all")
const sortKey = ref("newest")
const CUSTOM_PRICE_LIST = "Custom"
const ROW_BATCH_OPTIONS = [20, 50, 100]
const rowBatchSize = ref(50)
const loadedRowsCount = ref(rowBatchSize.value)
const tableWrapperEl = ref(null)

const STATUS_TONES = {
  Draft: "neutral",
  Pending: "caution",
  "In Progress": "caution",
  Submitted: "info",
  Completed: "ok",
  Cancelled: "danger",
}

function buildGroupView(group, items = []) {
  const hasLabCaseColumn = items.some((row) => !!row.lab_case_name || !!row.lab_case_recommended)
  const hasDraft = items.some((row) => isEditable(row))
  const hasOverrideColumn =
    hasDraft ||
    items.some((row) => hasAnyOverride(row))
  const showActions = items.some((row) => isEditable(row))
  return { ...group, items, hasLabCaseColumn, hasOverrideColumn, showActions }
}

function normalizeTooth(value) {
  return String(value || "").trim()
}

function formatToothLabel(value) {
  const tooth = normalizeTooth(value)
  if (!tooth) return "—"
  return tooth === "Full Mouth" ? tooth : tooth.replace(/^Tooth\s+/i, "")
}

function compareToothLabels(a, b) {
  const left = Number(a)
  const right = Number(b)
  if (Number.isFinite(left) && Number.isFinite(right)) return left - right
  if (Number.isFinite(left)) return -1
  if (Number.isFinite(right)) return 1
  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

function getProcedureMeta(row) {
  const area = normalizeTooth(row?.tooth) ? formatToothLabel(row.tooth) : ""
  return [row?.procedure_code, area].filter(Boolean).join(" · ")
}

function getDoctorLabel(row) {
  return String(row?.practitioner_name || row?.practitioner || "").trim()
}

function getProcedureLabel(row) {
  return String(row?.display_name || row?.procedure_template || row?.procedure || row?.name || "").trim()
}

function getRowDateValue(row) {
  return row?.procedure_date || row?.start_date || row?.date || ""
}

function getRowTimestamp(row) {
  const dateValue = getRowDateValue(row)
  if (!dateValue) return null
  const timeValue = row?.procedure_time || row?.time || row?.start_time || "00:00:00"
  const normalizedDate = String(dateValue).includes("T") ? String(dateValue) : `${dateValue}T${timeValue}`
  const parsed = Date.parse(normalizedDate)
  return Number.isFinite(parsed) ? parsed : null
}

function todayDateString() {
  const now = new Date()
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-")
}

function rowMatchesDateFilter(row) {
  if (dateFilter.value === "all") return true
  const dateValue = getRowDateValue(row)
  if (dateFilter.value === "undated") return !dateValue
  if (!dateValue) return false
  const rowDate = String(dateValue).slice(0, 10)
  if (dateFilter.value === "today") return rowDate === todayDateString()
  const days = Number(dateFilter.value)
  if (!Number.isFinite(days)) return true
  const timestamp = getRowTimestamp(row)
  if (timestamp === null) return false
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  start.setDate(start.getDate() - days + 1)
  return timestamp >= start.getTime()
}

function rowNeedsLabFollowUp(row) {
  const status = String(row?.lab_case_status || "").toLowerCase()
  if (Number(row?.lab_case_overdue || row?.is_lab_case_overdue || 0)) return true
  if (["ready for delivery", "quality checked", "received in clinic"].includes(status)) return true
  return Boolean(row?.lab_case_recommended && !row?.lab_case_name)
}

function rowNeedsBillingReview(row) {
  return hasAnyOverride(row) || rowIsInsurance(row)
}

function rowMatchesLabFilter(row) {
  if (labFilter.value === "all") return true
  if (labFilter.value === "follow_up") return rowNeedsLabFollowUp(row)
  const status = String(row?.lab_case_status || "").toLowerCase()
  if (labFilter.value === "linked") return Boolean(row?.lab_case_name)
  if (labFilter.value === "suggested") return Boolean(row?.lab_case_recommended)
  if (labFilter.value === "missing") return Boolean(row?.lab_case_recommended && !row?.lab_case_name)
  if (labFilter.value === "ready") return ["ready for delivery", "quality checked", "received in clinic"].includes(status)
  if (labFilter.value === "overdue") return Boolean(Number(row?.lab_case_overdue || row?.is_lab_case_overdue || 0))
  return true
}

function rowMatchesBillingFilter(row) {
  if (billingFilter.value === "all") return true
  if (billingFilter.value === "review") return rowNeedsBillingReview(row)
  if (billingFilter.value === "override") return hasAnyOverride(row) && !isNoCharge(row)
  if (billingFilter.value === "no_charge") return isNoCharge(row)
  if (billingFilter.value === "insurance") return rowIsInsurance(row)
  if (billingFilter.value === "billable") return Number(computedPrice(row) || 0) > 0 && !isNoCharge(row)
  return true
}

function rowMatchesSearch(row) {
  const query = searchQuery.value.toLowerCase()
  if (!query) return true
  const haystack = [
    getProcedureLabel(row),
    row?.procedure_code,
    row?.procedure_template,
    row?.status,
    row?.tooth,
    row?.derma_detail_text,
    row?.derma_artifact_text,
    formatSurfaceText(row),
    getDoctorLabel(row),
    row?.lab_case_name,
    row?.lab_case_status,
    getRowNoteValue(row),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
  return haystack.includes(query)
}

function rowMatchesFilters(row) {
  if (activeStatus.value !== "all") {
    const target = activeStatus.value.toLowerCase()
    if ((row?.status || "").toString().toLowerCase() !== target) return false
  }
  if (toothFilter.value !== "all" && normalizeTooth(row?.tooth) !== toothFilter.value) return false
  if (doctorFilter.value !== "all" && getDoctorLabel(row) !== doctorFilter.value) return false
  if (noteFilter.value === "has_note" && !getRowNoteRawValue(row)) return false
  if (noteFilter.value === "missing_note" && getRowNoteRawValue(row)) return false
  return rowMatchesSearch(row) && rowMatchesDateFilter(row) && rowMatchesLabFilter(row) && rowMatchesBillingFilter(row)
}

function sortRows(rows = []) {
  const copy = [...rows]
  const direction = sortKey.value === "oldest" ? 1 : -1
  if (["newest", "oldest"].includes(sortKey.value)) {
    return copy.sort((a, b) => {
      const left = getRowTimestamp(a)
      const right = getRowTimestamp(b)
      if (left === null && right === null) return 0
      if (left === null) return 1
      if (right === null) return -1
      return direction * (left - right)
    })
  }
  if (sortKey.value === "tooth") {
    return copy.sort((a, b) => compareToothLabels(normalizeTooth(a?.tooth), normalizeTooth(b?.tooth)))
  }
  if (sortKey.value === "procedure") {
    return copy.sort((a, b) => getProcedureLabel(a).localeCompare(getProcedureLabel(b)))
  }
  if (sortKey.value === "price_desc") {
    return copy.sort((a, b) => Number(computedPrice(b) || 0) - Number(computedPrice(a) || 0))
  }
  if (sortKey.value === "doctor") {
    return copy.sort((a, b) => getDoctorLabel(a).localeCompare(getDoctorLabel(b)))
  }
  if (sortKey.value === "status") {
    return copy.sort((a, b) => String(a?.status || "").localeCompare(String(b?.status || "")))
  }
  return copy
}

function sortGroups(groups = []) {
  const copy = [...groups]
  if (sortKey.value === "oldest") {
    return copy.sort((a, b) => {
      if (a.timestamp === null && b.timestamp === null) return 0
      if (a.timestamp === null) return 1
      if (b.timestamp === null) return -1
      return a.timestamp - b.timestamp
    })
  }
  return copy.sort((a, b) => {
    if (a.timestamp === null && b.timestamp === null) return 0
    if (a.timestamp === null) return 1
    if (b.timestamp === null) return -1
    return b.timestamp - a.timestamp
  })
}

const allRows = computed(() =>
  (props.groups || []).flatMap((group) => group.items || [])
)

const toothOptions = computed(() => {
  const values = new Set()
  for (const row of allRows.value) {
    const tooth = normalizeTooth(row?.tooth)
    if (tooth) values.add(tooth)
  }
  return Array.from(values).sort(compareToothLabels)
})

const doctorOptions = computed(() => {
  const values = new Set()
  for (const row of allRows.value) {
    const doctor = getDoctorLabel(row)
    if (doctor) values.add(doctor)
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b))
})

const hasActiveFilters = computed(() =>
  Boolean(
    searchQuery.value ||
      activeStatus.value !== "all" ||
      toothFilter.value !== "all" ||
      doctorFilter.value !== "all" ||
      dateFilter.value !== "all" ||
      labFilter.value !== "all" ||
      noteFilter.value !== "all" ||
      billingFilter.value !== "all" ||
      sortKey.value !== "newest"
  )
)

const activeSecondaryFilterCount = computed(() => {
  let count = 0
  if (toothFilter.value !== "all") count += 1
  if (doctorFilter.value !== "all") count += 1
  if (dateFilter.value !== "all") count += 1
  if (labFilter.value !== "all") count += 1
  if (noteFilter.value !== "all") count += 1
  if (billingFilter.value !== "all") count += 1
  return count
})

const hasSecondaryFilters = computed(() => activeSecondaryFilterCount.value > 0)

const allFilteredGroups = computed(() => {
  const sourceGroups = props.groups || []
  return sortGroups(
    sourceGroups
    .map((group) => {
      const items = sortRows((group.items || []).filter(rowMatchesFilters))
      return buildGroupView(group, items)
    })
    .filter((group) => group.items.length)
  )
})

const totalFilteredRows = computed(() =>
  allFilteredGroups.value.reduce((sum, group) => sum + (group.items?.length || 0), 0)
)

const filteredGroups = computed(() => {
  let remaining = Math.max(0, loadedRowsCount.value)
  const visible = []
  for (const group of allFilteredGroups.value) {
    if (remaining <= 0) break
    const allItems = group.items || []
    const items = allItems.slice(0, remaining)
    remaining -= items.length
    if (items.length) {
      visible.push(buildGroupView(group, items))
    }
  }
  return visible
})

const displayedRows = computed(() =>
  filteredGroups.value.reduce((sum, group) => sum + (group.items?.length || 0), 0)
)

const hasMoreRows = computed(() => displayedRows.value < totalFilteredRows.value)

const filteredRows = computed(() =>
  allFilteredGroups.value.flatMap((group) => group.items || [])
)

const historyStats = computed(() => {
  const stats = {
    missingNotes: 0,
    labFollowUp: 0,
    billingReview: 0,
  }
  for (const row of filteredRows.value) {
    const missingNote = !getRowNoteRawValue(row)
    const labFollowUp = rowNeedsLabFollowUp(row)
    if (missingNote) stats.missingNotes += 1
    if (labFollowUp) stats.labFollowUp += 1
    if (rowNeedsBillingReview(row)) stats.billingReview += 1
  }
  return stats
})

const ATTENTION_FILTERS = {
  note: { filter: noteFilter, value: "missing_note", stat: "missingNotes", label: __("Missing notes") },
  billing: { filter: billingFilter, value: "review", stat: "billingReview", label: __("Billing review") },
  lab: { filter: labFilter, value: "follow_up", stat: "labFollowUp", label: __("Lab follow-up") },
}

const statusCounts = computed(() => {
  const counts = {}
  for (const row of allRows.value) {
    const status = row?.status || "Draft"
    counts[status] = (counts[status] || 0) + 1
  }
  return counts
})

function isAttentionActive(key) {
  const { filter, value } = ATTENTION_FILTERS[key]
  return filter.value === value
}

// An active chip stays visible at zero so its filter can still be cleared from here.
const attentionChips = computed(() =>
  Object.entries(ATTENTION_FILTERS)
    .filter(([key]) => key !== "lab" || props.enableLabCases)
    // A select narrowed to another value already owns that dimension; the chip would widen it.
    .filter(([key, config]) => config.filter.value === "all" || isAttentionActive(key))
    .map(([key, config]) => ({ key, count: historyStats.value[config.stat], label: config.label }))
    .filter((chip) => chip.count > 0 || isAttentionActive(chip.key))
)

function toggleAttention(key) {
  const { filter, value } = ATTENTION_FILTERS[key]
  filter.value = isAttentionActive(key) ? "all" : value
  loadedRowsCount.value = rowBatchSize.value
}

const emptyStateTitle = computed(() =>
  allRows.value.length > 0 && hasActiveFilters.value ? __("No matching procedures") : __("No procedures added yet")
)

// The list holds this visit only; earlier visits live on the Review timeline.
const emptyStateMessage = computed(() =>
  allRows.value.length > 0 && hasActiveFilters.value
    ? __("Adjust or clear the filters to bring this visit's procedures back into view.")
    : __("Procedures recorded on this visit appear here. Earlier visits are on the Review timeline.")
)

function setFilter(status) {
  activeStatus.value = status
  loadedRowsCount.value = rowBatchSize.value
  if (tableWrapperEl.value) tableWrapperEl.value.scrollTop = 0
  nextTick(() => ensureViewportFilled())
}

function loadMoreRows() {
  if (!hasMoreRows.value) return
  loadedRowsCount.value += rowBatchSize.value
}

function clearHistoryFilters() {
  searchQuery.value = ""
  activeStatus.value = "all"
  toothFilter.value = "all"
  doctorFilter.value = "all"
  dateFilter.value = "all"
  labFilter.value = "all"
  noteFilter.value = "all"
  billingFilter.value = "all"
  sortKey.value = "newest"
  loadedRowsCount.value = rowBatchSize.value
  if (tableWrapperEl.value) tableWrapperEl.value.scrollTop = 0
  nextTick(() => ensureViewportFilled())
}

function handleHistoryScroll(event) {
  if (!hasMoreRows.value) return
  const el = event?.target
  if (!el) return
  const threshold = 96
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - threshold) {
    loadMoreRows()
  }
}

async function ensureViewportFilled() {
  const el = tableWrapperEl.value
  if (!el) return
  let guard = 0
  while (hasMoreRows.value && guard < 12 && el.scrollHeight <= el.clientHeight + 4) {
    loadMoreRows()
    guard += 1
    await nextTick()
  }
}

watch(rowBatchSize, async (value) => {
  loadedRowsCount.value = value
  await nextTick()
  if (tableWrapperEl.value) tableWrapperEl.value.scrollTop = 0
  ensureViewportFilled()
})

watch(
  () => props.groups,
  async () => {
    loadedRowsCount.value = rowBatchSize.value
    await nextTick()
    if (tableWrapperEl.value) tableWrapperEl.value.scrollTop = 0
    ensureViewportFilled()
  }
)

watch(
  [searchQuery, toothFilter, doctorFilter, dateFilter, labFilter, noteFilter, billingFilter, sortKey],
  async () => {
    loadedRowsCount.value = rowBatchSize.value
    await nextTick()
    if (tableWrapperEl.value) tableWrapperEl.value.scrollTop = 0
    ensureViewportFilled()
  }
)

onMounted(() => {
  nextTick(() => ensureViewportFilled())
  // The card is pinned to the viewport, so any scroll would leave it beside the wrong row.
  window.addEventListener("scroll", hideNotePreview, true)
})

const NOTE_PREVIEW_DELAY_MS = 250
const NOTE_PREVIEW_GAP_PX = 8
const notePreview = ref(null)
let notePreviewTimer = null

function showNotePreview(row, event) {
  const text = getRowNoteValue(row)
  if (!text) return
  const anchor = event.currentTarget.getBoundingClientRect()
  const delay = event.type === "focus" ? 0 : NOTE_PREVIEW_DELAY_MS
  clearTimeout(notePreviewTimer)
  notePreviewTimer = setTimeout(() => {
    notePreview.value = { row: row.name, title: getProcedureLabel(row), text, anchor }
  }, delay)
}

function hideNotePreview() {
  clearTimeout(notePreviewTimer)
  notePreview.value = null
}

// Opens to the left of the icon, and upward in the lower half so it never runs off the window.
const notePreviewStyle = computed(() => {
  const anchor = notePreview.value?.anchor
  if (!anchor) return {}
  const style = { right: `${window.innerWidth - anchor.left + NOTE_PREVIEW_GAP_PX}px` }
  if (anchor.top > window.innerHeight / 2) {
    style.bottom = `${window.innerHeight - anchor.bottom}px`
  } else {
    style.top = `${anchor.top}px`
  }
  return style
})

const edits = ref({})
const overrideListOpenRow = ref(null)
let overrideOutsideHandler = null

function getEditValue(row, key) {
  return edits.value[row.name]?.[key]
}

/** "Consented" when any consent was signed; waived-only coverage says so. */
function consentBadgeLabel(consents) {
  const isWaivedOnly = consents.every((consent) => consent.custom_derma_signature_waived)
  const label = isWaivedOnly ? __("Consent waived") : __("Consented")
  return consents.length > 1 ? `${label} (${consents.length})` : label
}

function isEditable(row) {
  if (props.readOnly) return false
  if (Number(row?.docstatus || 0) > 0) return false
  const status = (row.status || "").toLowerCase()
  return !["submitted", "completed", "cancelled"].includes(status)
}

function isPersistedRow(row) {
  const name = row?.name
  return Boolean(name) && !String(name).startsWith("local-")
}

function computedPrice(row) {
  if (row.base_rate !== undefined && row.base_rate !== null) return row.base_rate
  if (row.base_price !== undefined && row.base_price !== null) return row.base_price
  return ""
}

function displayPrice(row) {
  if (getEditValue(row, "price") !== undefined) return getEditValue(row, "price")
  if (row.price_override !== null && row.price_override !== undefined) return row.price_override
  if (row.display_price !== undefined && row.display_price !== null) return row.display_price
  if (row.base_rate !== undefined && row.base_rate !== null) return row.base_rate
  if (row.base_price !== undefined && row.base_price !== null) return row.base_price
  return ""
}

// Consumables belong to the mark, not to the procedure row that shows them. The server
// decides what counts as a deviation from the template; nothing here recomputes it.
const expandedConsumables = ref({})
const consumablesByOwner = ref({})
const consumableErrors = ref({})
const savingConsumables = ref({})
// Which procedure rows have a price, no-charge or note write in flight.
const savingRows = ref({})

watch(
  () => props.groups,
  () => {
    consumablesByOwner.value = {}
    consumableErrors.value = {}
  }
)

function marksOf(row) {
  return row?.derma_marks || []
}

function consumablesOf(owner) {
  return (
    consumablesByOwner.value[owner?.name] || {
      consumables: owner?.consumables || [],
      removed_consumables: owner?.removed_consumables || [],
      default_consumables: owner?.default_consumables || [],
    }
  )
}

// A procedure records its materials on its annotations when it has any, and on itself when
// it has none, so exactly one owner is ever on screen for a row.
function consumableOwners(row) {
  const marks = marksOf(row)
  if (marks.length) {
    return marks.map((mark) => ({
      doctype: "Derma Chart Mark",
      name: mark.name,
      label: markConsumablesLabel(mark),
      source: mark,
      editable: isEditable(row),
    }))
  }
  if (!isPersistedRow(row)) return []
  return [
    {
      doctype: "Clinical Procedure",
      name: row.name,
      label: procedureDisplayName(row),
      source: row,
      editable: isEditable(row),
    },
  ]
}

function consumableCount(row) {
  return consumableOwners(row).reduce(
    (total, owner) => total + consumablesOf(owner.source).consumables.length,
    0
  )
}

function isConsumablesOpen(row) {
  return !!expandedConsumables.value[row.name]
}

function toggleConsumables(row) {
  expandedConsumables.value = {
    ...expandedConsumables.value,
    [row.name]: !expandedConsumables.value[row.name],
  }
}

/** Names the mark the way the rest of the chart does - "#3 Botox - Forehead", never its autoname. */
function markConsumablesLabel(mark) {
  const detail = [mark.procedure_template || mark.category, mark.region_label || mark.body_region]
    .filter(Boolean)
    .join(" — ")
  const number = mark.sequence ? `#${mark.sequence}` : ""
  return [number, detail].filter(Boolean).join(" ") || __("Mark")
}

async function saveConsumables(owner, rows) {
  const name = owner.name
  savingConsumables.value = { ...savingConsumables.value, [name]: true }
  consumableErrors.value = { ...consumableErrors.value, [name]: "" }
  try {
    // Silent: a refused save already reports itself on the line it came from, and the
    // modal on top of it only buries the row the clinician is fixing.
    const resp = await frappe.call({
      method: "do_derma.api.save_consumables",
      args: { owner_doctype: owner.doctype, owner_name: name, rows },
      silent: true,
    })
    if (resp?.message) {
      consumablesByOwner.value = { ...consumablesByOwner.value, [name]: resp.message }
    }
  } catch (err) {
    consumableErrors.value = { ...consumableErrors.value, [name]: consumableErrorText(err) }
  } finally {
    savingConsumables.value = { ...savingConsumables.value, [name]: false }
  }
}

function consumableErrorText(err) {
  return serverErrorText(err, __("The materials could not be saved."))
}

function updateLocal(row, key, value) {
  edits.value = {
    ...edits.value,
    [row.name]: {
      ...(edits.value[row.name] || {}),
      [key]: value,
    },
  }
}

function resolveRowPatient(row) {
  if (row?.patient) return row.patient
  return window?.do_health?.patientWatcher?.read?.()?.patient || ""
}

function resolveRowProcedureName(row) {
  return row?.clinical_procedure || row?.name || ""
}

function escapeHtml(value) {
  const text = String(value ?? "")
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

function formatHistoryNote(value) {
  return htmlToPlainText(value || "")
}

async function fetchRowRelatedHistory(row, limit = 8) {
  const patient = resolveRowPatient(row)
  const clinicalProcedure = resolveRowProcedureName(row)
  if (!patient || !clinicalProcedure || String(clinicalProcedure).startsWith("local-")) {
    return { notes: [] }
  }
  try {
    const resp = await frappe.call("do_health.api.notes_center.get_related_procedure_notes", {
      patient,
      clinical_procedure: clinicalProcedure,
      limit,
    })
    const payload = resp?.message || { notes: [] }
    const filteredNotes = Array.isArray(payload.notes)
      ? payload.notes.filter((item) => {
          const sourceName = String(item?.clinical_procedure || item?.name || "").trim()
          if (!sourceName) return true
          return sourceName !== String(clinicalProcedure).trim()
        })
      : []
    return { ...payload, notes: filteredNotes }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("Failed to fetch related procedure notes", err)
    return { notes: [] }
  }
}

function getRowNoteRawValue(row) {
  const value = edits.value[row.name]?.notes ?? row.notes ?? ""
  return String(value || "")
}

function getRowNoteValue(row) {
  const value = getRowNoteRawValue(row)
  return htmlToPlainText(value)
}

function toEditorHtml(value) {
  const text = String(value || "").trim()
  if (!text) return ""
  if (/<[a-z][\s\S]*>/i.test(text)) {
    return text.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
  }
  const escaped = escapeHtml(text).replace(/\r\n/g, "\n")
  const paragraphs = escaped
    .split(/\n{2,}/)
    .map((chunk) => chunk.replace(/\n/g, "<br>").trim())
    .filter(Boolean)
  return paragraphs.length ? `<p>${paragraphs.join("</p><p>")}</p>` : ""
}

async function fetchNoteTemplate(templateName) {
  if (!templateName) return { raw_html: "", plain_text: "" }
  try {
    const resp = await frappe.call("frappe.client.get", {
      doctype: "Derma Note Template",
      name: templateName,
    })
    const raw = String(resp?.message?.note || "")
    return {
      raw_html: toEditorHtml(raw),
      plain_text: htmlToPlainText(raw),
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("Failed to fetch note template", err)
    frappe.show_alert({
      message: __("Could not load note template {0}.").replace("{0}", templateName),
      indicator: "red",
    })
    return null
  }
}

function renderRelatedNotesHtml(notes = []) {
  if (!Array.isArray(notes) || !notes.length) {
    return `<div class="procedure-note-dialog__empty">${__("No related notes yet.")}</div>`
  }
  return `
    <div class="procedure-note-dialog__history-list">
      ${notes
        .map((item) => {
          const title = escapeHtml(item?.source_procedure_label || item?.procedure_template || item?.name || __("Procedure"))
          const meta = escapeHtml(item?.occurred_at_label || item?.occurred_at || item?.modified || "")
          const body = escapeHtml(formatHistoryNote(item?.note || ""))
          return `
            <div class="procedure-note-dialog__history-item">
              <div class="procedure-note-dialog__history-title">${title}</div>
              <div class="procedure-note-dialog__history-meta">${meta}</div>
              <div class="procedure-note-dialog__history-body">${body || "—"}</div>
            </div>
          `
        })
        .join("")}
    </div>
  `
}

async function openProcedureNoteDialog(row) {
  if (!row) return
  const editable = isEditable(row)
  const currentPlain = getRowNoteValue(row).trim()
  const procedureLabel = row.display_name || row.procedure_template || row.name || __("Procedure")
  let dialog = null

  const setTemplatePreview = (templateHtml = "", templatePlain = "") => {
    if (!dialog) return
    const $wrapper = dialog.fields_dict?.template_preview?.$wrapper
    if (!$wrapper?.length) return
    if (!templateHtml && !templatePlain) {
      $wrapper.html("")
      return
    }
    const safePlain = escapeHtml(templatePlain || "")
    $wrapper.html(`
      <div class="procedure-note-dialog__template-preview">
        <div class="procedure-note-dialog__template-preview-rendered">${templateHtml || `<p>${safePlain || "—"}</p>`}</div>
        <div class="procedure-note-dialog__template-preview-plain">${safePlain || "—"}</div>
      </div>
    `)
  }

  // The procedure template's own note sentence is the default when nothing is
  // picked from the library.
  const noteSentence = String(row.note_sentence_template || "").trim()

  const setTemplateMessage = (text) => {
    const $wrapper = dialog?.fields_dict?.template_preview?.$wrapper
    if ($wrapper?.length) $wrapper.html(`<div class="procedure-note-dialog__loading">${escapeHtml(text)}</div>`)
  }

  const updateTemplatePreview = async () => {
    if (!dialog) return
    const templateName = dialog.get_value("note_template")
    if (!templateName) {
      setTemplatePreview(toEditorHtml(noteSentence), htmlToPlainText(noteSentence))
      return
    }
    setTemplateMessage(__("Loading the template..."))
    const templateData = await fetchNoteTemplate(templateName)
    if (!templateData) {
      setTemplatePreview()
      return
    }
    setTemplatePreview(templateData.raw_html, templateData.plain_text)
  }

  const applyTemplateToNote = async () => {
    if (!dialog) return
    const templateName = dialog.get_value("note_template")
    if (!templateName && !noteSentence) {
      frappe.show_alert({ message: __("Select a note template first."), indicator: "orange" })
      return
    }
    const templateData = templateName
      ? await fetchNoteTemplate(templateName)
      : { raw_html: toEditorHtml(noteSentence), plain_text: htmlToPlainText(noteSentence) }
    if (!templateData) return
    if (!templateData.raw_html && !templateData.plain_text) {
      frappe.show_alert({ message: __("Selected template has no text."), indicator: "orange" })
      return
    }
    const append = Boolean(dialog.get_value("append_to_existing"))
    const existing = String(dialog.get_value("note") || "").trim()
    const incoming = String(templateData.raw_html || "").trim()
    const merged = append && existing ? `${existing}<p><br></p>${incoming}` : incoming
    dialog.set_value("note", merged)
    setTemplatePreview(templateData.raw_html, templateData.plain_text)
    frappe.show_alert({ message: __("Template inserted."), indicator: "green" })
  }

  const renderRelatedHistory = async () => {
    if (!dialog) return
    const $wrapper = dialog.fields_dict?.related_notes?.$wrapper
    if (!$wrapper?.length) return
    $wrapper.html(`<div class="procedure-note-dialog__loading">${__("Loading related notes...")}</div>`)
    const payload = await fetchRowRelatedHistory(row, 14)
    $wrapper.html(renderRelatedNotesHtml(payload?.notes || []))
  }

  dialog = new frappe.ui.Dialog({
    title: `${__("Procedure Note")} · ${procedureLabel}`,
    size: "large",
    fields: [
      {
        fieldname: "related_notes_label",
        fieldtype: "HTML",
      },
      {
        fieldname: "related_notes",
        fieldtype: "HTML",
      },
      {
        fieldname: "template_break",
        fieldtype: "Section Break",
        hidden: editable ? 0 : 1,
      },
      {
        fieldname: "note_template",
        fieldtype: "Link",
        label: __("Apply Note Template"),
        options: "Derma Note Template",
        hidden: editable ? 0 : 1,
        get_query: () => ({ filters: { disabled: 0 } }),
        onchange: updateTemplatePreview,
      },
      {
        fieldname: "append_to_existing",
        fieldtype: "Check",
        label: __("Append template to current note"),
        default: currentPlain ? 1 : 0,
        hidden: editable ? 0 : 1,
      },
      {
        fieldname: "template_preview",
        fieldtype: "HTML",
        label: __("Template Preview"),
        hidden: editable ? 0 : 1,
      },
      {
        fieldname: "note_break",
        fieldtype: "Section Break",
      },
      {
        fieldname: "note",
        fieldtype: "Text Editor",
        label: __("Note"),
        default: getRowNoteRawValue(row),
        read_only: editable ? 0 : 1,
      },
    ],
    primary_action_label: editable ? __("Save Note") : __("Close"),
    primary_action: (values) => {
      if (!editable) {
        dialog.hide()
        return undefined
      }
      return runDialogAction(dialog, __("Saving the note..."), async () => {
        updateLocal(row, "notes", values?.note ?? "")
        const saved = await saveRow(row, { silent: true })
        if (!saved) {
          frappe.show_alert({ message: __("Could not save the note."), indicator: "red" })
          return false
        }
        frappe.show_alert({ message: __("Procedure note saved."), indicator: "green" })
        return true
      })
    },
  })

  dialog.$wrapper?.addClass("procedure-note-dialog")
  dialog.fields_dict.related_notes_label?.$wrapper?.html(
    `<div class="procedure-note-dialog__related-title">${__("Related Procedure Notes")}</div>`
  )
  if (editable) {
    dialog.set_secondary_action_label(__("Apply Template"))
    dialog.set_secondary_action(async (event) => {
      const button = event?.currentTarget
      if (button) button.disabled = true
      try {
        await applyTemplateToNote()
      } finally {
        if (button) button.disabled = false
      }
    })
  }
  dialog.show()
  nameDialogControls(dialog)
  void renderRelatedHistory()
  if (editable && noteSentence) void updateTemplatePreview()
}

function normalizePriceListName(value) {
  if (!value) return value
  const trimmed = String(value).trim()
  const parts = trimmed.split(" — ")
  if (parts.length <= 1) return trimmed
  const suffix = parts[parts.length - 1].trim()
  if (/^[0-9.,]+$/.test(suffix)) {
    return parts.slice(0, -1).join(" — ").trim()
  }
  return trimmed
}

function displayPriceList(row) {
  const frozen = row.price_list_used || row.price_list
  const value = normalizePriceListName(getEditValue(row, "price_list") || frozen || props.defaultPriceList)
  if (!value) return ""
  return value === CUSTOM_PRICE_LIST || value === "Custom" ? "Custom" : value
}

function priceSourceLabel(row) {
  if (isNoCharge(row)) return "No charge"
  if (row.price_override !== null && row.price_override !== undefined && row.price_override > 0) return "Override"
  return ""
}

function isNoCharge(row) {
  return Number(row?.no_charge || 0) === 1 && Number(row?.price_override || 0) === 0
}

function rowIsInsurance(row) {
  return Boolean(row?.appointment_is_insurance) || String(row?.appointment_payment_type || "").toLowerCase().includes("insur")
}

function hasAnyOverride(row) {
  if (isNoCharge(row)) return true
  return row?.price_override !== null && row?.price_override !== undefined && Number(row.price_override) !== 0
}

function displayOverride(row) {
  if (isNoCharge(row)) return __("No charge")
  if (row.price_override === null || row.price_override === undefined) return "—"
  if (Number(row.price_override) === 0) return "—"
  return formatCurrency(row.price_override)
}

function getPriceListOptions(row) {
  const set = new Set()
  ;[row.price_list, props.defaultPriceList, ...(props.priceLists || [])].forEach((pl) => {
    const normalized = normalizePriceListName(pl)
    if (normalized && normalized !== "Custom" && normalized !== CUSTOM_PRICE_LIST) set.add(normalized)
  })
  return Array.from(set)
}

function updatePriceManual(row, value) {
  if (rowIsInsurance(row)) {
    frappe.show_alert({ message: __("Overrides are not allowed for insurance visits."), indicator: "orange" })
    return
  }
  updateLocal(row, "price", value)
  updateLocal(row, "no_charge", false)
  updateLocal(row, "price_override_reason", "")
  // updateLocal(row, "price_list", CUSTOM_PRICE_LIST)
  saveRow(row, { silent: true })
}

function clearPriceOverride(row) {
  updateLocal(row, "price", null)
  updateLocal(row, "no_charge", false)
  updateLocal(row, "price_override_reason", "")
  saveRow(row)
}

function promptNoChargeReason() {
  return new Promise((resolve) => {
    frappe.prompt(
      [
        {
          fieldtype: "Small Text",
          fieldname: "reason",
          label: __("No Charge Reason"),
          reqd: 1,
        },
      ],
      (values) => resolve(values?.reason || ""),
      __("Confirm No Charge"),
      __("Apply")
    )
  })
}

async function markNoCharge(row) {
  if (!isEditable(row)) return
  if (rowIsInsurance(row)) {
    frappe.show_alert({ message: __("Overrides are not allowed for insurance visits."), indicator: "orange" })
    return
  }
  const reason = await promptNoChargeReason()
  if (!reason) return
  updateLocal(row, "price", 0)
  updateLocal(row, "no_charge", true)
  updateLocal(row, "price_override_reason", reason)
  saveRow(row)
}

function onPriceListSelect(row, priceList) {
  const normalized = normalizePriceListName(priceList)
  if (priceList === CUSTOM_PRICE_LIST) {
    updateLocal(row, "price_list", CUSTOM_PRICE_LIST)
    return
  }
  updateLocal(row, "price_list", normalized)
  repriceRow(row, normalized)
}

function openOverrideList(row) {
  overrideListOpenRow.value = row?.name || null
  if (!overrideOutsideHandler) {
    overrideOutsideHandler = (event) => {
      if (!event.target?.closest?.(".override-picker")) {
        closeOverrideList()
      }
    }
    document.addEventListener("click", overrideOutsideHandler)
  }
}

function closeOverrideList() {
  const openRow = overrideListOpenRow.value
  // Focus inside the editor would fall to <body> when it unmounts; hand it back to the amount.
  const hadFocus = Boolean(document.activeElement?.closest?.(".override-popover"))
  overrideListOpenRow.value = null
  if (openRow && hadFocus) {
    nextTick(() => document.querySelector(`.price-trigger[data-row="${CSS.escape(openRow)}"]`)?.focus())
  }
  if (overrideOutsideHandler) {
    document.removeEventListener("click", overrideOutsideHandler)
    overrideOutsideHandler = null
  }
}

async function setOverrideFromPriceList(row, priceList) {
  const normalized = normalizePriceListName(priceList)
  if (!normalized || isRowSaving(row)) return
  await withRowSaving(row.name, async () => {
    try {
      const resp = await frappe.call("do_derma.api.get_procedure_price", {
        procedure_name: row.name,
        price_list: normalized,
      })
      const rate = resp?.message?.rate
      updateLocal(row, "price", rate)
      updateLocal(row, "no_charge", false)
      updateLocal(row, "price_override_reason", "")
      await saveRow(row, { silent: true })
    } catch (err) {
      frappe.show_alert({ message: __("Could not fetch price."), indicator: "red" })
      // eslint-disable-next-line no-console
      console.warn("Failed to fetch override price", err)
    } finally {
      closeOverrideList()
    }
  })
}

onBeforeUnmount(() => {
  hideNotePreview()
  window.removeEventListener("scroll", hideNotePreview, true)
  if (overrideOutsideHandler) {
    document.removeEventListener("click", overrideOutsideHandler)
    overrideOutsideHandler = null
  }
})

async function repriceRow(row, priceList) {
  if (!isPersistedRow(row)) {
    updateLocal(row, "price_list", normalizePriceListName(priceList) || CUSTOM_PRICE_LIST)
    return
  }
  if (isRowSaving(row)) return
  await withRowSaving(row.name, async () => {
    try {
      const resp = await frappe.call("do_derma.api.get_procedure_price", {
        procedure_name: row.name,
        price_list: normalizePriceListName(priceList),
      })
      const rate = resp?.message?.rate
      updateLocal(row, "price", rate)
      updateLocal(row, "price_list", normalizePriceListName(priceList))
      updateLocal(row, "no_charge", false)
      updateLocal(row, "price_override_reason", "")
      row.base_rate = rate
      await saveRow(row)
    } catch (err) {
      frappe.show_alert({ message: __("Could not fetch price."), indicator: "red" })
      // eslint-disable-next-line no-console
      console.warn("Failed to fetch price", err)
    }
  })
}

// Client row keys -> Clinical Procedure fieldnames (do_derma custom fields,
// created by schema.py). The note rides on the core `notes` field, which do_derma's
// property setter unlocks so an edit after insert lands instead of throwing.
const PROCEDURE_UPDATE_FIELD_MAP = {
  price_override: "custom_derma_price_override",
  price_list: "custom_derma_price_list",
  no_charge: "custom_derma_no_charge",
  price_override_reason: "custom_derma_price_override_reason",
  notes: "notes",
}

/** Resolves true when the row is persisted (or there was nothing to save), false on failure. */
function saveRow(row, opts = {}) {
  if (!isPersistedRow(row)) return Promise.resolve(false)
  return withRowSaving(row.name, () => writeRow(row, opts))
}

function isRowSaving(row) {
  return Boolean(savingRows.value[row?.name])
}

/**
 * Counted, because a reprice wraps this around the save that wraps it again. Both ends read
 * the live count: two saves of one row can overlap - a price edit still in flight when Reset
 * is clicked - and writing back a depth captured on the way in left the count above zero for
 * good, so the row span forever and refused every later reprice.
 */
async function withRowSaving(name, action) {
  savingRows.value = { ...savingRows.value, [name]: (savingRows.value[name] || 0) + 1 }
  try {
    return await action()
  } finally {
    const remaining = Math.max((savingRows.value[name] || 1) - 1, 0)
    savingRows.value = { ...savingRows.value, [name]: remaining }
  }
}

function writeRow(row, opts) {
  const payload = edits.value[row.name] || {}
  const updates = {}
  if (payload.price !== undefined) {
    const parsedPrice = payload.price === "" || payload.price === null ? null : Number(payload.price)
    if (parsedPrice !== null && !Number.isNaN(parsedPrice)) {
      // Clear override if it matches base rate
      const base = row.base_rate !== undefined ? Number(row.base_rate) : null
      if (parsedPrice === 0 && payload.no_charge) {
        updates.price_override = 0
      } else if (parsedPrice === 0) {
        updates.price_override = null
      } else if (base !== null && !Number.isNaN(base) && parsedPrice === base) {
        updates.price_override = null
      } else {
        updates.price_override = parsedPrice
      }
    } else if (parsedPrice === null) {
      updates.price_override = null
    }
  }
  if (payload.price_list !== undefined) {
    updates.price_list =
      payload.price_list === CUSTOM_PRICE_LIST ? "Custom" : normalizePriceListName(payload.price_list)
  }
  if (payload.no_charge !== undefined) updates.no_charge = payload.no_charge ? 1 : 0
  if (payload.price_override_reason !== undefined) {
    updates.price_override_reason = String(payload.price_override_reason || "")
  }
  if (payload.notes !== undefined) updates.notes = String(payload.notes || "")
  if (!Object.keys(updates).length) return Promise.resolve(true)

  const serverUpdates = Object.fromEntries(
    Object.entries(updates).map(([key, value]) => [PROCEDURE_UPDATE_FIELD_MAP[key] || key, value])
  )
  return frappe
    .call("do_derma.api.update_clinical_procedure_fields", {
      procedure_name: row.name,
      updates: serverUpdates,
    })
    .then((resp) => {
      Object.assign(row, {
        price_override: updates.price_override !== undefined ? updates.price_override : row.price_override,
        no_charge: updates.no_charge !== undefined ? Boolean(updates.no_charge) : row.no_charge,
        price_override_reason:
          updates.price_override_reason !== undefined ? updates.price_override_reason : row.price_override_reason,
        display_price:
          updates.price_override !== undefined
            ? updates.price_override === null
              ? row.base_rate
              : updates.price_override
            : displayPrice(row),
        price_list: updates.price_list !== undefined ? updates.price_list : row.price_list,
        price_source:
          updates.price_override !== undefined
            ? updates.price_override === null
              ? "Price List"
              : updates.no_charge
                ? "No charge"
                : "Override"
            : row.price_source,
        notes: updates.notes !== undefined ? updates.notes : row.notes,
      })
      edits.value[row.name] = {}
      if (updates.price_override !== undefined && typeof window !== "undefined") {
        const syncInfo = resp?.message?.billing_sync || {}
        const appointment = syncInfo?.appointment || row.appointment || null
        if (appointment) {
          window.dispatchEvent(
            new CustomEvent("do_health:appointment_billing_needs_refresh", {
              detail: {
                appointment,
                source: "chart_procedure_override",
              },
            })
          )
        }
      }
      if (!opts.silent) {
        frappe.show_alert({ message: __("Updated."), indicator: "green" })
      }
      return true
    })
    .catch((err) => {
      if (!opts.silent) {
        frappe.show_alert({ message: __("Could not update."), indicator: "red" })
      }
      // eslint-disable-next-line no-console
      console.warn("Failed to update procedure row", err)
      return false
    })
}

function formatCurrency(value, currency = null) {
  if (value === undefined || value === null || value === "") return ""
  const amount = Number(value)
  if (!Number.isFinite(amount)) return value
  return new Intl.NumberFormat(undefined, {
    style: currency ? "currency" : "decimal",
    currency: currency || "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

function formatGroupLabel(group) {
  const first = group?.items?.[0]
  const dateValue = group?.procedure_date || first?.procedure_date || first?.date || first?.start_date || ""
  if (!dateValue) return __("No date")
  try {
    return frappe.datetime.str_to_user(dateValue)
  } catch (err) {
    return dateValue
  }
}

function resetPrice(row) {
  updateLocal(row, "price", "0")
  saveRow(row)
}

function statusTone(status) {
  return STATUS_TONES[status] || "neutral"
}

function labCaseTone(status) {
  const key = (status || "").toString().toLowerCase()
  if (["delivered", "closed"].includes(key)) return "ok"
  if (["cancelled"].includes(key)) return "danger"
  if (["ready for delivery", "quality checked", "received in clinic", "sent", "in production", "received by lab", "shipped"].includes(key)) return "caution"
  return "neutral"
}

function formatSurfaceText(row) {
  const list = edits.value[row.name]?.surfaces || row.surfaces || []
  return list.map((s) => s.surface || s).join(", ")
}

function rowAllowsSurfaces(row) {
  const profile = String(row.surface_profile || "").toLowerCase()
  if (!profile || profile === "none") return false
  const style = String(row.render_style || "").toLowerCase()
  return !["crown", "implant", "extraction", "outline", "prosthesis"].includes(style)
}

function deleteRow(row) {
  if (!row?.name) return
  const procedure = row.clinical_procedure || row.name
  const label = __("Delete the procedure with its marks and drawings?")
  frappe.confirm(label, () => {
    const doctype = "Clinical Procedure"
    const name = procedure
    frappe
      .call("do_derma.api.delete_clinical_procedure_entry", { doctype, name })
      .then(() => {
        frappe.show_alert({ message: __("Deleted."), indicator: "green" })
        emit("refresh")
      })
      .catch((err) => {
        frappe.show_alert({ message: __("Could not delete."), indicator: "red" })
        // eslint-disable-next-line no-console
        console.warn("Failed to delete procedure row", err)
      })
  })
}

function getProcedureName(row) {
  const name = row?.clinical_procedure || row?.name
  if (!name || String(name).startsWith("local-")) return ""
  return name
}

function noteLabel(row) {
  if (!isEditable(row)) return __("View note")
  return getRowNoteRawValue(row) ? __("Edit note") : __("Add note")
}

function annotateLabel(row) {
  const count = Number(row?.annotation_count || 0)
  return count ? `${__("Annotate")} (${count})` : __("Annotate")
}

function openProcedure(row) {
  const procedureName = getProcedureName(row)
  if (!procedureName) return
  frappe.msgprint({
    title: row?.procedure_template || row?.template_label || __("Clinical Procedure"),
    message: [
      `<p><b>${__("Procedure")}:</b> ${escapeHtml(procedureName)}</p>`,
      row?.status ? `<p><b>${__("Status")}:</b> ${escapeHtml(row.status)}</p>` : "",
      row?.notes ? `<p>${escapeHtml(row.notes)}</p>` : "",
    ].filter(Boolean).join(""),
    indicator: "blue",
  })
}

function handleRowDoubleClick(row, event) {
  const target = event?.target
  if (
    target?.closest?.(
      "input, textarea, select, button, a, .override-popover"
    )
  ) {
    return
  }
  openProcedure(row)
}

</script>

<style scoped>

/* Wraps rather than squeezing: the action buttons move to their own line before a label breaks. */
.dental-chart-page .procedure-primary-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
  padding: 0;
  border-bottom: 0;
}

.dental-chart-page .procedure-primary-toolbar > .history-search {
  flex: 1 1 260px;
}

.dental-chart-page .procedure-primary-toolbar > .panel-actions {
  margin-left: auto;
  flex-wrap: wrap;
}

.dental-chart-page .procedure-primary-toolbar button {
  white-space: nowrap;
}

.dental-chart-page .panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.dental-chart-page .procedure-load-more-row .history-load-selector {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--chart-muted);
  font-size: 12px;
  font-weight: 700;
}

.dental-chart-page .procedure-load-more-row .history-load-selector select {
  border: 1px solid var(--chart-border-strong);
  background: var(--chart-surface);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 12px;
}

.dental-chart-page .procedure-history-controls {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 8px;
  align-items: end;
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface-muted);
}

.dental-chart-page .history-search,
.dental-chart-page .history-filter-control {
  border: 1px solid var(--chart-border);
  background: var(--chart-surface);
  border-radius: 8px;
  min-height: 34px;
}

.dental-chart-page .procedure-sort {
  min-height: 34px;
  padding: 0 28px 0 10px;
  border: 1px solid var(--chart-border);
  border-radius: 8px;
  background-color: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
}

.dental-chart-page .filter-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dental-chart-page .filter-toggle-btn.active {
  background: var(--chart-accent-soft);
  color: var(--chart-accent-text);
}

.dental-chart-page .filter-count,
.dental-chart-page .pill-count {
  font-weight: 700;
  opacity: 0.75;
}

.dental-chart-page .status-filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.dental-chart-page .attention-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: auto;
}

.dental-chart-page .load-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dental-chart-page .history-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  min-width: 0;
}

.dental-chart-page .history-search i {
  color: var(--chart-muted);
  font-size: 12px;
}

.dental-chart-page .history-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: none;
  font-size: 13px;
  background: transparent;
}

.dental-chart-page .history-filter-control {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 5px 8px;
}

.dental-chart-page .history-filter-control span {
  color: var(--chart-muted);
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
  text-transform: uppercase;
}

.dental-chart-page .history-filter-control select {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--chart-text);
  font-size: 12px;
  font-weight: 700;
  padding: 0;
}

.dental-chart-page .procedure-table-wrapper {
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  overflow: auto;
  max-height: 62vh;
}

.dental-chart-page .procedure-load-more-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-top: 1px solid var(--chart-border);
  background: var(--chart-surface-muted);
}

.dental-chart-page .procedure-load-more-row .text-muted {
  color: var(--chart-muted);
  font-size: 12px;
  font-weight: 600;
}

.dental-chart-page .procedure-load-more-row .ghost.small {
  padding: 4px 10px;
}

/* Below this the six columns cannot all hold their content, so the wrapper
   scrolls the whole table rather than clipping the Actions column off the end. */
.dental-chart-page .procedure-table {
  width: 100%;
  min-width: 800px;
  border-collapse: collapse;
  table-layout: fixed;
}

.dental-chart-page .procedure-table .col-status {
  width: 13%;
}

.dental-chart-page .procedure-table .col-procedure {
  width: 23%;
}

.dental-chart-page .procedure-table .col-details {
  width: 25%;
}

.dental-chart-page .procedure-table .col-price {
  width: 14%;
}

.dental-chart-page .procedure-table .col-doctor {
  width: 13%;
}

/* Up to three 28px icon buttons plus the annotation count badge. */
.dental-chart-page .procedure-table .col-actions {
  width: 12%;
}

.dental-chart-page .procedure-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 8px 12px;
  border-bottom: 1px solid var(--chart-border);
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-align: left;
  text-transform: uppercase;
}

.dental-chart-page .procedure-date-row td {
  padding: 10px 12px 6px;
  border-bottom: 1px solid var(--chart-border);
  background: var(--chart-surface);
  color: var(--chart-muted);
  font-size: 12px;
  font-weight: 600;
}

.dental-chart-page .procedure-table .cell-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

/* Consent pills outgrow the status column at 1280px; wrap rather than spill into Procedure. */
.dental-chart-page .procedure-table .cell-stack .chart-pill {
  white-space: normal;
  max-width: 100%;
  text-align: left;
}

.dental-chart-page .procedure-table .procedure-meta {
  color: var(--chart-muted);
  font-size: 12px;
}

.dental-chart-page .procedure-table .details-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
}

.dental-chart-page .procedure-table .detail-text {
  max-width: 100%;
  overflow: hidden;
}

.dental-chart-page .procedure-table .detail-text span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dental-chart-page .procedure-table .detail-empty {
  color: var(--chart-muted);
}

.dental-chart-page .procedure-table .price-meta {
  font-size: 11px;
  color: var(--chart-muted);
  margin-top: 4px;
}

.dental-chart-page .procedure-table td.row-actions {
  white-space: nowrap;
  padding-left: 6px;
  padding-right: 6px;
}

.dental-chart-page .procedure-table .icon-btn {
  position: relative;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chart-muted);
  font-size: 13px;
  cursor: pointer;
}

.dental-chart-page .procedure-table .icon-btn:hover:not(:disabled),
.dental-chart-page .procedure-table .icon-btn:focus-visible {
  background: var(--chart-surface-muted);
  color: var(--chart-text);
}

.dental-chart-page .procedure-table .icon-btn.danger:hover:not(:disabled),
.dental-chart-page .procedure-table .icon-btn.danger:focus-visible {
  background: var(--chart-danger-soft);
  color: var(--chart-danger-text);
}

.dental-chart-page .procedure-table .icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Fixed, not absolute: the table wrapper's overflow-x would clip it beside the last column. */
.dental-chart-page .note-preview {
  position: fixed;
  z-index: 1050;
  width: min(320px, calc(100vw - 32px));
  padding: 10px 12px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: var(--chart-shadow);
  pointer-events: none;
}

.dental-chart-page .note-preview p {
  display: -webkit-box;
  margin: 4px 0 0;
  overflow: hidden;
  color: var(--chart-text);
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-line;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 10;
}

.dental-chart-page .procedure-table .note-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--chart-ok);
}

.dental-chart-page .procedure-table .icon-btn .icon-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 15px;
  height: 15px;
  padding: 0 3px;
  border-radius: 999px;
  background: var(--chart-accent-strong);
  color: white;
  font-size: 10px;
  font-weight: 800;
  line-height: 15px;
  text-align: center;
}

.dental-chart-page .procedure-table td {
  padding: 10px;
  border-bottom: 1px solid var(--chart-surface-muted);
  font-size: 13px;
}

.dental-chart-page .procedure-table .procedure-open-link {
  border: 0;
  background: transparent;
  padding: 0;
  margin: 0;
  color: var(--chart-text);
  text-decoration: none;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  border-bottom: 1px solid transparent;
  line-height: 1.3;
  transition: color 120ms ease, border-color 120ms ease;
}

.dental-chart-page .procedure-table .procedure-open-link:hover {
  color: var(--chart-info-text);
  border-bottom-color: var(--chart-border-strong);
}

.dental-chart-page .procedure-table .procedure-open-link:focus-visible {
  outline: none;
  color: var(--chart-info-text);
  border-bottom-color: var(--chart-info-text);
}

.dental-chart-page .procedure-table .inline-input {
  width: 100%;
  border: 1px solid var(--chart-border-strong);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
}

.dental-chart-page .procedure-table .price-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.dental-chart-page .procedure-table .override-picker {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
}

.dental-chart-page .procedure-table .price-trigger,
.dental-chart-page .procedure-table .price-amount {
  padding: 0;
  border: 0;
  border-bottom: 1px dashed transparent;
  background: transparent;
  color: var(--chart-text);
  font-weight: 600;
}

.dental-chart-page .procedure-table .price-trigger {
  border-bottom-color: var(--chart-border-strong);
  cursor: pointer;
}

.dental-chart-page .procedure-table .price-trigger:focus-visible {
  outline: none;
  border-radius: 4px;
  box-shadow: var(--chart-focus);
}

.dental-chart-page .procedure-table .price-trigger:hover,
.dental-chart-page .procedure-table .price-trigger[aria-expanded="true"] {
  border-bottom-color: var(--chart-accent);
}

/* In flow, not absolute: the wrapper's overflow-x would clip a floating popover on the last rows. */
.dental-chart-page .procedure-table .override-popover {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: var(--chart-shadow);
}

.dental-chart-page .procedure-table .override-popover-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 4px;
}

.dental-chart-page .procedure-table .override-option {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 8px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.dental-chart-page .procedure-table .override-option:hover {
  background: var(--chart-surface-muted);
}

.dental-chart-page .procedure-table .ghost.small {
  background: var(--chart-surface-muted);
  padding: 6px 10px;
}

.dental-chart-page .procedure-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 22px 16px;
  text-align: center;
  color: var(--chart-muted);
  border: 1px dashed var(--chart-border-strong);
  border-radius: 12px;
  background: var(--chart-surface-muted);
}

.dental-chart-page .procedure-empty strong {
  color: var(--chart-text);
  font-size: 14px;
}

.dental-chart-page .procedure-empty span {
  max-width: 520px;
  font-size: 13px;
  line-height: 1.45;
}

.dental-chart-page .procedure-empty .ghost.small {
  padding: 6px 10px;
  font-weight: 700;
}

.dental-chart-page .invoice-footer {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  padding-top: 12px;
}

.dental-chart-page .invoice-btn {
  background: var(--chart-accent-strong);
  color: white;
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 120ms ease, background 120ms ease;
}

.dental-chart-page .invoice-btn.disabled,
.dental-chart-page .invoice-btn:disabled {
  background: var(--chart-faint);
  cursor: not-allowed;
  opacity: 0.7;
}

.dental-chart-page .invoice-btn.ghost {
  background: var(--chart-surface-muted);
  border: 1px solid var(--chart-border-strong);
  color: var(--chart-text-soft);
}

:global(.procedure-note-dialog .modal-dialog) {
  width: min(980px, calc(100vw - 32px));
  max-width: 980px;
}

:global(.procedure-note-dialog .modal-content) {
  border: 1px solid var(--chart-border);
  border-radius: 14px;
  overflow: hidden;
}

:global(.procedure-note-dialog .modal-header) {
  background: linear-gradient(135deg, var(--chart-surface-muted), var(--chart-info-soft));
  border-bottom: 1px solid var(--chart-border);
}

:global(.procedure-note-dialog .modal-footer) {
  border-top: 1px solid var(--chart-border);
  background: var(--chart-surface);
}

:global(.procedure-note-dialog .frappe-control[data-fieldname="note"] .ql-editor) {
  min-height: 230px;
}

:global(.procedure-note-dialog__template-preview) {
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface-muted);
  overflow: hidden;
}

:global(.procedure-note-dialog__template-preview-rendered) {
  padding: 10px 12px;
  background: var(--chart-surface);
  border-bottom: 1px solid var(--chart-border);
  max-height: 180px;
  overflow: auto;
}

:global(.procedure-note-dialog__template-preview-plain) {
  padding: 10px 12px;
  color: var(--chart-muted);
  font-size: 12px;
  line-height: 1.45;
  max-height: 100px;
  overflow: auto;
  white-space: pre-wrap;
}

:global(.procedure-note-dialog__related-title) {
  margin-top: 4px;
  margin-bottom: 8px;
  font-weight: 700;
  color: var(--chart-text);
  font-size: 13px;
  letter-spacing: 0.01em;
}

:global(.procedure-note-dialog__loading),
:global(.procedure-note-dialog__empty) {
  border: 1px dashed var(--chart-border-strong);
  border-radius: 10px;
  padding: 12px;
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
  font-size: 12px;
}

:global(.procedure-note-dialog__history-list) {
  display: grid;
  gap: 8px;
  max-height: 260px;
  overflow: auto;
  padding-right: 2px;
}

:global(.procedure-note-dialog__history-item) {
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  padding: 10px;
  background: var(--chart-surface-muted);
}

:global(.procedure-note-dialog__history-title) {
  font-size: 12px;
  font-weight: 700;
  color: var(--chart-text);
  margin-bottom: 3px;
}

:global(.procedure-note-dialog__history-meta) {
  font-size: 11px;
  color: var(--chart-muted);
  margin-bottom: 6px;
}

:global(.procedure-note-dialog__history-body) {
  font-size: 12px;
  line-height: 1.45;
  color: var(--chart-text-soft);
  white-space: pre-wrap;
}

@media (max-width: 768px) {
  .dental-chart-page .panel-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .dental-chart-page .procedure-history-controls {
    grid-template-columns: 1fr 1fr;
  }

  :global(.procedure-note-dialog .modal-dialog) {
    width: calc(100vw - 12px);
    margin: 6px auto;
  }

  :global(.procedure-note-dialog .frappe-control[data-fieldname="note"] .ql-editor) {
    min-height: 170px;
  }
}
</style>

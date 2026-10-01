<template>
  <div class="chart-hero-stack" data-test="encounter-header">
    <div v-if="encounter.name && !isLatest" class="chart-hero-banner" data-test="encounter-visit-strip">
      <b>{{ __("Previous visit") }}</b>
      <span>{{ visitWhen }}</span>
      <span>{{ encounter.name }}</span>
      <span v-if="encounter.practitioner_name">· {{ encounter.practitioner_name }}</span>
      <button type="button" class="chart-hero-banner-link" data-test="open-latest-visit" @click="$emit('open-latest')">
        {{ __("Open latest visit") }} →
      </button>
    </div>

    <header class="chart-hero">
      <div class="chart-hero-identity">
        <img
          v-if="patient.image && !isBroken(patient.image)"
          class="chart-hero-avatar"
          :src="patient.image"
          :alt="patientName"
          @error="markBroken(patient.image)"
        />
        <span v-else class="chart-hero-avatar">{{ initials }}</span>
        <div class="chart-hero-text">
          <h1 data-test="header-patient-name">{{ patientName }}</h1>
          <p class="chart-hero-meta">{{ patientMeta }}</p>
          <span v-if="patient.mobile" class="chart-hero-chip">☎ {{ patient.mobile }}</span>
          <div v-if="alerts.length" class="chart-hero-alerts" data-test="encounter-alerts">
            <button
              v-for="alert in alerts"
              :key="alert.key"
              type="button"
              class="chart-hero-chip"
              :data-tone="alert.tone"
              :title="alert.detail"
              @click="$emit('alert-action', alert)"
            >
              <b>{{ alert.label }}</b>
            </button>
          </div>
        </div>
      </div>

      <aside class="chart-hero-visit">
        <div class="chart-hero-visit-top">
          <span class="chart-hero-label">{{ __("This visit") }}</span>
          <span v-if="statusLabel" class="chart-hero-status" :data-tone="isCompleted ? 'ok' : 'caution'" data-test="hero-visit-status">
            {{ statusLabel }}
          </span>
        </div>
        <strong class="chart-hero-when">{{ visitWhen || __("No visit date") }}</strong>
        <small>{{ [visitType, practitionerName].filter(Boolean).join(" · ") }}</small>
        <small>{{ insuranceLabel }}</small>
        <button
          v-if="hasSessionContext"
          type="button"
          class="chart-hero-readiness"
          :data-tone="readinessTone"
          data-test="hero-readiness"
          @click="$emit('open-readiness')"
        >{{ readinessText }}</button>
        <button
          v-if="!isCompleted"
          type="button"
          class="primary chart-hero-action"
          data-test="complete-session"
          :disabled="!hasSessionContext || completing || pending"
          @click="$emit('complete')"
        >{{ completing ? __("Completing...") : __("Complete Encounter") }}</button>
        <button
          v-else-if="canReopen"
          type="button"
          class="chart-hero-action"
          data-test="reopen-session"
          :disabled="reopening"
          @click="$emit('reopen')"
        >{{ reopening ? __("Reopening...") : __("Reopen Encounter") }}</button>
        <small v-else data-test="encounter-completed-note">{{ __("Completed. Reopening needs cancel permission.") }}</small>
      </aside>
    </header>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { useBrokenImages } from "../../../shared/broken_images.js"

const __ = window.__ || ((txt) => txt)
const { isBroken, markBroken } = useBrokenImages()

const props = defineProps({
  patient: { type: Object, default: () => ({}) },
  appointment: { type: Object, default: () => ({}) },
  encounter: { type: Object, default: () => ({}) },
  practitionerName: { type: String, default: "" },
  insuranceLabel: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  completing: { type: Boolean, default: false },
  // A completion awaiting its confirm dialog: refuse a second click without claiming one is under way.
  pending: { type: Boolean, default: false },
  canReopen: { type: Boolean, default: false },
  reopening: { type: Boolean, default: false },
  alerts: { type: Array, default: () => [] },
  latestEncounter: { type: String, default: "" },
  visitDate: { type: String, default: "" },
  visitTime: { type: String, default: "" },
  readiness: { type: Object, default: () => ({ items: [], blockers: [] }) },
})

defineEmits(["complete", "reopen", "open-latest", "alert-action", "open-readiness"])

const isCompleted = computed(() => Number(props.encounter.docstatus) === 1)
const isLatest = computed(() => !props.latestEncounter || props.latestEncounter === props.encounter.name)
const visitWhen = computed(() => {
  const date = window.frappe?.datetime?.str_to_user?.(props.visitDate) || props.visitDate
  // Frappe sends times as "7:15:15.9": pad the hour, drop the seconds.
  const [hour = "", minute = ""] = props.visitTime.split(":")
  const time = hour && minute ? `${hour.padStart(2, "0")}:${minute}` : ""
  return [date, time].filter(Boolean).join(" · ")
})
const patientName = computed(() => props.patient.patient_name || props.patient.name || __("Patient"))
const initials = computed(() => patientName.value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "P")
const age = computed(() => {
  if (!props.patient.dob) return ""
  const born = new Date(props.patient.dob)
  const today = new Date()
  const hasHadBirthday =
    today.getMonth() > born.getMonth() || (today.getMonth() === born.getMonth() && today.getDate() >= born.getDate())
  return `${today.getFullYear() - born.getFullYear() - (hasHadBirthday ? 0 : 1)} y`
})
const patientMeta = computed(() =>
  [
    age.value,
    props.patient.sex,
    props.patient.custom_file_number ? `${__("File")} ${props.patient.custom_file_number}` : `${__("MRN")} ${props.patient.name || ""}`,
    props.patient.custom_cpr ? `${__("CPR")} ${props.patient.custom_cpr}` : "",
  ].filter((part) => part && part.trim()).join(" · ")
)
const visitType = computed(() => props.appointment.custom_appointment_category || props.appointment.appointment_type || props.encounter.appointment_type || "")
const statusLabel = computed(() => (isCompleted.value ? __("Completed") : props.appointment.status || ""))
const blockerCount = computed(() => (props.readiness.blockers || []).length)
const warningCount = computed(() => (props.readiness.items || []).length - blockerCount.value)
const readinessTone = computed(() => (blockerCount.value ? "danger" : warningCount.value ? "caution" : "ok"))
const readinessText = computed(() => {
  const warnings = warningCount.value ? __("{0} warning(s)").replace("{0}", warningCount.value) : ""
  if (blockerCount.value) {
    return [__("{0} blocker(s)").replace("{0}", blockerCount.value), warnings].filter(Boolean).join(" · ")
  }
  return warnings || __("Ready to complete")
})
</script>

<style scoped>
.chart-hero-stack {
  display: grid;
  gap: 8px;
}

.chart-hero-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--chart-caution-border);
  border-radius: 10px;
  background: var(--chart-caution-soft);
  color: var(--chart-caution-text);
  font-size: 12px;
}

.chart-hero-banner-link {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: var(--chart-blue);
  font-weight: 600;
}

.chart-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 18px;
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: 18px;
  box-shadow: var(--chart-shadow);
}

.chart-hero-identity {
  display: flex;
  gap: 18px;
  min-width: 0;
}

.chart-hero-avatar {
  display: grid;
  place-items: center;
  flex: 0 0 96px;
  width: 96px;
  height: 96px;
  border-radius: 20px;
  border: 4px solid var(--chart-surface);
  box-shadow: 0 0 0 1px var(--chart-border), var(--chart-shadow);
  background: linear-gradient(135deg, #dcfce7, #d1fae5);
  color: var(--chart-ok-text);
  font-size: 32px;
  font-weight: 700;
  object-fit: cover;
}

.chart-hero-text {
  display: grid;
  align-content: start;
  justify-items: start;
  gap: 6px;
  min-width: 0;
}

.chart-hero-text h1 {
  margin: 0;
  color: var(--chart-text);
  font-size: 22px;
  font-weight: 750;
}

.chart-hero-meta {
  margin: 0;
  color: var(--chart-text-soft);
  font-size: 13px;
}

.chart-hero-chip {
  display: inline-flex;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--chart-border-strong);
  border-radius: 999px;
  background: var(--chart-surface);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.chart-hero-chip[data-tone="danger"] {
  background: var(--chart-danger-soft);
  border-color: var(--chart-danger-border);
  color: var(--chart-danger-text);
}

.chart-hero-chip[data-tone="warning"] {
  background: var(--chart-caution-soft);
  border-color: var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.chart-hero-alerts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chart-hero-visit {
  display: grid;
  align-content: start;
  gap: 4px;
  flex: 0 0 240px;
  padding: 12px 14px;
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
  font-size: 12px;
}

.chart-hero-visit-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-hero-label {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chart-hero-status {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.chart-hero-status[data-tone="caution"] {
  background: var(--chart-caution-soft);
  border: 1px solid var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.chart-hero-status[data-tone="ok"] {
  background: var(--chart-ok-soft);
  color: var(--chart-ok-text);
}

.chart-hero-when {
  color: var(--chart-text);
  font-size: 15px;
}

.chart-hero-readiness {
  justify-self: start;
  margin-top: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 12px;
  font-weight: 650;
}

.chart-hero-readiness[data-tone="danger"] { color: var(--chart-danger-text); }
.chart-hero-readiness[data-tone="caution"] { color: var(--chart-caution-text); }
.chart-hero-readiness[data-tone="ok"] { color: var(--chart-ok-text); }

.chart-hero-action {
  margin-top: 8px;
  width: 100%;
}

@media (max-width: 900px) {
  .chart-hero {
    flex-direction: column;
  }

  .chart-hero-visit {
    flex-basis: auto;
  }
}
</style>

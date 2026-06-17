<template>
  <header class="derma-encounter-header">
    <div class="encounter-patient">
      <img v-if="patient.image" :src="patient.image" :alt="patientName" />
      <span v-else class="patient-avatar">{{ initials }}</span>
      <div>
        <strong>{{ patientName }}</strong>
        <small>{{ patientMeta }}</small>
      </div>
    </div>

    <div class="encounter-status-strip">
      <span class="encounter-chip" :class="{ warning: allergyText }">
        <b>{{ __("Allergies") }}</b>
        {{ allergyText || __("None recorded") }}
      </span>
      <span class="encounter-chip">
        <b>{{ __("Visit") }}</b>
        {{ visitType || __("Visit") }}
      </span>
      <span class="encounter-chip" :class="{ active: hasSessionContext }">
        <b>{{ __("Status") }}</b>
        {{ encounter.docstatus === 1 ? __("Submitted") : hasSessionContext ? __("Open") : __("Pending") }}
      </span>
      <span class="encounter-chip">
        <b>{{ __("Insurance") }}</b>
        {{ insuranceLabel || __("Not set") }}
      </span>
    </div>

    <div class="encounter-actions">
      <button type="button" class="ghost small" @click="$emit('refresh')">{{ __("Refresh") }}</button>
      <button type="button" class="primary" :disabled="!hasSessionContext" @click="$emit('complete')">
        {{ __("Complete Encounter") }}
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  patient: { type: Object, default: () => ({}) },
  appointment: { type: Object, default: () => ({}) },
  encounter: { type: Object, default: () => ({}) },
  practitionerName: { type: String, default: "" },
  allergyText: { type: String, default: "" },
  insuranceLabel: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
})

defineEmits(["refresh", "complete"])

const patientName = computed(() => props.patient.patient_name || props.patient.name || __("Patient"))
const initials = computed(() => patientName.value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "P")
const patientMeta = computed(() => {
  const parts = [
    props.patient.sex,
    props.patient.name ? `${__("MRN")}: ${props.patient.name}` : "",
    props.practitionerName,
  ].filter(Boolean)
  return parts.join(" · ")
})
const visitType = computed(() => props.appointment.custom_appointment_category || props.appointment.appointment_type || props.encounter.appointment_type || "")
</script>

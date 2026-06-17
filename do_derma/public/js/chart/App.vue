<template>
  <DermaChart :context="context" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue"
import DermaChart from "./DermaChart.vue"

const context = ref({})
let unsubscribe = null

function updateContext(source = {}) {
  const route = window.frappe?.route_options || {}
  const sidebar = window.doHealthSidebar?.getSelectedPatient?.() || window.do_health?.patientWatcher?.read?.() || {}
  const next = source?.patient ? source : sidebar
  context.value = {
    patient: route.patient || next.patient,
    appointment: route.appointment || next.appointment,
    encounter: route.encounter || next.encounter_name || next.encounter,
  }
}

onMounted(() => {
  if (window.do_health?.patientWatcher) {
    unsubscribe = window.do_health.patientWatcher.subscribe(updateContext)
  }
  updateContext()
})

onBeforeUnmount(() => {
  if (unsubscribe) unsubscribe()
})
</script>

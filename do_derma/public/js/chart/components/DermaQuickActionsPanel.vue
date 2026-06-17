<template>
  <aside class="derma-quick-panel">
    <section>
      <header>
        <strong>{{ __("Quick Actions") }}</strong>
        <small>{{ activeProcedure ? __("Linked to active procedure") : __("Encounter-level evidence until a procedure is active") }}</small>
      </header>
      <div class="quick-action-grid">
        <button type="button" @click="$emit('new-procedure')">{{ __("New Procedure") }}</button>
        <button type="button" @click="$emit('prescription')">{{ __("New Prescription") }}</button>
        <button type="button" :disabled="!allowEvidence" @click="$emit('upload-photos')">{{ __("Upload Photos") }}</button>
        <button type="button" :disabled="!allowEvidence || !canAnnotate" @click="$emit('annotate')">{{ __("Annotate") }}</button>
        <button type="button" @click="$emit('consent')">{{ __("Consent") }}</button>
        <button type="button" @click="$emit('followup')">{{ __("Follow-up") }}</button>
      </div>
    </section>

    <section>
      <header>
        <strong>{{ __("Smart Alerts") }}</strong>
        <small>{{ alerts.length ? __("{0} item(s)").replace("{0}", alerts.length) : __("No urgent alerts") }}</small>
      </header>
      <div v-if="alerts.length" class="smart-alert-list">
        <button v-for="alert in alerts" :key="alert.key" type="button" :class="alert.tone" @click="$emit('alert-action', alert)">
          <b>{{ alert.label }}</b>
          <small>{{ alert.detail }}</small>
        </button>
      </div>
      <p v-else class="panel-muted">{{ __("All required procedure signals look clear.") }}</p>
    </section>
  </aside>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  activeProcedure: { type: Object, default: null },
  canAnnotate: { type: Boolean, default: false },
  allowEvidence: { type: Boolean, default: false },
  alerts: { type: Array, default: () => [] },
})

defineEmits(["new-procedure", "prescription", "upload-photos", "annotate", "consent", "followup", "alert-action"])
</script>

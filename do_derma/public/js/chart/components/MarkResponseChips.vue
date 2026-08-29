<template>
  <div v-if="mark" class="response-chip-row">
    <button
      v-for="status in statuses"
      :key="status"
      type="button"
      :class="{ active: mark.status === status }"
      :data-test="`mark-response-${status.toLowerCase()}`"
      :disabled="busy"
      @click="$emit('set', status)"
    >
      {{ status }}
    </button>
    <span v-if="busy" class="chart-spinner" role="status" :aria-label="__('Saving the status')"></span>
  </div>
</template>

<script setup>
const __ = window.__ || ((text) => text)

defineProps({
  statuses: { type: Array, default: () => [] },
  mark: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})

defineEmits(["set"])
</script>

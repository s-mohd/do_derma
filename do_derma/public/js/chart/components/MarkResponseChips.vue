<template>
  <div v-if="mark" class="response-chip-row">
    <button
      v-for="status in statuses"
      :key="status"
      type="button"
      :class="{ active: mark.status === status }"
      :data-test="`mark-response-${status.toLowerCase()}`"
      @click="$emit('set', status)"
    >
      {{ status }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  statuses: { type: Array, default: () => [] },
  mark: { type: Object, default: null },
})

defineEmits(["set"])
</script>

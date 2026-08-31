<template>
  <div class="degraded-section-notice" role="alert" data-test="degraded-section" :data-section="section">
    <span>
      <span aria-hidden="true">⚠</span>
      {{ __("Couldn't load {0}.").replace("{0}", label) }}
    </span>
    <button type="button" class="ghost small" data-test="degraded-section-retry" @click="$emit('retry')">
      {{ __("Retry") }}
    </button>
  </div>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  section: { type: String, default: "" },
  label: { type: String, default: "" },
})

defineEmits(["retry"])
</script>

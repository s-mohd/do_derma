<template>
  <section class="derma-mode-bar">
    <nav class="derma-mode-switch" :aria-label="__('Derma chart modes')">
      <button
        v-for="mode in modes"
        :key="mode.key"
        type="button"
        :class="{ active: activeMode === mode.key }"
        @click="$emit('update:activeMode', mode.key)"
      >
        <span>{{ mode.label }}</span>
        <small>{{ mode.hint }}</small>
      </button>
    </nav>

    <div class="derma-mode-context">
      <span v-if="activeProcedureLabel" class="active-procedure-chip">
        <b>{{ __("Active") }}</b>
        {{ activeProcedureLabel }}
      </span>
      <button type="button" class="ghost small" @click="$emit('new-procedure')">{{ __("New Procedure") }}</button>
      <button type="button" class="ghost small" @click="$emit('annotate')">{{ __("Annotate") }}</button>
      <button type="button" class="ghost small" @click="$emit('upload-photo')">{{ __("Upload Photo") }}</button>
      <button type="button" class="primary small" @click="$emit('complete')">{{ __("Complete Encounter") }}</button>
    </div>
  </section>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  modes: { type: Array, default: () => [] },
  activeMode: { type: String, default: "encounter" },
  activeProcedureLabel: { type: String, default: "" },
})

defineEmits(["update:activeMode", "new-procedure", "annotate", "upload-photo", "complete"])
</script>

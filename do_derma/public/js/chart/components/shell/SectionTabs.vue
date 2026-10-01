<template>
  <nav class="chart-tabs" :aria-label="__('Derma encounter sections')" data-test="derma-section-bar">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      class="chart-tabs-button"
      :data-test="`section-tab-${tab.key}`"
      :data-active="tab.key === active ? 'true' : 'false'"
      :aria-current="tab.key === active ? 'page' : undefined"
      @click="$emit('select', tab.key)"
    >
      <span>{{ tab.label }}</span>
      <i
        v-if="blocked.includes(tab.key)"
        class="chart-tabs-dot"
        :data-test="`tab-blocker-${tab.key}`"
        :title="__('Blocking completion')"
      ></i>
      <i v-if="filled.includes(tab.key)" class="chart-tabs-tick" :data-test="`${tab.key}-tick`">✓</i>
      <i v-if="counts[tab.key]" class="chart-tabs-count" :data-test="`${tab.key}-tab-count`">{{ counts[tab.key] }}</i>
    </button>
  </nav>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  tabs: { type: Array, default: () => [] },
  active: { type: String, default: "" },
  counts: { type: Object, default: () => ({}) },
  filled: { type: Array, default: () => [] },
  blocked: { type: Array, default: () => [] },
})

defineEmits(["select"])
</script>

<style scoped>
.chart-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: 12px;
  box-shadow: var(--chart-shadow);
  margin-bottom: 14px;
}

.chart-tabs-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--chart-text-soft);
  font-size: 13px;
  font-weight: 600;
}

.chart-tabs-button:hover {
  background: var(--chart-surface-muted);
}

.chart-tabs-button:focus-visible {
  outline: none;
  box-shadow: var(--chart-focus);
}

.chart-tabs-button[data-active="true"] {
  background: var(--chart-ok-soft);
  color: var(--chart-ok-text);
}

.chart-tabs-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--chart-danger);
}

.chart-tabs-tick {
  color: var(--chart-ok);
  font-style: normal;
}

.chart-tabs-count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--chart-surface-muted);
  border: 1px solid var(--chart-border);
  color: var(--chart-muted);
  font-size: 11px;
  font-style: normal;
  line-height: 16px;
  text-align: center;
}
</style>

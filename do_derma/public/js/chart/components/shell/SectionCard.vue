<template>
  <section class="chart-section-card" data-test="section-card">
    <header class="chart-section-card-header">
      <h2>{{ label }}</h2>
      <div v-if="$slots.actions" class="chart-section-card-actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="chart-section-card-body">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  label: { type: String, default: "" },
})
</script>

<style scoped>
.chart-section-card {
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: var(--chart-radius);
  box-shadow: var(--chart-shadow);
  min-width: 0;
}

.chart-section-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px 0;
}

.chart-section-card-header h2 {
  margin: 0;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chart-section-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-section-card-body {
  padding: 12px 18px 18px;
  min-width: 0;
}
</style>

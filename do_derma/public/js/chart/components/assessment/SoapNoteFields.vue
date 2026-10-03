<template>
  <div class="soap-fields" :class="{ 'is-reading': !editMode }" data-test="soap-note-fields">
    <p v-if="!layout.length" class="fields-empty">
      {{ __("SOAP Note fields are not installed on this site. Run bench migrate.") }}
    </p>

    <p v-else-if="!editMode && !documentedRows.length" class="fields-empty">
      {{ __("Nothing documented in this format.") }}
    </p>

    <template v-else>
      <label v-for="row in editMode ? layout : documentedRows" :key="row.fieldname" class="soap-field">
        <span class="soap-label chart-label">{{ row.label }}</span>
        <textarea
          v-if="editMode"
          v-model="draft[row.fieldname]"
          class="soap-input"
          rows="3"
          :data-test="`soap-${row.fieldname}`"
          :readonly="isReadOnly(row)"
          @input="emitDirty"
        ></textarea>
        <p v-else class="soap-readonly">{{ draft[row.fieldname] }}</p>
      </label>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  layout: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  editMode: { type: Boolean, default: false },
  docstatus: { type: [Number, null], default: null },
  allowOnSubmitFields: { type: Array, default: () => [] },
})

const emit = defineEmits(["dirty"])

const draft = ref({})
const savedSignature = ref("")

const allowOnSubmitSet = computed(() => new Set((props.allowOnSubmitFields || []).filter(Boolean)))
const isSubmittedEncounter = computed(() => Number(props.docstatus ?? 0) === 1)

const documentedRows = computed(() =>
  (props.layout || []).filter((row) => String(draft.value[row.fieldname] || "").trim())
)

watch(
  () => [props.values, props.layout],
  () => {
    const next = {}
    for (const row of props.layout || []) {
      if (row?.fieldname) next[row.fieldname] = props.values?.[row.fieldname] ?? ""
    }
    draft.value = next
    savedSignature.value = signature()
    emit("dirty", false)
  },
  { deep: true, immediate: true }
)

defineExpose({ collectPayload, markSaved })

function isReadOnly(row) {
  return isSubmittedEncounter.value && !allowOnSubmitSet.value.has(row.fieldname)
}

function signature() {
  try {
    return JSON.stringify(draft.value || {})
  } catch (e) {
    return ""
  }
}

function emitDirty() {
  emit("dirty", signature() !== savedSignature.value)
}

function collectPayload() {
  const payload = {}
  for (const row of props.layout || []) {
    if (!row?.fieldname) continue
    if (isReadOnly(row)) continue
    payload[row.fieldname] = draft.value[row.fieldname] ?? ""
  }
  return payload
}

function markSaved() {
  savedSignature.value = signature()
  emit("dirty", false)
}
</script>

<style scoped>
.soap-fields {
  display: grid;
  gap: 14px;
}

.fields-empty {
  border: 1px dashed var(--chart-border-strong);
  border-radius: 10px;
  padding: 14px;
  margin: 0;
  color: var(--chart-text-soft);
  font-size: 13px;
  background: var(--chart-surface-muted);
}

.soap-field {
  display: grid;
  gap: 6px;
}

.soap-input {
  width: 100%;
  resize: vertical;
  padding: 8px 10px;
  font: inherit;
  color: var(--chart-text);
  background: var(--chart-surface);
  border: 1px solid var(--chart-border-strong);
  border-radius: 8px;
  min-height: 72px;
  field-sizing: content;
}

.soap-input[readonly] {
  opacity: 0.7;
}

.soap-readonly {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--chart-text);
  white-space: pre-wrap;
}

.soap-fields.is-reading {
  gap: 10px;
}

.soap-fields.is-reading .soap-field {
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
  align-items: baseline;
}

@media (max-width: 1100px) {
  .soap-fields.is-reading .soap-field {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
  }
}
</style>

<template>
  <div class="soap-fields" data-test="soap-note-fields">
    <p v-if="!layout.length" class="fields-empty">
      {{ __("SOAP Note fields are not installed on this site. Run bench migrate.") }}
    </p>

    <p v-else-if="!editMode && !documentedRows.length" class="fields-empty">
      {{ __("Nothing documented in this format.") }}
    </p>

    <template v-else>
      <label v-for="row in editMode ? layout : documentedRows" :key="row.fieldname" class="soap-field">
        <span class="soap-label">{{ row.label }}</span>
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
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 14px;
  margin: 0;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
}

.soap-field {
  display: grid;
  gap: 6px;
}

.soap-label {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.soap-input {
  width: 100%;
  resize: vertical;
  padding: 8px 10px;
  font: inherit;
  color: #0f172a;
  background: var(--control-bg, #edeef0);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.soap-input:focus {
  outline: none;
  border-color: #087b75;
}

.soap-input[readonly] {
  opacity: 0.7;
}

.soap-readonly {
  margin: 0;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.5;
  color: #0f172a;
  white-space: pre-wrap;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}
</style>

<template>
  <tr ref="rowElement" class="prescription-row" data-test="prescription-row">
    <td class="medication-cell">
      <div
        v-if="openField === 'medication'"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker('medication')"
      ></div>
      <button
        v-else
        type="button"
        class="cell-input medication-name"
        :class="{ 'is-empty': !row.values.medication && !readOnly, 'is-missing': missing.includes('medication') }"
        data-field="medication"
        data-test="prescription-medication"
        :disabled="readOnly"
        @click="emit('open-picker', 'medication')"
      >
        {{ medicationLabel }}
      </button>
      <div
        v-if="openField === 'drug_code'"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker('drug_code')"
      ></div>
      <button
        v-else-if="row.linkedItems.length > 1 && !readOnly"
        type="button"
        class="drug-code-link"
        data-field="drug_code"
        data-test="prescription-choose-item"
        @click="emit('open-picker', 'drug_code')"
      >
        {{ row.values.drug_code || __("Choose item") }}
      </button>
      <small v-else-if="row.values.drug_code" class="drug-code">{{ row.values.drug_code }}</small>
      <span v-if="row.filling" class="filling" data-test="prescription-filling">
        <span class="chart-spinner" aria-hidden="true"></span>
        {{ __("Filling in dosage and duration...") }}
      </span>
    </td>
    <td v-for="column in LINK_COLUMNS" :key="column.field">
      <div
        v-if="openField === column.field"
        :ref="setPickerHost"
        class="picker-host"
        @keydown.escape.stop="closePicker(column.field)"
      ></div>
      <button
        v-else
        type="button"
        class="cell-input"
        :class="{ 'is-empty': !row.values[column.field], 'is-missing': missing.includes(column.field) }"
        :data-field="column.field"
        :data-test="`prescription-${column.field}`"
        :disabled="readOnly"
        @click="emit('open-picker', column.field)"
      >
        {{ row.values[column.field] || (readOnly ? "—" : column.placeholder) }}
      </button>
    </td>
    <td>
      <input
        type="number"
        min="0"
        step="1"
        class="cell-input repeats-input"
        data-test="prescription-repeats"
        :value="row.values.number_of_repeats_allowed"
        :disabled="readOnly"
        :aria-label="__('Repeats')"
        @input="emit('update', 'number_of_repeats_allowed', $event.target.value)"
      />
    </td>
    <td class="row-actions">
      <button
        v-if="!readOnly || row.values.comment"
        type="button"
        class="icon-btn"
        data-test="prescription-comment"
        :aria-label="__('Comment')"
        :aria-expanded="commentOpen ? 'true' : 'false'"
        @click="hidePreview(); emit('toggle-comment')"
        @mouseenter="showPreview"
        @focus="showPreview"
        @mouseleave="hidePreview"
        @blur="hidePreview"
      >
        <i class="fa-regular fa-comment"></i>
        <span v-if="row.values.comment" class="note-dot"></span>
      </button>
      <button
        v-if="!readOnly"
        type="button"
        class="icon-btn danger"
        data-test="prescription-delete"
        :title="__('Remove medication')"
        :aria-label="__('Remove medication')"
        @click="emit('remove')"
      >
        <i class="fa-regular fa-trash-can"></i>
      </button>
      <div v-if="preview" class="comment-preview" role="tooltip" :style="previewStyle">
        <span class="chart-label">{{ __("Comment") }}</span>
        <p>{{ preview.text }}</p>
      </div>
    </td>
  </tr>
  <tr v-if="commentOpen" class="comment-row">
    <td colspan="6">
      <textarea
        class="comment-input"
        rows="2"
        data-test="prescription-comment-input"
        :value="row.values.comment"
        :disabled="readOnly"
        :placeholder="__('Instructions for the patient or pharmacist')"
        @input="emit('update', 'comment', $event.target.value)"
      ></textarea>
    </td>
  </tr>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"

const __ = window.__ || ((text) => text)

const LINK_OPTIONS = {
  medication: "Medication",
  drug_code: "Item",
  dosage: "Prescription Dosage",
  period: "Prescription Duration",
  dosage_form: "Dosage Form",
}
const LINK_COLUMNS = [
  { field: "dosage", placeholder: __("Dosage") },
  { field: "period", placeholder: __("Duration") },
  { field: "dosage_form", placeholder: __("Form") },
]
const PREVIEW_DELAY_MS = 250
const PREVIEW_GAP_PX = 8

const props = defineProps({
  row: { type: Object, required: true },
  readOnly: { type: Boolean, default: false },
  openField: { type: String, default: "" },
  commentOpen: { type: Boolean, default: false },
  missing: { type: Array, default: () => [] },
})

const emit = defineEmits(["update", "open-picker", "close-picker", "toggle-comment", "remove"])

// Older rows carry only a drug name or item code.
const medicationLabel = computed(() => {
  const { medication, drug_code: drugCode } = props.row.values
  if (medication) return medication
  if (props.readOnly) return props.row.original.drug_name || drugCode || "—"
  return __("Choose medication")
})

const rowElement = ref(null)
const preview = ref(null)
let pickerHost = null
let control = null
let previewTimer = null

watch(
  () => props.openField,
  async (field) => {
    if (!field) return
    await nextTick()
    mountPicker(field)
  },
  { immediate: true }
)

onBeforeUnmount(hidePreview)

function setPickerHost(element) {
  pickerHost = element || null
}

function mountPicker(field) {
  if (!pickerHost || !window.frappe?.ui?.form?.make_control) return
  pickerHost.innerHTML = ""
  control = frappe.ui.form.make_control({
    parent: pickerHost,
    df: {
      fieldtype: "Link",
      fieldname: field,
      options: LINK_OPTIONS[field],
      placeholder: __(LINK_OPTIONS[field]),
      only_select: 1,
      get_query: field === "drug_code" ? () => ({ filters: { name: ["in", props.row.linkedItems] } }) : undefined,
      change: () => {
        emit("update", field, control.get_value() || "")
        closePicker(field)
      },
    },
    render_input: true,
  })
  // Seeded without firing `change`; desk's blur only reports values that differ from `last_value`.
  const current = props.row.values[field] || ""
  control.set_input(current)
  control.last_value = current
  control.$input?.focus()
}

// Save calls this so a typed value desk is still validating reaches the row first.
async function commitPicker() {
  if (!props.openField || !control?.$input) return
  await control.parse_validate_and_set_in_model(control.get_input_value())
}

defineExpose({ commitPicker })

function closePicker(field) {
  emit("close-picker")
  nextTick(() => rowElement.value?.querySelector(`[data-field="${field}"]`)?.focus())
}

function showPreview(event) {
  const text = props.row.values.comment
  if (!text || props.commentOpen) return
  const anchor = event.currentTarget.getBoundingClientRect()
  clearTimeout(previewTimer)
  previewTimer = setTimeout(
    () => {
      preview.value = { text, anchor }
    },
    event.type === "focus" ? 0 : PREVIEW_DELAY_MS
  )
}

function hidePreview() {
  clearTimeout(previewTimer)
  preview.value = null
}

// Opens to the left of the icon, and upward in the lower half so it never runs off the window.
const previewStyle = computed(() => {
  const anchor = preview.value?.anchor
  if (!anchor) return {}
  const style = { right: `${window.innerWidth - anchor.left + PREVIEW_GAP_PX}px` }
  if (anchor.top > window.innerHeight / 2) {
    style.bottom = `${window.innerHeight - anchor.bottom}px`
  } else {
    style.top = `${anchor.top}px`
  }
  return style
})
</script>

<style scoped>
.cell-input {
  display: block;
  width: 100%;
  min-height: 30px;
  padding: 5px 8px;
  border: 1px solid var(--chart-border);
  border-radius: 6px;
  background: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

.cell-input:hover:not(:disabled),
.cell-input:focus-visible {
  border-color: var(--chart-accent);
  outline: none;
}

.cell-input.is-empty {
  color: var(--chart-muted);
}

.cell-input.is-missing {
  border-color: var(--chart-danger-text);
  background: var(--chart-danger-soft);
}

.cell-input:disabled {
  padding-left: 0;
  border-color: transparent;
  background: transparent;
  color: var(--chart-text);
  opacity: 1;
  cursor: default;
}

.medication-name {
  font-weight: 600;
}

.repeats-input {
  cursor: text;
}

.drug-code,
.drug-code-link {
  display: block;
  margin-top: 3px;
  color: var(--chart-muted);
  font-size: 12px;
}

.drug-code-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--chart-accent-strong);
  text-decoration: underline dotted;
  cursor: pointer;
}

.filling {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  color: var(--chart-muted);
  font-size: 12px;
}

.picker-host :deep(.frappe-control) {
  margin-bottom: 0;
}

.picker-host :deep(.control-label) {
  display: none;
}

.row-actions {
  white-space: nowrap;
  text-align: right;
}

.icon-btn {
  position: relative;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chart-muted);
  font-size: 13px;
  cursor: pointer;
}

.icon-btn:hover:not(:disabled),
.icon-btn:focus-visible {
  background: var(--chart-surface-muted);
  color: var(--chart-text);
}

.icon-btn.danger:hover:not(:disabled),
.icon-btn.danger:focus-visible {
  background: var(--chart-danger-soft);
  color: var(--chart-danger-text);
}

.note-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--chart-ok);
}

/* Fixed: a positioned cell ancestor must not clip it. */
.comment-preview {
  position: fixed;
  z-index: 1050;
  width: min(320px, calc(100vw - 32px));
  padding: 10px 12px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: var(--chart-shadow);
  text-align: left;
  white-space: normal;
  pointer-events: none;
}

.comment-preview p {
  margin: 4px 0 0;
  color: var(--chart-text);
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-line;
}

.comment-input {
  width: 100%;
  min-height: 56px;
  padding: 6px 8px;
  border: 1px solid var(--chart-border);
  border-radius: 6px;
  background: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
  resize: vertical;
}

.comment-input:focus {
  border-color: var(--chart-accent);
  outline: none;
}
</style>

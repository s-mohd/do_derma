<template>
  <div class="mark-consumables" data-test="mark-consumables">
    <div class="mark-consumables-head">
      <strong>{{ markLabel }}</strong>
      <span v-if="saving" class="text-muted">{{ __("Saving...") }}</span>
    </div>

    <p v-if="error && failedIndex === null" class="consumables-error" data-test="consumables-error">
      {{ error }}
    </p>

    <table v-if="draftRows.length" class="consumables-table">
      <thead>
        <tr>
          <th>{{ __("Material") }}</th>
          <th>{{ __("Qty") }}</th>
          <th>{{ __("Unit") }}</th>
          <th>{{ __("Batch") }}</th>
          <th v-if="!readOnly"></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(row, index) in draftRows" :key="`${row.item_code}-${index}`">
        <tr :class="{ overridden: row.is_overridden }" data-test="consumable-line">
          <td>
            <span>{{ row.item_name || row.item_code }}</span>
            <span v-if="row.is_overridden" class="consumable-flag" :title="__('Differs from the template')">
              {{ __("Changed") }}
            </span>
          </td>
          <td>
            <span v-if="readOnly">{{ row.qty }}</span>
            <input
              v-else
              type="number"
              min="0"
              step="any"
              class="inline-input consumable-qty"
              data-test="consumable-qty"
              :value="row.qty"
              @blur="commitQty(index, $event.target.value)"
              @keyup.enter="$event.target.blur()"
            />
          </td>
          <td>
            <div v-if="isEditingLink(index, 'uom')" ref="linkHost" class="consumable-link-host"></div>
            <button v-else-if="!readOnly" type="button" class="link-cell" @click="editLink(index, 'uom')">
              {{ row.uom || __("Set unit") }}
            </button>
            <span v-else>{{ row.uom || "-" }}</span>
          </td>
          <td>
            <div v-if="isEditingLink(index, 'batch_no')" ref="linkHost" class="consumable-link-host"></div>
            <button
              v-else-if="!readOnly"
              type="button"
              class="link-cell"
              data-test="consumable-batch"
              @click="editLink(index, 'batch_no')"
            >
              {{ row.batch_no || __("Set batch") }}
            </button>
            <span v-else>{{ row.batch_no || "-" }}</span>
          </td>
          <td v-if="!readOnly">
            <button
              type="button"
              class="ghost small"
              data-test="consumable-remove"
              :title="__('Remove material')"
              @click="removeRow(index)"
            >
              {{ __("Remove") }}
            </button>
          </td>
        </tr>
        <tr v-if="error && failedIndex === index" class="consumables-error-row">
          <td :colspan="readOnly ? 4 : 5" class="consumables-error" data-test="consumables-error">
            {{ error }}
          </td>
        </tr>
        </template>
      </tbody>
    </table>

    <p v-else class="text-muted consumables-empty">{{ __("No materials recorded.") }}</p>

    <div v-if="removed.length" class="consumables-removed" data-test="consumables-removed">
      <span class="text-muted">{{ __("Removed from the template") }}</span>
      <span v-for="(row, index) in removed" :key="`removed-${index}`" class="removed-chip">
        {{ row.item_name || row.item_code }}
        <button v-if="!readOnly" type="button" class="ghost small" @click="restore(row)">
          {{ __("Restore") }}
        </button>
      </span>
    </div>

    <div v-if="!readOnly" class="consumables-actions">
      <button v-if="!adding" type="button" class="ghost small" data-test="consumable-add" @click="startAdd">
        {{ __("Add material") }}
      </button>
      <button
        type="button"
        class="ghost small"
        data-test="consumable-reset"
        :disabled="!defaults.length"
        :title="__('Restore the template list')"
        @click="resetToTemplate"
      >
        {{ __("Reset to template") }}
      </button>
    </div>

    <div v-if="adding && !readOnly" class="consumables-add" data-test="consumable-add-row">
      <div v-if="isEditingLink(NEW_ROW, 'item_code')" ref="linkHost" class="consumable-link-host"></div>
      <button v-else type="button" class="link-cell" @click="editLink(NEW_ROW, 'item_code')">
        {{ draftNew.item_code || __("Pick an item") }}
      </button>
      <input v-model="draftNew.qty" type="number" min="0" step="any" class="inline-input" />
      <button type="button" class="ghost small" :disabled="!canAdd" @click="confirmAdd">{{ __("Add") }}</button>
      <button type="button" class="ghost small" @click="cancelAdd">{{ __("Cancel") }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)
const NEW_ROW = -1

const props = defineProps({
  markName: { type: String, required: true },
  markLabel: { type: String, default: "" },
  rows: { type: Array, default: () => [] },
  removed: { type: Array, default: () => [] },
  defaults: { type: Array, default: () => [] },
  readOnly: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
})

const emit = defineEmits(["change"])

// The panel's copy is the owner. This draft only survives a refused save, so the
// clinician's value stays on screen instead of being thrown away.
const draftRows = ref(clone(props.rows))
const draftNew = ref(emptyDraft())
const adding = ref(false)
const linkEditor = ref(null)
const linkHost = ref(null)
// Which line the last change came from, so a refused save reports itself where it happened.
const failedIndex = ref(null)
let linkControl = null

watch(
  () => props.rows,
  (value) => {
    draftRows.value = clone(value)
    failedIndex.value = null
  }
)

const canAdd = computed(() => !!draftNew.value.item_code && Number(draftNew.value.qty) > 0)

function clone(rows) {
  return (rows || []).map((row) => ({ ...row }))
}

function emptyDraft() {
  return { item_code: "", qty: 1 }
}

function submit(rows, index = null) {
  failedIndex.value = index
  emit(
    "change",
    rows.map((row) => ({ ...row }))
  )
}

function replaceRow(index, changes) {
  const next = draftRows.value.map((row, position) => (position === index ? { ...row, ...changes } : row))
  draftRows.value = next
  submit(next, index)
}

function commitQty(index, value) {
  const quantity = Number(value)
  const row = draftRows.value[index]
  if (!row || Number.isNaN(quantity) || quantity === Number(row.qty)) return
  replaceRow(index, { qty: quantity })
}

function removeRow(index) {
  submit(draftRows.value.filter((_, position) => position !== index))
}

function restore(row) {
  submit([...draftRows.value, { ...row }])
}

function resetToTemplate() {
  submit(clone(props.defaults))
}

function startAdd() {
  draftNew.value = emptyDraft()
  adding.value = true
  editLink(NEW_ROW, "item_code")
}

function cancelAdd() {
  adding.value = false
  closeLinkEditor()
}

function confirmAdd() {
  if (!canAdd.value) return
  const row = { item_code: draftNew.value.item_code, qty: Number(draftNew.value.qty) }
  adding.value = false
  closeLinkEditor()
  submit([...draftRows.value, row])
}

function isEditingLink(index, field) {
  return linkEditor.value?.index === index && linkEditor.value?.field === field
}

function editLink(index, field) {
  if (props.readOnly) return
  linkEditor.value = { index, field }
  nextTick(mountLinkControl)
}

function closeLinkEditor() {
  linkEditor.value = null
  linkControl = null
}

const LINK_FIELDS = {
  item_code: { options: "Item", label: __("Item") },
  uom: { options: "UOM", label: __("Unit") },
  batch_no: { options: "Batch", label: __("Batch") },
}

function mountLinkControl() {
  const editor = linkEditor.value
  const host = Array.isArray(linkHost.value) ? linkHost.value[0] : linkHost.value
  if (!editor || !host || !window.frappe?.ui?.form?.make_control) return

  const spec = LINK_FIELDS[editor.field]
  const current = editor.index === NEW_ROW ? draftNew.value : draftRows.value[editor.index] || {}
  host.innerHTML = ""
  linkControl = frappe.ui.form.make_control({
    parent: host,
    df: {
      fieldtype: "Link",
      fieldname: editor.field,
      options: spec.options,
      label: spec.label,
      placeholder: spec.label,
      only_select: 1,
      get_query: () => ({ filters: linkFilters(editor, current) }),
      change: () => applyLink(linkControl?.get_value()),
    },
    render_input: true,
  })
  linkControl.set_value(current[editor.field] || "")
  linkControl.$input?.focus()
}

function linkFilters(editor, row) {
  if (editor.field !== "batch_no") return {}
  return row.item_code ? { item: row.item_code } : {}
}

function applyLink(value) {
  const editor = linkEditor.value
  if (!editor || !value) return
  if (editor.index === NEW_ROW) {
    draftNew.value = { ...draftNew.value, item_code: value }
    closeLinkEditor()
    return
  }
  const row = draftRows.value[editor.index]
  const index = editor.index
  closeLinkEditor()
  if (!row || value === row[editor.field]) return
  replaceRow(index, { [editor.field]: value })
}
</script>

<style scoped>
.mark-consumables {
  padding: 8px 12px;
  border-top: 1px solid var(--border-color, #e5e7eb);
}

.mark-consumables-head {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 6px;
}

.consumables-table {
  width: 100%;
  font-size: 12px;
}

.consumables-table td,
.consumables-table th {
  padding: 4px 6px;
  text-align: left;
}

.consumables-table tr.overridden {
  background: var(--fg-hover-color, #f6f8fa);
}

.consumable-flag {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 8px;
  font-size: 10px;
  text-transform: uppercase;
  background: var(--yellow-100, #fef3c7);
  color: var(--yellow-700, #a16207);
}

.consumables-error {
  color: var(--red-600, #dc2626);
  margin: 4px 0;
}

.consumable-qty {
  width: 80px;
}

.link-cell {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-color, #1f272e);
  text-decoration: underline dotted;
  cursor: pointer;
}

.consumable-link-host {
  min-width: 140px;
}

.consumables-removed,
.consumables-actions,
.consumables-add {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 6px;
}

.removed-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--fg-hover-color, #f6f8fa);
  color: var(--text-muted, #6b7280);
}
</style>

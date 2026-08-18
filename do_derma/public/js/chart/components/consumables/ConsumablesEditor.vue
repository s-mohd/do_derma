<template>
  <div class="mark-consumables" data-test="mark-consumables">
    <div class="mark-consumables-head">
      <strong>{{ label }}</strong>
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
            <select
              v-if="!readOnly"
              class="inline-input consumable-select"
              data-test="consumable-uom"
              :value="row.uom"
              :disabled="unitOptions(row).length < 2"
              @change="commitField(index, 'uom', $event.target.value)"
            >
              <option v-for="unit in unitOptions(row)" :key="unit" :value="unit">{{ unit }}</option>
            </select>
            <span v-else>{{ row.uom || "-" }}</span>
          </td>
          <td>
            <select
              v-if="!readOnly && isBatchTracked(row.item_code)"
              class="inline-input consumable-select"
              data-test="consumable-batch"
              :class="{ 'consumable-missing': !row.batch_no }"
              :value="row.batch_no || ''"
              @change="commitField(index, 'batch_no', $event.target.value)"
            >
              <option value="">{{ __("Pick a batch") }}</option>
              <option v-for="batch in batchOptions(row)" :key="batch.name" :value="batch.name">
                {{ batchLabel(batch) }}
              </option>
            </select>
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
      <div v-if="pickingItem" ref="itemHost" class="consumable-link-host"></div>
      <button v-else type="button" class="link-cell" @click="pickItem">
        {{ draftNew.item_code || __("Pick an item") }}
      </button>
      <input v-model="draftNew.qty" type="number" min="0" step="any" class="inline-input consumable-qty" />
      <select
        v-if="draftNew.item_code"
        v-model="draftNew.uom"
        class="inline-input consumable-select"
        data-test="consumable-new-uom"
        :disabled="unitOptions(draftNew).length < 2"
      >
        <option v-for="unit in unitOptions(draftNew)" :key="unit" :value="unit">{{ unit }}</option>
      </select>
      <select
        v-if="isBatchTracked(draftNew.item_code)"
        v-model="draftNew.batch_no"
        class="inline-input consumable-select"
        data-test="consumable-new-batch"
      >
        <option value="">{{ __("Pick a batch") }}</option>
        <option v-for="batch in batchOptions(draftNew)" :key="batch.name" :value="batch.name">
          {{ batchLabel(batch) }}
        </option>
      </select>
      <span v-if="isBatchTracked(draftNew.item_code) && !batchOptions(draftNew).length" class="consumables-error">
        {{ __("No batch of this item has stock left.") }}
      </span>
      <button type="button" class="ghost small" :disabled="!canAdd" @click="confirmAdd">{{ __("Add") }}</button>
      <button type="button" class="ghost small" @click="cancelAdd">{{ __("Cancel") }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  ownerDoctype: { type: String, required: true },
  ownerName: { type: String, required: true },
  label: { type: String, default: "" },
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
const pickingItem = ref(false)
const itemHost = ref(null)
// Units and batches per item, fetched once the panel is open and reused by every row.
const itemOptions = ref({})
// Which line the last change came from, so a refused save reports itself where it happened.
const failedIndex = ref(null)
let itemControl = null

watch(
  () => props.rows,
  (value) => {
    draftRows.value = clone(value)
    failedIndex.value = null
    loadOptionsForRows()
  }
)

onMounted(loadOptionsForRows)

const canAdd = computed(() => {
  const draft = draftNew.value
  if (!draft.item_code || Number(draft.qty) <= 0) return false
  return !isBatchTracked(draft.item_code) || !!draft.batch_no
})

function clone(rows) {
  return (rows || []).map((row) => ({ ...row }))
}

function emptyDraft() {
  return { item_code: "", qty: 1, uom: "", batch_no: "" }
}

function optionsOf(itemCode) {
  return itemOptions.value[itemCode] || null
}

function unitOptions(row) {
  const options = optionsOf(row?.item_code)
  const units = options?.uoms || []
  if (row?.uom && !units.includes(row.uom)) return [row.uom, ...units]
  return units.length ? units : [row?.uom].filter(Boolean)
}

function batchOptions(row) {
  return optionsOf(row?.item_code)?.batches || []
}

function isBatchTracked(itemCode) {
  return !!optionsOf(itemCode)?.has_batch_no
}

function batchLabel(batch) {
  const expiry = batch.expiry_date ? ` · ${__("exp")} ${batch.expiry_date}` : ""
  return `${batch.name} (${batch.qty})${expiry}`
}

function loadOptionsForRows() {
  if (props.readOnly) return
  for (const itemCode of new Set(draftRows.value.map((row) => row.item_code).filter(Boolean))) {
    loadOptions(itemCode)
  }
}

async function loadOptions(itemCode) {
  if (!itemCode || itemOptions.value[itemCode]) return null
  const resp = await frappe.call({
    method: "do_derma.api.get_consumable_item_options",
    args: { item_code: itemCode, owner_doctype: props.ownerDoctype, owner_name: props.ownerName },
    silent: true,
  })
  if (!resp?.message) return null
  itemOptions.value = { ...itemOptions.value, [itemCode]: resp.message }
  return resp.message
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

function commitField(index, field, value) {
  const row = draftRows.value[index]
  if (!row || value === (row[field] || "")) return
  replaceRow(index, { [field]: value })
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
  pickItem()
}

function cancelAdd() {
  adding.value = false
  closeItemPicker()
}

function confirmAdd() {
  if (!canAdd.value) return
  const draft = draftNew.value
  const row = {
    item_code: draft.item_code,
    qty: Number(draft.qty),
    uom: draft.uom,
    batch_no: draft.batch_no || null,
  }
  adding.value = false
  closeItemPicker()
  submit([...draftRows.value, row])
}

function pickItem() {
  if (props.readOnly) return
  pickingItem.value = true
  nextTick(mountItemControl)
}

function closeItemPicker() {
  pickingItem.value = false
  itemControl = null
}

function mountItemControl() {
  const host = Array.isArray(itemHost.value) ? itemHost.value[0] : itemHost.value
  if (!host || !window.frappe?.ui?.form?.make_control) return

  host.innerHTML = ""
  itemControl = frappe.ui.form.make_control({
    parent: host,
    df: {
      fieldtype: "Link",
      fieldname: "item_code",
      options: "Item",
      label: __("Item"),
      placeholder: __("Item"),
      only_select: 1,
      change: () => applyItem(itemControl?.get_value()),
    },
    render_input: true,
  })
  itemControl.$input?.focus()
}

async function applyItem(itemCode) {
  if (!itemCode || itemCode === draftNew.value.item_code) return
  closeItemPicker()
  const options = await loadOptions(itemCode)
  const known = options || optionsOf(itemCode)
  draftNew.value = { ...draftNew.value, item_code: itemCode, uom: known?.stock_uom || "", batch_no: "" }
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

.consumable-select {
  min-width: 110px;
}

.consumable-missing {
  border-color: var(--red-400, #f87171);
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

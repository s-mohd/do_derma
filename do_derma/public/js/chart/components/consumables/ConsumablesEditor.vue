<template>
  <div class="mark-consumables" data-test="mark-consumables">
    <div class="mark-consumables-head">
      <span class="chart-label">{{ label }}</span>
      <span class="chart-pill" data-tone="neutral" data-test="consumables-count">{{ draftRows.length }}</span>
      <span v-if="saving" class="chart-pill" data-tone="neutral">{{ __("Saving...") }}</span>
    </div>

    <p v-if="error && failedIndex === null" class="consumables-error" data-test="consumables-error">
      {{ error }}
    </p>

    <table v-if="draftRows.length" class="consumables-table">
      <thead>
        <tr>
          <th class="chart-label">{{ __("Material") }}</th>
          <th class="chart-label">{{ __("Qty") }}</th>
          <th class="chart-label">{{ __("Unit") }}</th>
          <th class="chart-label">{{ __("Batch") }}</th>
          <th v-if="!readOnly" class="chart-label"><span class="sr-only">{{ __("Actions") }}</span></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(row, index) in draftRows" :key="`${row.item_code}-${index}`">
        <tr :class="{ overridden: row.is_overridden }" data-test="consumable-line">
          <td>
            <span>{{ row.item_name || row.item_code }}</span>
            <span v-if="row.is_overridden" class="chart-pill" data-tone="neutral" :title="__('Differs from the template')">
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
            <template v-if="!readOnly">
              <select
                class="inline-input consumable-select"
                data-test="consumable-uom"
                :value="row.uom"
                :disabled="isUnitLocked(row)"
                :title="unitTitle(row)"
                @change="commitField(index, 'uom', $event.target.value)"
              >
                <option v-for="unit in unitOptions(row)" :key="unit" :value="unit">
                  {{ unitLabel(row, unit) }}
                </option>
              </select>
              <span v-if="isOptionsLoading(row)" class="text-muted consumable-hint">
                {{ __("Loading units...") }}
              </span>
              <span v-else-if="isUnitUnknown(row)" class="chart-pill" data-tone="danger" :title="unitTitle(row)">
                {{ __("No conversion") }}
              </span>
            </template>
            <span v-else>{{ row.uom || "-" }}</span>
          </td>
          <td>
            <div class="batch-cell">
              <div v-if="hasBatchFacts(row)" class="consumable-batch" data-test="consumable-batch-facts">
                <b v-if="readOnly && row.batch.name">{{ row.batch.name }}</b>
                <span
                  v-if="row.batch.available_qty !== null"
                  class="chart-pill"
                  :data-tone="row.batch.is_short ? 'caution' : 'neutral'"
                  data-test="consumable-batch-stock"
                >{{ __("{0} left", [row.batch.available_qty]) }}</span>
                <span
                  v-if="row.batch.expiry_date"
                  class="chart-pill"
                  :data-tone="expiryTone(row.batch)"
                  data-test="consumable-batch-expiry"
                >{{ expiryLabel(row.batch) }}</span>
              </div>
              <select
                v-if="!readOnly && isBatchTracked(row.item_code)"
                class="inline-input consumable-select consumable-change"
                data-test="consumable-batch"
                :class="{ 'consumable-missing': !row.batch_no }"
                :value="row.batch_no || ''"
                @change="commitField(index, 'batch_no', $event.target.value)"
              >
                <option value="">{{ row.batch_no ? __("Change lot") : __("Pick a batch") }}</option>
                <option v-for="batch in batchOptions(row)" :key="batch.name" :value="batch.name">
                  {{ batchLabel(batch) }}
                </option>
              </select>
              <span v-else-if="isOptionsLoading(row)" class="text-muted consumable-hint">
                {{ __("Loading batches...") }}
              </span>
              <span v-else-if="readOnly && row.batch_no && !row.batch?.name">{{ row.batch_no }}</span>
            </div>
          </td>
          <td v-if="!readOnly" class="row-actions">
            <button
              type="button"
              class="icon-btn danger"
              data-test="consumable-remove"
              :title="__('Remove material')"
              :aria-label="__('Remove material')"
              @click="removeRow(index)"
            >
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </td>
        </tr>
        <tr v-if="row.readiness_message" class="consumable-notice-row">
          <td :colspan="readOnly ? 4 : 5">
            <span class="chart-pill" :data-tone="row.readiness_tone" data-test="consumable-notice">{{ row.readiness_message }}</span>
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

    <p v-else class="consumables-empty">{{ __("No materials recorded.") }}</p>

    <div v-if="removed.length" class="consumables-removed" data-test="consumables-removed">
      <span class="consumables-muted">{{ __("Removed from the template") }}</span>
      <span v-for="(row, index) in removed" :key="`removed-${index}`" class="removed-chip chart-pill" data-tone="neutral">
        {{ row.item_name || row.item_code }}
        <button v-if="!readOnly" type="button" class="restore-btn" @click="restore(row)">
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
      <div v-if="pickingItem" ref="itemHost" class="consumable-link-host" @keydown.escape.stop="cancelItemPicker"></div>
      <button v-else ref="itemButton" type="button" class="cell-input" :class="{ 'is-empty': !draftNew.item_code }" @click="pickItem">
        {{ draftNew.item_code || __("Pick an item") }}
      </button>
      <input v-model="draftNew.qty" type="number" min="0" step="any" class="inline-input consumable-qty" />
      <select
        v-if="draftNew.item_code"
        v-model="draftNew.uom"
        class="inline-input consumable-select"
        data-test="consumable-new-uom"
        :disabled="isUnitLocked(draftNew)"
        :title="unitTitle(draftNew)"
      >
        <option v-for="unit in unitOptions(draftNew)" :key="unit" :value="unit">
          {{ unitLabel(draftNew, unit) }}
        </option>
      </select>
      <span v-if="isOptionsLoading(draftNew)" class="text-muted consumable-hint">
        {{ __("Loading units...") }}
      </span>
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
const itemButton = ref(null)
// Units and batches per item, fetched once the panel is open and reused by every row.
const itemOptions = ref({})
// The items whose options are still in flight, so a row says so instead of looking single-unit.
const pendingItems = ref([])
const optionRequests = new Map()
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
  // The item's convertible units come first and always stay listed: a stored unit the item
  // cannot convert is appended, so picking a good one never empties the list and locks the row.
  const units = optionsOf(row?.item_code)?.uoms || []
  if (row?.uom && !units.includes(row.uom)) return [...units, row.uom]
  return units.length ? units : [row?.uom].filter(Boolean)
}

function isOptionsLoading(row) {
  return !!row?.item_code && pendingItems.value.includes(row.item_code)
}

function isUnitUnknown(row) {
  const options = optionsOf(row?.item_code)
  return !!options && !!row?.uom && !options.uoms.includes(row.uom)
}

function isUnitLocked(row) {
  // Only a genuinely single-unit item locks. Until the item's options are in hand the list is
  // unknown, so the control stays open rather than looking broken.
  return !!optionsOf(row?.item_code) && unitOptions(row).length < 2
}

function unitLabel(row, unit) {
  const options = optionsOf(row?.item_code)
  if (!options || options.uoms.includes(unit)) return unit
  return `${unit} · ${__("no conversion")}`
}

function unitTitle(row) {
  if (isOptionsLoading(row)) return __("Loading units...")
  const stockUnit = optionsOf(row?.item_code)?.stock_uom
  if (isUnitUnknown(row)) {
    return __("{0} does not convert to the stock unit {1}. Pick a listed unit.")
      .replace("{0}", row.uom)
      .replace("{1}", stockUnit || "")
  }
  if (isUnitLocked(row)) {
    return __("This item is only stocked in {0}.").replace("{0}", stockUnit || row?.uom || "")
  }
  return ""
}

function batchOptions(row) {
  return optionsOf(row?.item_code)?.batches || []
}

function isBatchTracked(itemCode) {
  return !!optionsOf(itemCode)?.has_batch_no
}

function batchLabel(batch) {
  const expiry = batch.expiry_date ? ` · ${__("exp")} ${formatDate(batch.expiry_date)}` : ""
  return `${batch.name} · ${__("{0} left", [batch.qty])}${expiry}`
}

function formatDate(value) {
  return window.frappe?.datetime?.str_to_user?.(value) || value
}

function hasBatchFacts(row) {
  return Boolean(row.batch && (row.batch.name || row.batch.available_qty !== null))
}

function expiryTone(batch) {
  if (batch.is_expired) return "danger"
  return batch.is_expiring_soon ? "caution" : "neutral"
}

function expiryLabel(batch) {
  if (batch.is_expired) return __("expired {0}", [formatDate(batch.expiry_date)])
  if (!batch.is_expiring_soon) return formatDate(batch.expiry_date)
  return batch.days_to_expiry === 0 ? __("expires today") : __("in {0} days", [batch.days_to_expiry])
}

function loadOptionsForRows() {
  if (props.readOnly) return
  for (const itemCode of new Set(draftRows.value.map((row) => row.item_code).filter(Boolean))) {
    loadOptions(itemCode)
  }
}

async function loadOptions(itemCode) {
  if (!itemCode) return null
  if (itemOptions.value[itemCode]) return itemOptions.value[itemCode]
  // The in-flight call is shared rather than skipped, so a second asker waits for the same
  // answer instead of being told there is none and settling for a blank unit.
  if (!optionRequests.has(itemCode)) optionRequests.set(itemCode, fetchOptions(itemCode))
  return optionRequests.get(itemCode)
}

async function fetchOptions(itemCode) {
  pendingItems.value = [...pendingItems.value, itemCode]
  try {
    const resp = await frappe.call({
      method: "do_derma.api.get_consumable_item_options",
      args: { item_code: itemCode, owner_doctype: props.ownerDoctype, owner_name: props.ownerName },
      silent: true,
    })
    if (!resp?.message) return null
    itemOptions.value = { ...itemOptions.value, [itemCode]: resp.message }
    return resp.message
  } finally {
    pendingItems.value = pendingItems.value.filter((code) => code !== itemCode)
    optionRequests.delete(itemCode)
  }
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

function cancelItemPicker() {
  closeItemPicker()
  nextTick(() => itemButton.value?.focus())
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
  padding: 10px 12px;
  border-top: 1px solid var(--chart-border);
}

.mark-consumables-head {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.consumables-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.consumables-table th {
  padding: 6px 8px;
  border-bottom: 1px solid var(--chart-border);
  text-align: left;
}

.consumables-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--chart-surface-muted);
  color: var(--chart-text);
  text-align: left;
  vertical-align: middle;
}

.consumables-table td .chart-pill {
  margin-left: 6px;
}

.inline-input,
.cell-input {
  min-height: 30px;
  padding: 4px 8px;
  border: 1px solid var(--chart-border);
  border-radius: 6px;
  background: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
}

.inline-input:focus,
.cell-input:focus-visible {
  border-color: var(--chart-accent);
  outline: none;
}

.inline-input:disabled {
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
}

.cell-input {
  min-width: 180px;
  text-align: left;
  cursor: pointer;
}

.cell-input.is-empty {
  color: var(--chart-muted);
}

.consumable-hint,
.consumables-muted,
.consumables-empty {
  color: var(--chart-muted);
  font-size: 12px;
}

.consumable-hint {
  margin-left: 6px;
}

.consumables-empty {
  margin: 0;
}

.consumables-error {
  margin: 4px 0;
  color: var(--chart-danger-text);
  font-size: 12px;
}

.consumable-qty {
  width: 80px;
}

.consumable-select {
  min-width: 110px;
}

.consumable-missing {
  border-color: var(--chart-danger);
}

.consumable-link-host {
  min-width: 180px;
}

.consumable-link-host :deep(.frappe-control) {
  margin-bottom: 0;
}

.consumable-link-host :deep(.control-label) {
  display: none;
}

.consumables-removed,
.consumables-actions,
.consumables-add {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 8px;
}

.removed-chip {
  gap: 6px;
}

.restore-btn {
  padding: 0;
  border: 0;
  background: none;
  color: var(--chart-accent-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.restore-btn:hover {
  text-decoration: underline;
}

.consumable-batch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.consumable-batch .chart-pill {
  margin-left: 0;
}

.batch-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

/* The select reads first; the lot's stock and expiry pills follow it. */
.batch-cell .consumable-select {
  order: -1;
}

.row-actions {
  width: 44px;
  text-align: right;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chart-muted);
  font-size: 13px;
  cursor: pointer;
}

.icon-btn.danger:hover:not(:disabled),
.icon-btn.danger:focus-visible {
  background: var(--chart-danger-soft);
  color: var(--chart-danger-text);
}

.consumable-notice-row td {
  padding-top: 0;
  border-top: 0;
}

.consumable-notice-row .chart-pill {
  margin-left: 0;
  white-space: normal;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>

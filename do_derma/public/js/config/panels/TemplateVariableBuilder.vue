<template>
  <div class="config-builder" data-test="config-variable-builder" :data-template="template">
    <header class="config-section-head">
      <h4>{{ __("Variables — {0}", [title || template]) }}</h4>
      <div class="config-builder-actions">
        <button type="button" class="btn btn-default btn-xs" data-test="config-close-variables" @click="emit('close')">
          {{ __("Back to list") }}
        </button>
        <button
          type="button"
          class="btn btn-primary btn-xs"
          data-test="config-save-variables"
          :disabled="saving || !!collision || hasBlankLabel"
          @click="save"
        >
          {{ saving ? __("Saving…") : __("Save variables") }}
        </button>
      </div>
    </header>

    <p v-if="loading" class="config-status" data-test="config-variable-loading">{{ __("Loading variables…") }}</p>
    <p v-else-if="loadError" class="config-status error" data-test="config-variable-error">{{ loadError }}</p>

    <template v-else>
      <p v-if="collision" class="config-status warning" data-test="config-variable-collision">
        {{ __("{0} and {1} both become the fieldname {2}.", [collision.first, collision.second, collision.fieldname]) }}
      </p>
      <p v-if="hasBlankLabel" class="config-status warning" data-test="config-variable-blank-label">
        {{ __("Every variable needs a label.") }}
      </p>
      <p class="config-status" data-test="config-variable-required-summary">
        {{
          requiredFieldnames.length
            ? __("Required: {0}", [requiredFieldnames.join(", ")])
            : __("This template requires nothing.")
        }}
      </p>
      <p v-if="saveError" class="config-status error" data-test="config-variable-error">{{ saveError }}</p>

      <p v-if="!rows.length" class="config-status" data-test="config-variables-empty">
        {{ __("This template records nothing yet.") }}
      </p>

      <table v-else class="config-table">
        <thead>
          <tr>
            <th>{{ __("Label") }}</th>
            <th>{{ __("Fieldname") }}</th>
            <th>{{ __("Type") }}</th>
            <th>{{ __("Options") }}</th>
            <th>{{ __("Required") }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in rows"
            :key="index"
            data-test="config-variable-row"
            :data-fieldname="fieldnameOf(row)"
            :data-locked="row.locked_by ? '1' : '0'"
          >
            <td>
              <input
                v-model="row.label"
                type="text"
                class="form-control input-xs"
                data-test="config-variable-label"
                :placeholder="__('Lot No')"
              />
              <span v-if="row.locked_by" class="config-badge" data-test="config-variable-locked">
                {{ __("from {0}", [sourceLabel(row.locked_by)]) }}
              </span>
            </td>
            <td>
              <code data-test="config-variable-fieldname">{{ fieldnameOf(row) || "—" }}</code>
            </td>
            <td>
              <select
                v-model="row.fieldtype"
                class="form-control input-xs"
                data-test="config-variable-type"
              >
                <option v-for="fieldtype in fieldtypes" :key="fieldtype" :value="fieldtype">{{ fieldtype }}</option>
              </select>
            </td>
            <td>
              <textarea
                v-if="row.fieldtype === 'Select'"
                v-model="row.options"
                rows="2"
                class="form-control input-xs"
                data-test="config-variable-options"
                :placeholder="__('One option per line')"
              ></textarea>
              <span v-else>—</span>
            </td>
            <td>
              <input
                v-model="row.required"
                type="checkbox"
                data-test="config-variable-required"
                :disabled="!!row.locked_by"
              />
            </td>
            <td class="actions">
              <button
                v-if="!row.locked_by"
                type="button"
                class="btn btn-default btn-xs"
                data-test="config-remove-variable"
                @click="removeRow(index)"
              >
                {{ __("Remove") }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <button type="button" class="btn btn-default btn-xs" data-test="config-add-variable" @click="addRow">
        {{ __("Add variable") }}
      </button>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { REQUIRED_FIELD_SOURCE_LABELS, labelFor } from "../labels"
import { variableFieldname } from "../../shared/variable_fieldname.js"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  template: { type: String, required: true },
})
const emit = defineEmits(["close", "saved"])

const title = ref("")
const rows = ref([])
const fieldtypes = ref(["Data"])
const loading = ref(true)
const loadError = ref("")
const saveError = ref("")
const saving = ref(false)

/** The first pair of labels that collapse to one fieldname - the server refuses these,
 * so the builder names them before a save can fail. */
const collision = computed(() => {
  const labels = {}
  for (const row of rows.value) {
    const fieldname = fieldnameOf(row)
    if (!fieldname) continue
    if (labels[fieldname]) {
      return { first: labels[fieldname], second: row.label, fieldname }
    }
    labels[fieldname] = row.label
  }
  return null
})

const hasBlankLabel = computed(() => rows.value.some((row) => !fieldnameOf(row)))

const requiredFieldnames = computed(() =>
  rows.value.filter((row) => row.required).map((row) => fieldnameOf(row))
)

/** What the chart will store this variable under. A row the server already knows keeps its
 * fieldname when it is relabelled - `_validated_variable_rows` reads `fieldname` first, and
 * re-keying an existing variable would orphan every value already recorded under it. */
function fieldnameOf(row) {
  return row.fieldname || variableFieldname(row.label)
}

function sourceLabel(source) {
  return labelFor(REQUIRED_FIELD_SOURCE_LABELS, source)
}

function addRow() {
  rows.value = [...rows.value, { label: "", fieldtype: "Data", options: "", required: false, locked_by: "" }]
}

function removeRow(index) {
  rows.value = rows.value.filter((_row, position) => position !== index)
}

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.get_derma_template_variables",
      args: { template: props.template },
    })
    apply(response.message || {})
  } catch (error) {
    console.warn("[do_derma] Failed to load template variables", error)
    loadError.value = __("Unable to load this template's variables.")
  } finally {
    loading.value = false
  }
}

function apply(payload) {
  title.value = payload.title || ""
  fieldtypes.value = payload.fieldtypes || ["Data"]
  rows.value = (payload.variables || []).map((variable) => ({ ...variable }))
}

async function save() {
  saving.value = true
  saveError.value = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.save_derma_template_variables",
      args: { template: props.template, variables: rows.value },
    })
    apply(response.message || {})
    emit("saved")
  } catch (error) {
    // Frappe renders its own message dialog; this line keeps the reason on the panel.
    saveError.value = error?.message || __("Unable to save these variables.")
  } finally {
    saving.value = false
  }
}

watch(() => props.template, load, { immediate: true })
</script>

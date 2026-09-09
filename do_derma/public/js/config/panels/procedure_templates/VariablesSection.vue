<template>
  <section class="config-detail-section" data-test="config-variables-section">
    <h4>{{ __("Variables") }}</h4>

    <!-- How these are captured, which belongs beside them rather than in Requirements. -->
    <slot />

    <p v-if="collision" class="config-status warning" data-test="config-variable-collision">
      {{ __("{0} and {1} both become the fieldname {2}.", [collision.first, collision.second, collision.fieldname]) }}
    </p>
    <p v-if="hasBlankLabel" class="config-status warning" data-test="config-variable-blank-label">
      {{ __("Every variable needs a label.") }}
    </p>

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
              :disabled="readOnly"
              :placeholder="__('Lot No')"
            />
            <span v-if="row.locked_by" class="config-badge" data-test="config-variable-locked">
              {{ __("from {0}", [sourceLabel(row.locked_by)]) }}
            </span>
          </td>
          <td><code data-test="config-variable-fieldname">{{ fieldnameOf(row) || "—" }}</code></td>
          <td>
            <select
              v-model="row.fieldtype"
              class="form-control input-xs"
              data-test="config-variable-type"
              :disabled="readOnly"
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
              :disabled="readOnly"
              :placeholder="__('One option per line')"
            ></textarea>
            <span v-else>—</span>
          </td>
          <td>
            <input
              v-model="row.required"
              type="checkbox"
              data-test="config-variable-required"
              :disabled="readOnly || !!row.locked_by"
            />
          </td>
          <td class="actions">
            <button
              v-if="!readOnly && !row.locked_by"
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

    <button
      v-if="!readOnly"
      type="button"
      class="btn btn-default btn-xs"
      data-test="config-add-variable"
      @click="addRow"
    >
      {{ __("Add variable") }}
    </button>
  </section>
</template>

<script setup>
import { computed } from "vue"
import { REQUIRED_FIELD_SOURCE_LABELS, labelFor } from "../../labels"
import { variableFieldnameOf, variableIssues } from "./variable_issues.js"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  rows: { type: Array, default: () => [] },
  fieldtypes: { type: Array, default: () => ["Data"] },
  readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(["update:rows"])

const issues = computed(() => variableIssues(props.rows))
const collision = computed(() => issues.value.collision)
const hasBlankLabel = computed(() => issues.value.hasBlankLabel)

function fieldnameOf(row) {
  return variableFieldnameOf(row)
}

function sourceLabel(source) {
  return labelFor(REQUIRED_FIELD_SOURCE_LABELS, source)
}

function addRow() {
  emit("update:rows", [
    ...props.rows,
    { label: "", fieldtype: "Data", options: "", required: false, locked_by: "" },
  ])
}

function removeRow(index) {
  emit("update:rows", props.rows.filter((_row, position) => position !== index))
}
</script>

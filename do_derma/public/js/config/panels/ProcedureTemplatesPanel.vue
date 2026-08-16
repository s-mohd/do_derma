<template>
  <div class="config-section" data-test="config-procedure-templates">
    <header class="config-section-head">
      <h3>{{ __("Procedure Templates") }}</h3>
      <span v-if="needingAttention" class="config-badge warn" data-test="config-template-warning-count">
        {{ __("{0} of {1} need attention", [needingAttention, templates.length]) }}
      </span>
    </header>

    <p v-if="!templates.length" class="config-status" data-test="config-procedure-templates-empty">
      {{ __("No procedure template is configured for derma yet.") }}
    </p>

    <table v-else class="config-table">
      <thead>
        <tr>
          <th>{{ __("Template") }}</th>
          <th>{{ __("Category") }}</th>
          <th class="numeric">{{ __("Variables") }}</th>
          <th>{{ __("Required fields") }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="template in templates"
          :key="template.name"
          data-test="config-procedure-template-row"
          :data-template="template.name"
        >
          <td>
            {{ template.template }}
            <span v-if="template.disabled" class="config-badge" data-test="config-procedure-template-disabled">
              {{ __("Disabled") }}
            </span>
            <div v-if="template.warnings.length" class="config-warnings">
              <span
                v-for="warning in template.warnings"
                :key="warning"
                class="config-badge warn"
                data-test="config-template-warning"
                :data-warning="warning"
              >
                {{ warningLabel(warning) }}
              </span>
            </div>
          </td>
          <td>{{ template.category || "—" }}</td>
          <td class="numeric" data-test="config-variable-count">{{ template.variable_count }}</td>
          <td>
            <span v-if="!template.required_fields.length">—</span>
            <span
              v-for="field in template.required_fields"
              :key="field.fieldname"
              class="config-chip"
              :class="{ unenforced: !field.enforced }"
              data-test="config-required-field"
              :data-source="field.source"
              :data-enforced="field.enforced ? '1' : '0'"
            >
              {{ field.fieldname }}
              <em>{{ sourceLabel(field.source) }}</em>
              <em v-if="!field.enforced">{{ __("not enforced") }}</em>
            </span>
          </td>
          <td class="actions">
            <button
              type="button"
              class="btn btn-default btn-xs"
              data-test="config-edit-procedure-template"
              @click="editTemplate(template)"
            >
              {{ __("Edit") }} →
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { labelFor } from "../labels"

const __ = window.__ || ((txt) => txt)

const WARNING_LABELS = {
  no_required_fields: "Requires nothing",
  category_name_defaults: "Requirements come from the category name",
  unenforced_required_fields: "A required field the chart cannot enforce",
  unreadable_variables: "Variables JSON cannot be read",
}

const SOURCE_LABELS = {
  template: "Template",
  category_name: "Category name",
  product_tracking: "Product tracking",
  device_settings: "Device settings",
  variables_json: "Variables JSON",
}

const props = defineProps({
  templates: { type: Array, default: () => [] },
})

const needingAttention = computed(
  () => props.templates.filter((template) => template.warnings.length).length
)

function warningLabel(warning) {
  return labelFor(WARNING_LABELS, warning)
}

function sourceLabel(source) {
  return labelFor(SOURCE_LABELS, source)
}

function editTemplate(template) {
  frappe.set_route("Form", "Clinical Procedure Template", template.name)
}
</script>

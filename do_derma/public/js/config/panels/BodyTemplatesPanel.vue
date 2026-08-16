<template>
  <div class="config-section" data-test="config-body-templates">
    <header class="config-section-head">
      <h3>{{ __("Body Templates") }}</h3>
      <button type="button" class="btn btn-primary btn-sm" data-test="config-new-body-template" @click="createTemplate">
        {{ __("New template") }}
      </button>
    </header>

    <p v-if="!templates.length" class="config-status" data-test="config-body-templates-empty">
      {{ __("No body templates yet.") }}
    </p>

    <table v-else class="config-table">
      <thead>
        <tr>
          <th>{{ __("Title") }}</th>
          <th>{{ __("Type") }}</th>
          <th>{{ __("Gender") }}</th>
          <th class="numeric">{{ __("Areas") }}</th>
          <th class="numeric">{{ __("Retired") }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="template in templates" :key="template.name" data-test="config-body-template-row" :data-template="template.name">
          <td>
            {{ template.title || template.name }}
            <span v-if="template.disabled" class="config-badge" data-test="config-body-template-disabled">{{ __("Disabled") }}</span>
          </td>
          <td>{{ template.template_type || "—" }}</td>
          <td>{{ template.gender || "—" }}</td>
          <td class="numeric" data-test="config-area-count">{{ template.area_count }}</td>
          <td class="numeric" data-test="config-retired-area-count">{{ template.retired_area_count }}</td>
          <td class="actions">
            <button type="button" class="btn btn-default btn-xs" data-test="config-design-areas" @click="designAreas(template)">
              {{ __("Design areas") }} →
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  templates: { type: Array, default: () => [] },
})

function designAreas(template) {
  // The designer reads its template from window.location.search, and set_route
  // JSON-encodes route options into the query string, so navigate to the URL itself.
  window.location.assign(`/app/derma-body-template-editor?template=${encodeURIComponent(template.name)}`)
}

function createTemplate() {
  frappe.new_doc("Derma Body Template")
}
</script>

<template>
  <div class="config-section" data-test="config-categories">
    <header class="config-section-head">
      <h3>{{ __("Categories") }}</h3>
    </header>

    <p v-if="!categories.length" class="config-status" data-test="config-categories-empty">
      {{ __("No procedure category yet.") }}
    </p>

    <table v-else class="config-table">
      <thead>
        <tr>
          <th>{{ __("Title") }}</th>
          <th>{{ __("Workflow") }}</th>
          <th>{{ __("Marker") }}</th>
          <th>{{ __("Default body template") }}</th>
          <th class="numeric">{{ __("Templates") }}</th>
          <th>{{ __("Read by nothing") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="category in categories"
          :key="category.name"
          data-test="config-category-row"
          :data-category="category.name"
        >
          <td>
            {{ category.title || category.name }}
            <span v-if="category.disabled" class="config-badge" data-test="config-category-disabled">
              {{ __("Disabled") }}
            </span>
          </td>
          <td>{{ category.workflow || "—" }}</td>
          <td>{{ category.marker_behavior || "—" }}</td>
          <td>{{ category.default_body_template || "—" }}</td>
          <td class="numeric" data-test="config-category-template-count">{{ category.template_count }}</td>
          <td>
            <span v-if="!category.unread_fields.length">—</span>
            <span
              v-for="field in category.unread_fields"
              :key="field"
              class="config-badge warn"
              data-test="config-category-unread-field"
              :data-field="field"
            >
              {{ field }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="categories.length" class="config-status" data-test="config-categories-note">
      {{ __("Requirement fields set on a category change nothing — the procedure template owns them.") }}
    </p>
  </div>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  categories: { type: Array, default: () => [] },
})
</script>

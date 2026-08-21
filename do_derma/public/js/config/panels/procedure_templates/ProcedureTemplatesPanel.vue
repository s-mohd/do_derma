<template>
  <div class="config-section" data-test="config-procedure-templates">
    <ProcedureTemplateDetail
      v-if="editing !== null"
      :template="editing"
      :section="jumpSection"
      :categories="categories"
      :body-templates="bodyTemplates"
      @close="close"
      @saved="onSaved"
    />

    <template v-else>
      <header class="config-section-head">
        <h3>{{ __("Procedure Templates") }}</h3>
        <div class="config-head-tools">
          <span v-if="needingAttention" class="config-badge warn" data-test="config-template-warning-count">
            {{ __("{0} of {1} need attention", [needingAttention, templates.length]) }}
          </span>
          <input
            v-model="search"
            type="search"
            class="form-control input-sm config-search"
            data-test="config-template-search"
            :placeholder="__('Search name or category')"
          />
          <label class="config-toggle">
            <input v-model="showRetired" type="checkbox" data-test="config-show-retired" />
            {{ __("Show retired") }}
          </label>
          <button
            v-if="canWrite"
            type="button"
            class="btn btn-primary btn-sm"
            data-test="config-new-procedure-template"
            @click="editing = ''"
          >
            {{ __("New template") }}
          </button>
        </div>
      </header>

      <p v-if="!templates.length" class="config-status" data-test="config-procedure-templates-empty">
        {{ __("No procedure template is configured for derma yet.") }}
      </p>
      <p v-else-if="!visible.length" class="config-status" data-test="config-procedure-templates-no-match">
        {{ __("No procedure template matches this search.") }}
      </p>

      <div v-for="group in groups" :key="group.title" class="config-card-group">
        <div class="config-card-group-head" data-test="config-template-group" :data-group="group.title">
          {{ group.label }} <span>{{ group.templates.length }}</span>
        </div>
        <div class="config-card-grid">
          <article
            v-for="template in group.templates"
            :key="template.name"
            class="config-template-card"
            :class="{ retired: template.disabled }"
            data-test="config-procedure-template-row"
            :data-template="template.name"
            @click="open(template.name)"
          >
            <div class="config-template-card-marker">
              <MarkerPreview
                :behavior="template.effective_marker.behavior"
                :color="template.effective_marker.color"
                :size="58"
              />
              <span class="config-marker-name">
                {{ markerBehaviorLabel(template.effective_marker.behavior) }}
                <em v-if="template.effective_marker.inherited" data-test="config-marker-inherited">
                  {{ __("inherited") }}
                </em>
              </span>
            </div>
            <div class="config-template-card-body">
              <h5>{{ template.template }}</h5>
              <div class="config-template-card-meta">
                <span data-test="config-variable-count">{{ __("{0} variables", [template.variable_count]) }}</span>
                <span v-if="template.disabled" class="config-badge" data-test="config-procedure-template-disabled">
                  {{ __("Retired") }}
                </span>
                <span v-if="template.has_marker_preset" class="config-badge" data-test="config-marker-preset">
                  {{ __("Custom preset") }}
                </span>
              </div>
              <div v-if="template.warnings.length" class="config-warnings">
                <button
                  v-for="warning in template.warnings"
                  :key="warning"
                  type="button"
                  class="config-badge warn config-badge-button"
                  data-test="config-template-warning"
                  :data-warning="warning"
                  @click.stop="open(template.name, WARNING_SECTIONS[warning])"
                >
                  {{ warningLabel(warning) }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"
import MarkerPreview from "./MarkerPreview.vue"
import ProcedureTemplateDetail from "./ProcedureTemplateDetail.vue"
import { labelFor, markerBehaviorLabel } from "../../labels"

const __ = window.__ || ((txt) => txt)

const UNCATEGORISED = "Uncategorised"

const WARNING_LABELS = {
  no_required_fields: "Requires nothing",
  unenforced_required_fields: "A required field the chart cannot enforce",
  unreadable_variables: "Variables JSON cannot be read",
}

/** Which detail section owns each warning, so a badge lands on the setting that caused it. */
const WARNING_SECTIONS = {
  no_required_fields: "requirements",
  unenforced_required_fields: "requirements",
  unreadable_variables: "variables",
}

const props = defineProps({
  templates: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  bodyTemplates: { type: Array, default: () => [] },
  canWrite: { type: Boolean, default: false },
})
const emit = defineEmits(["changed"])

/** "" is a new template, null is the grid. */
const editing = ref(null)
const jumpSection = ref("")
const search = ref("")
const showRetired = ref(false)

const needingAttention = computed(
  () => props.templates.filter((template) => template.warnings.length).length
)

const visible = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return props.templates.filter((template) => {
    if (!showRetired.value && template.disabled) return false
    if (!needle) return true
    return `${template.template} ${template.category}`.toLowerCase().includes(needle)
  })
})

const groups = computed(() => {
  const byCategory = new Map()
  for (const template of visible.value) {
    const title = template.category || UNCATEGORISED
    if (!byCategory.has(title)) byCategory.set(title, [])
    byCategory.get(title).push(template)
  }
  const named = [...byCategory.entries()]
    .filter(([title]) => title !== UNCATEGORISED)
    .sort(([first], [second]) => first.localeCompare(second))
  const loose = byCategory.get(UNCATEGORISED)
  const ordered = loose ? [...named, [UNCATEGORISED, loose]] : named
  return ordered.map(([title, templates]) => ({
    title,
    label: title === UNCATEGORISED ? __("Uncategorised") : title,
    templates,
  }))
})

function warningLabel(warning) {
  return labelFor(WARNING_LABELS, warning)
}

function open(template, section = "") {
  jumpSection.value = section
  editing.value = template
}

function close() {
  editing.value = null
  jumpSection.value = ""
}

function onSaved() {
  emit("changed")
}
</script>

<template>
  <div class="config-detail" data-test="config-template-detail" :data-template="template">
    <header class="config-section-head">
      <h4>{{ isNew ? __("New procedure template") : draft.template || template }}</h4>
      <div class="config-builder-actions">
        <a
          v-if="!isNew"
          class="config-detail-link"
          :href="`/app/clinical-procedure-template/${encodeURIComponent(template)}`"
          data-test="config-open-desk-form"
        >
          {{ __("Open full form") }} ↗
        </a>
        <button type="button" class="btn btn-default btn-xs" data-test="config-close-detail" @click="emit('close')">
          {{ __("Back to templates") }}
        </button>
        <button
          v-if="canWrite"
          type="button"
          class="btn btn-primary btn-xs"
          data-test="config-save-template"
          :disabled="saving || !!issues.collision || issues.hasBlankLabel"
          @click="save"
        >
          {{ saving ? __("Saving…") : __("Save") }}
        </button>
      </div>
    </header>

    <p v-if="loading" class="config-status" data-test="config-detail-loading">{{ __("Loading template…") }}</p>
    <p v-else-if="loadError" class="config-status error" data-test="config-detail-error">{{ loadError }}</p>

    <template v-else>
      <p v-if="!canWrite" class="config-status warning" data-test="config-detail-read-only">
        {{ __("You may read this template but not change it.") }}
      </p>
      <p v-if="saveError" class="config-status error" data-test="config-detail-save-error">{{ saveError }}</p>

      <section class="config-detail-section" id="config-section-identity">
        <h4>{{ __("Identity & billing") }}</h4>
        <div class="config-field-grid">
          <label v-if="isNew">
            {{ __("Template name") }}
            <input v-model="draft.template" type="text" class="form-control input-sm" data-test="config-template-name" />
          </label>
          <label v-else>
            {{ __("Template name") }}
            <div class="config-readonly-value" data-test="config-template-name">{{ draft.template }}</div>
          </label>
          <label>
            {{ __("Item group") }}
            <input
              v-model="draft.item_group"
              type="text"
              class="form-control input-sm"
              list="config-item-groups"
              :disabled="!canWrite"
              data-test="config-item-group"
            />
          </label>
          <label>
            {{ __("Medical department") }}
            <input
              v-model="draft.medical_department"
              type="text"
              class="form-control input-sm"
              list="config-medical-departments"
              :disabled="!canWrite"
              data-test="config-medical-department"
            />
          </label>
          <label>
            {{ __("Rate") }}
            <input v-model.number="draft.rate" type="number" class="form-control input-sm" :disabled="!canWrite" data-test="config-rate" />
          </label>
        </div>
        <label class="config-field-block">
          {{ __("Description") }}
          <textarea v-model="draft.description" rows="2" class="form-control input-sm" :disabled="!canWrite" data-test="config-description"></textarea>
        </label>
        <label class="config-toggle">
          <input v-model="draft.is_billable" type="checkbox" :true-value="1" :false-value="0" :disabled="!canWrite" data-test="config-is-billable" />
          {{ __("Billable") }}
        </label>
        <label class="config-toggle">
          <input v-model="draft.disabled" type="checkbox" :true-value="1" :false-value="0" :disabled="!canWrite" data-test="config-disabled" />
          {{ __("Retired") }}
        </label>
        <datalist id="config-item-groups">
          <option v-for="option in itemGroups" :key="option" :value="option"></option>
        </datalist>
        <datalist id="config-medical-departments">
          <option v-for="option in medicalDepartments" :key="option" :value="option"></option>
        </datalist>
      </section>

      <section class="config-detail-section" id="config-section-behavior">
        <h4>{{ __("Chart behavior") }}</h4>
        <label class="config-field-block">
          {{ __("Category") }}
          <select v-model="draft.category" class="form-control input-sm" :disabled="!canWrite" data-test="config-category">
            <option value="">{{ __("Uncategorised") }}</option>
            <option v-for="category in categories" :key="category.name" :value="category.name">
              {{ category.title || category.name }}
            </option>
          </select>
        </label>

        <div class="config-field-label">{{ __("Marker") }}</div>
        <div class="config-marker-tiles">
          <button
            type="button"
            class="config-marker-tile"
            :class="{ active: !draft.marker_behavior }"
            :disabled="!canWrite"
            data-test="config-marker-inherit"
            @click="draft.marker_behavior = ''"
          >
            <MarkerPreview :behavior="inheritedBehavior" :color="markerColor" :size="38" />
            <span>
              {{ __("Inherit") }}
              <em v-if="inheritedBehavior">{{ markerBehaviorLabel(inheritedBehavior) }}</em>
            </span>
          </button>
          <button
            v-for="behavior in payload.marker_behaviors"
            :key="behavior"
            type="button"
            class="config-marker-tile"
            :class="{ active: draft.marker_behavior === behavior }"
            :disabled="!canWrite"
            data-test="config-marker-tile"
            :data-behavior="behavior"
            @click="draft.marker_behavior = behavior"
          >
            <MarkerPreview :behavior="behavior" :color="markerColor" :size="38" />
            <span>{{ markerBehaviorLabel(behavior) }}</span>
          </button>
        </div>

        <div class="config-field-label">{{ __("Colour") }}</div>
        <div class="config-swatches">
          <button
            v-for="color in MARKER_COLOR_PRESETS"
            :key="color"
            type="button"
            class="config-swatch"
            :class="{ active: draft.marker_color === color }"
            :style="{ background: color }"
            :disabled="!canWrite"
            data-test="config-marker-swatch"
            :data-color="color"
            @click="draft.marker_color = color"
          ></button>
          <input
            v-model="draft.marker_color"
            type="text"
            class="form-control input-sm config-hex"
            placeholder="#0f766e"
            :disabled="!canWrite"
            data-test="config-marker-color"
          />
          <button type="button" class="btn btn-default btn-xs" :disabled="!canWrite" @click="draft.marker_color = ''">
            {{ __("Inherit") }}
          </button>
        </div>

        <div class="config-field-label">{{ __("Size") }}</div>
        <div class="config-marker-size" data-test="config-marker-size" :data-size="markerSize">
          <button
            type="button"
            class="btn btn-default btn-xs"
            data-test="config-marker-size-down"
            :disabled="!canWrite || markerSize <= MARKER_SIZE_MIN"
            :aria-label="__('Smaller mark')"
            @click="setMarkerSize(markerSize - MARKER_SIZE_STEP)"
          >
            −
          </button>
          <input
            type="range"
            :min="MARKER_SIZE_MIN"
            :max="MARKER_SIZE_MAX"
            :step="MARKER_SIZE_STEP"
            :value="markerSize"
            :disabled="!canWrite"
            data-test="config-marker-size-slider"
            :aria-label="__('Mark size')"
            @input="setMarkerSize($event.target.value)"
          />
          <button
            type="button"
            class="btn btn-default btn-xs"
            data-test="config-marker-size-up"
            :disabled="!canWrite || markerSize >= MARKER_SIZE_MAX"
            :aria-label="__('Larger mark')"
            @click="setMarkerSize(markerSize + MARKER_SIZE_STEP)"
          >
            +
          </button>
          <strong>{{ `${markerSize}×` }}</strong>
          <button
            type="button"
            class="btn btn-default btn-xs"
            data-test="config-marker-size-reset"
            :disabled="!canWrite || !draft.marker_size"
            @click="draft.marker_size = 0"
          >
            {{ __("Default") }}
          </button>
          <span class="config-marker-sample" data-test="config-marker-sample">
            <MarkerPreview
              :behavior="effectiveBehavior"
              :color="markerColor"
              :size="60"
              :scale="markerSize"
              :frame="MARKER_SIZE_MAX"
            />
          </span>
        </div>

        <p v-if="payload.has_marker_preset" class="config-status warning" data-test="config-marker-preset-notice">
          {{ __("A marker preset on this template overrides the shape above. It is edited in the full form.") }}
        </p>

        <div class="config-field-label">
          {{ __("Allowed body templates") }} <em>{{ __("none means every map") }}</em>
        </div>
        <div class="config-chips">
          <button
            v-for="body in bodyTemplates"
            :key="body.name"
            type="button"
            class="config-chip-button"
            :class="{ active: draft.allowed_body_templates.includes(body.name) }"
            :disabled="!canWrite"
            data-test="config-body-template-chip"
            :data-body-template="body.name"
            @click="toggleBodyTemplate(body.name)"
          >
            {{ body.title || body.name }}
          </button>
        </div>
      </section>

      <section class="config-detail-section" id="config-section-requirements">
        <h4>{{ __("Requirements") }}</h4>
        <label v-for="flag in SAFETY_FLAGS" :key="flag.key" class="config-toggle">
          <input
            v-model="draft[flag.key]"
            type="checkbox"
            :true-value="1"
            :false-value="0"
            :disabled="!canWrite"
            data-test="config-safety-flag"
            :data-flag="flag.key"
          />
          {{ __(flag.label) }}
        </label>

        <div class="config-field-label">{{ __("What the chart will demand") }}</div>
        <p v-if="!payload.required_fields.length" class="config-status" data-test="config-required-empty">
          {{ __("This template requires nothing.") }}
        </p>
        <div v-else>
          <span
            v-for="field in payload.required_fields"
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
        </div>
      </section>

      <VariablesSection
        id="config-section-variables"
        :rows="draft.variables"
        :fieldtypes="payload.fieldtypes"
        :read-only="!canWrite"
        @update:rows="draft.variables = $event"
      />

      <section class="config-detail-section" id="config-section-note">
        <h4>{{ __("Note sentence") }}</h4>
        <textarea
          v-model="draft.note_template"
          rows="3"
          class="form-control input-sm"
          :disabled="!canWrite"
          data-test="config-note-template"
        ></textarea>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import MarkerPreview from "./MarkerPreview.vue"
import VariablesSection from "./VariablesSection.vue"
import { MARKER_COLOR_PRESETS, SAFETY_FLAGS, blankTemplateDraft, templateDraft } from "./template_draft.js"
import {
  MARKER_SIZE_MAX,
  MARKER_SIZE_MIN,
  MARKER_SIZE_STEP,
  markerSizeOf,
  steppedMarkerSize,
} from "../../../shared/marker_size.js"
import { variableIssues } from "./variable_issues.js"
import { REQUIRED_FIELD_SOURCE_LABELS, labelFor, markerBehaviorLabel } from "../../labels"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  template: { type: String, default: "" },
  section: { type: String, default: "" },
  categories: { type: Array, default: () => [] },
  bodyTemplates: { type: Array, default: () => [] },
})
const emit = defineEmits(["close", "saved"])

const payload = ref({ marker_behaviors: [], fieldtypes: ["Data"], required_fields: [] })
const draft = ref(blankTemplateDraft())
const itemGroups = ref([])
const medicalDepartments = ref([])
const loading = ref(true)
const loadError = ref("")
const saveError = ref("")
const saving = ref(false)

const isNew = computed(() => !props.template)
const canWrite = computed(() => Boolean(payload.value.can_write))
const issues = computed(() => variableIssues(draft.value.variables))
const markerColor = computed(() => draft.value.marker_color || payload.value.effective_marker?.color || "")
const inheritedBehavior = computed(() =>
  categoryOf(draft.value.category)?.marker_behavior || ""
)
const effectiveBehavior = computed(() => draft.value.marker_behavior || inheritedBehavior.value)
// An unset size is stored as 0 so "never set" stays distinct from a deliberate 1.0, and the
// sample still has a multiplier to draw at.
const markerSize = computed(() => markerSizeOf(draft.value.marker_size))

function setMarkerSize(value) {
  draft.value.marker_size = steppedMarkerSize(value)
}

function categoryOf(name) {
  return props.categories.find((category) => category.name === name)
}

function sourceLabel(source) {
  return labelFor(REQUIRED_FIELD_SOURCE_LABELS, source)
}

function toggleBodyTemplate(name) {
  const allowed = draft.value.allowed_body_templates
  draft.value.allowed_body_templates = allowed.includes(name)
    ? allowed.filter((entry) => entry !== name)
    : [...allowed, name]
}

async function loadLinkOptions() {
  const [groups, departments] = await Promise.all([
    frappe.db.get_list("Item Group", { fields: ["name"], limit: 200, order_by: "name asc" }),
    frappe.db.get_list("Medical Department", { fields: ["name"], limit: 200, order_by: "name asc" }),
  ])
  itemGroups.value = groups.map((row) => row.name)
  medicalDepartments.value = departments.map((row) => row.name)
}

async function load() {
  loading.value = true
  loadError.value = ""
  saveError.value = ""
  try {
    loadLinkOptions().catch((error) => console.warn("[do_derma] Link options unavailable", error))
    const response = await frappe.call({
      method: "do_derma.api.get_derma_procedure_template",
      args: { template: props.template },
    })
    apply(response.message || {})
  } catch (error) {
    console.warn("[do_derma] Failed to load the procedure template", error)
    loadError.value = __("Unable to load this procedure template.")
  } finally {
    loading.value = false
    scrollToSection()
  }
}

function apply(message) {
  payload.value = message
  draft.value = templateDraft(message)
}

function scrollToSection() {
  if (!props.section) return
  requestAnimationFrame(() => {
    document.getElementById(`config-section-${props.section}`)?.scrollIntoView({ block: "start" })
  })
}

async function save() {
  saving.value = true
  saveError.value = ""
  try {
    const response = await frappe.call({
      method: "do_derma.api.save_derma_procedure_template",
      args: { template: props.template, values: { ...draft.value, modified: payload.value.modified } },
    })
    apply(response.message || {})
    emit("saved", response.message?.name || props.template)
  } catch (error) {
    // Frappe renders its own message dialog; this line keeps the reason on the panel.
    saveError.value = error?.message || __("Unable to save this procedure template.")
  } finally {
    saving.value = false
  }
}

watch(() => props.template, load, { immediate: true })
</script>

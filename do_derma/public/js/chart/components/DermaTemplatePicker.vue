<template>
  <section class="derma-template-picker">
    <header>
      <div>
        <strong>{{ __("Chart Image") }}</strong>
        <small>{{ helperText }}</small>
      </div>
      <div class="template-header-actions">
        <button type="button" class="ghost small" @click="emit('open-template-library')">
          {{ __("Library") }}
        </button>
        <button type="button" class="ghost small" @click="emit('new-template', { gender: genderFilter, templateType: activeGroup })">
          {{ __("New") }}
        </button>
        <button type="button" class="ghost small" :disabled="!selectedTemplate" @click="emit('edit-template-regions', selectedTemplate)">
          {{ __("Regions") }}
        </button>
        <button type="button" class="ghost small" :disabled="!selectedTemplate" @click="emit('load-template', selectedTemplate)">
          {{ __("Load") }}
        </button>
      </div>
    </header>

    <nav class="template-type-tabs" :aria-label="__('Body template groups')">
      <button
        v-for="gender in visibleGenderFilters"
        :key="`gender-${gender.key}`"
        type="button"
        :class="{ active: genderFilter === gender.key }"
        @click="genderFilter = gender.key"
      >
        {{ gender.label }}
      </button>
    </nav>

    <nav class="template-type-tabs compact" :aria-label="__('Body template anatomy groups')">
      <button
        v-for="group in visibleGroups"
        :key="group"
        type="button"
        :class="{ active: activeGroup === group }"
        @click="activeGroup = group"
      >
        {{ group }}
      </button>
    </nav>

    <div class="template-thumb-grid">
      <button
        v-for="template in activeTemplates"
        :key="template.name"
        type="button"
        class="template-thumb"
        :class="{
          active: template.name === selectedTemplate?.name,
        }"
        @click="selectTemplate(template)"
      >
        <span class="thumb-image">
          <img v-if="template.image" :src="template.image" :alt="template.title || template.name" />
          <span v-else>{{ initials(template) }}</span>
        </span>
        <span class="thumb-copy">
          <strong>{{ template.title || template.name }}</strong>
          <small>{{ template.template_type || __("Template") }} · {{ template.gender || __("Any") }}</small>
          <em v-if="isCategoryDefault(template)">{{ __("Default") }}</em>
          <em v-else-if="template.is_standard">{{ __("Standard") }}</em>
        </span>
      </button>

      <p v-if="!activeTemplates.length" class="template-empty">
        {{ __("No templates configured for this group.") }}
      </p>
    </div>

    <footer class="template-picker-footer">
      <button type="button" class="ghost small" :disabled="!canSetDefault" @click="emit('set-default-template', selectedTemplate)">
        {{ __("Use as Category Default") }}
      </button>
      <small v-if="categoryDefaultTemplate">{{ __("Default: {0}").replace("{0}", categoryDefaultTemplate.title || categoryDefaultTemplate.name) }}</small>
      <small v-else>{{ __("No category default configured.") }}</small>
    </footer>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  templates: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  templateSets: { type: Array, default: () => [] },
  modelValue: { type: Object, default: null },
  selectedProcedure: { type: Object, default: null },
  patientSex: { type: String, default: "" },
})

const emit = defineEmits(["update:modelValue", "load-template", "set-default-template", "open-template-library", "new-template", "edit-template-regions"])

const activeGroup = ref("")

const preferredGender = computed(() => {
  const sex = String(props.patientSex || "").toLowerCase()
  if (sex.startsWith("female")) return "Female"
  if (sex.startsWith("male")) return "Male"
  return "Female"
})

const genderFilter = ref(preferredGender.value)

const visibleGenderFilters = computed(() => [
  { key: "Female", label: __("Female") },
  { key: "Male", label: __("Male") },
])

const genderedTemplates = computed(() => {
  return props.templates.filter((row) => genderMatches(row, genderFilter.value))
})

const groups = computed(() => {
  const values = []
  for (const template of genderedTemplates.value) {
    const group = template.template_type || __("Custom")
    if (!values.includes(group)) values.push(group)
  }
  return values
})

const suggestedTemplates = computed(() => {
  const allowed = parseAllowedTemplates(props.selectedProcedure?.custom_derma_allowed_body_templates)
  const category = String(props.selectedProcedure?.custom_derma_category || "").toLowerCase()
  const setTemplates = selectedTemplateSetTemplates.value
  const source = genderedTemplates.value
  if (setTemplates.length) {
    return orderTemplates(source.filter((row) => setTemplates.includes(row.name) || setTemplates.includes(row.title)))
  }
  if (allowed.length) {
    return orderTemplates(source.filter((row) => allowed.includes(row.name) || allowed.includes(row.title)))
  }
  if (["botox", "filler", "laser", "acne", "scar", "pigmentation"].includes(category)) {
    return orderTemplates(source.filter((row) => row.template_type === "Face"))
  }
  if (["lesion", "biopsy"].includes(category)) {
    return orderTemplates(source.filter((row) => ["Body", "Face"].includes(row.template_type)))
  }
  return orderTemplates(source.slice(0, 4))
})

const visibleGroups = computed(() => {
  return groups.value
})

const activeTemplates = computed(() => {
  return orderTemplates(genderedTemplates.value.filter((row) => (row.template_type || __("Custom")) === activeGroup.value))
})

const selectedTemplate = computed(() => props.modelValue)
const selectedCategory = computed(() => props.selectedProcedure?.custom_derma_category || "")
const categorySettings = computed(() => {
  const category = selectedCategory.value
  return props.categories.find((row) => row.name === category || row.title === category) || props.selectedProcedure?.derma_category_defaults || {}
})
const categoryDefaultTemplate = computed(() => {
  const name = categorySettings.value?.default_body_template
  if (!name) return null
  return props.templates.find((row) => row.name === name || row.title === name) || null
})
const canSetDefault = computed(() => Boolean(selectedCategory.value && selectedTemplate.value?.name))

const selectedTemplateSetTemplates = computed(() => {
  const category = selectedCategory.value
  const gender = genderFilter.value
  const row = props.templateSets.find((set) => {
    const categories = set.procedure_category_list || parseAllowedTemplates(set.procedure_categories)
    return set.gender === gender && (!categories.length || categories.includes(category))
  })
  return row?.body_template_list || parseAllowedTemplates(row?.body_templates)
})

const helperText = computed(() => {
  return __("Choose a template to load it into the drawing surface.")
})

watch(
  () => props.templates,
  () => ensureActiveGroup(),
  { immediate: true, deep: true }
)

watch(
  () => props.selectedProcedure?.name,
  () => {
    const suggested = suggestedTemplates.value[0]
    activeGroup.value = suggested?.template_type || groups.value[0] || ""
    if (suggested) emit("update:modelValue", suggested)
  }
)

watch(
  () => props.patientSex,
  () => {
    genderFilter.value = preferredGender.value
    ensureActiveGroup()
  }
)

watch(
  () => genderFilter.value,
  () => ensureActiveGroup()
)

function ensureActiveGroup() {
  if (activeGroup.value && visibleGroups.value.includes(activeGroup.value)) return
  activeGroup.value = groups.value[0] || ""
}

function selectTemplate(template) {
  emit("update:modelValue", template)
  emit("load-template", template)
}

function isCategoryDefault(template) {
  const category = selectedCategory.value
  if (!category) return false
  return categoryDefaultTemplate.value?.name === template.name || (template.default_for_categories || []).includes(category)
}

function orderTemplates(rows) {
  const defaultName = categoryDefaultTemplate.value?.name
  const setOrder = selectedTemplateSetTemplates.value
  return [...rows].sort((a, b) => {
    if (a.name === defaultName) return -1
    if (b.name === defaultName) return 1
    const ai = setOrder.findIndex((value) => value === a.name || value === a.title)
    const bi = setOrder.findIndex((value) => value === b.name || value === b.title)
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
    return Number(a.sequence || 0) - Number(b.sequence || 0) || String(a.title || a.name).localeCompare(String(b.title || b.name))
  })
}

function parseAllowedTemplates(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function initials(template) {
  return String(template?.title || template?.name || "?").slice(0, 2)
}

function genderMatches(template, gender) {
  return (template.gender || "") === gender
}
</script>

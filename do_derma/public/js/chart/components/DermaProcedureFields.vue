<template>
  <section class="derma-procedure-fields">
    <header>
      <div>
        <strong>{{ __("Procedure Details") }}</strong>
        <small>{{ helperText }}</small>
      </div>
    </header>

    <div v-if="!fields.length" class="procedure-field-empty">
      {{ __("No required fields configured for this procedure.") }}
    </div>

    <div v-else class="procedure-field-grid">
      <label
        v-for="field in fields"
        :key="field.fieldname"
        :class="{ wide: isWide(field), missing: isMissing(field) }"
      >
        <span>
          {{ field.label || field.fieldname }}
          <em v-if="field.required">*</em>
        </span>
        <select
          v-if="field.fieldtype === 'Select'"
          :value="valueFor(field)"
          @change="setValue(field, $event.target.value)"
        >
          <option value=""></option>
          <option v-for="option in optionsFor(field)" :key="option" :value="option">{{ option }}</option>
        </select>
        <textarea
          v-else-if="field.fieldtype === 'Small Text'"
          rows="2"
          :value="valueFor(field)"
          @input="setValue(field, $event.target.value)"
        ></textarea>
        <input
          v-else
          :type="inputType(field)"
          :checked="field.fieldtype === 'Check' ? Boolean(valueFor(field)) : undefined"
          :value="field.fieldtype === 'Check' ? undefined : valueFor(field)"
          @input="setInputValue(field, $event)"
          @change="field.fieldtype === 'Check' ? setValue(field, $event.target.checked) : null"
        />
      </label>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  selectedProcedure: { type: Object, default: null },
  missingFields: { type: Array, default: () => [] },
})

const emit = defineEmits(["update:modelValue"])

const helperText = computed(() => {
  const source = props.fields.find((field) => field.source_treatment)?.source_treatment
  if (source) return __("Using variables from {0}").replace("{0}", source)
  return props.selectedProcedure ? __("Configured by selected procedure") : __("Select a procedure to show requirements")
})

function valueFor(field) {
  return props.modelValue?.[field.fieldname] ?? ""
}

function setInputValue(field, event) {
  if (field.fieldtype === "Check") return
  setValue(field, event.target.value)
}

function setValue(field, value) {
  emit("update:modelValue", {
    ...(props.modelValue || {}),
    [field.fieldname]: value,
  })
}

function optionsFor(field) {
  if (Array.isArray(field.options)) return field.options
  return String(field.options || "")
    .split("\n")
    .map((row) => row.trim())
    .filter(Boolean)
}

function inputType(field) {
  if (field.fieldtype === "Date") return "date"
  if (["Float", "Int"].includes(field.fieldtype)) return "number"
  if (field.fieldtype === "Check") return "checkbox"
  return "text"
}

function isWide(field) {
  return field.fieldtype === "Small Text" || String(field.label || "").length > 18
}

function isMissing(field) {
  return props.missingFields.includes(field.fieldname)
}
</script>

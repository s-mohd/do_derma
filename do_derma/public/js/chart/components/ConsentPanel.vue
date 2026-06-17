<template>
  <section class="workspace-panel consent-panel">
    <header class="panel-header">
      <div class="actions">
        <button type="button" class="ghost" :disabled="loading || saving" @click="$emit('refresh')">{{ __("Refresh") }}</button>
        <button
          type="button"
          class="primary"
          :disabled="loading || saving || !canCreate"
          @click="emitCreate"
        >
          {{ saving ? __("Creating...") : __("Create") }}
        </button>
      </div>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="loading" class="empty-state">{{ __("Loading consents...") }}</div>
    <div v-else-if="!hasSessionContext" class="empty-state">
      {{ __("Consents are visit-scoped. Select or start an appointment session first.") }}
    </div>
    <div v-else>
      <div class="consent-grid">
        <div class="compose-column">
          <div class="field-host" :ref="(el) => bindHost('consent_form_template', el)"></div>
          <div class="field-host" :ref="(el) => bindHost('procedure_selection', el)"></div>
          <div class="field-host" :ref="(el) => bindHost('signed_by', el)"></div>
          <div class="field-host" :ref="(el) => bindHost('relationship', el)"></div>
          <div class="field-host" :ref="(el) => bindHost('signature', el)"></div>
        </div>

        <div class="preview-column">
          <h4>{{ __("Preview") }}</h4>
          <div class="preview-box" v-if="previewLoading">{{ __("Rendering preview...") }}</div>
          <div
            v-else
            class="preview-box"
            v-html="previewMarkup"
          ></div>

          <h4>{{ __("Existing Consents") }}</h4>
          <div v-if="consents.length" class="consent-list">
            <button
              v-for="row in consents"
              :key="row.name"
              type="button"
              class="consent-row"
              @click="$emit('open-consent', row)"
            >
              <span class="name">{{ row.consent_form_template || row.name }}</span>
              <span class="meta">{{ consentMeta(row) }}</span>
            </button>
          </div>
          <div v-else class="preview-box text-muted">{{ __("No consents yet.") }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  encounterName: { type: String, default: "" },
  consents: { type: Array, default: () => [] },
  procedureOptions: { type: Array, default: () => [] },
  previewHtml: { type: String, default: "" },
  previewLoading: { type: Boolean, default: false },
  defaultSignedBy: { type: String, default: "" },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["refresh", "request-preview", "create", "open-consent"])

const hosts = new Map()
const controls = new Map()
let renderQueued = false
let previewTimer = null
let renderingControls = false
let lastPreviewKey = ""
const localValues = ref({
  consent_form_template: "",
  procedure_selection: [],
  signed_by: "",
  relationship: "",
  signature: "",
})

const canCreate = computed(() => props.hasSessionContext && !props.readOnly)
const previewMarkup = computed(
  () => props.previewHtml || `<div class="text-muted">${__("Select a consent template.")}</div>`
)

watch(
  () => props.hasSessionContext,
  () => scheduleRender(),
  { immediate: true }
)

watch(
  () => props.procedureOptions,
  () => {
    syncProcedureOptions()
  },
  { deep: true }
)

watch(
  () => props.defaultSignedBy,
  (value) => {
    const next = value || ""
    if (!next) return
    if (localValues.value.signed_by) return
    localValues.value.signed_by = next
    const control = controls.get("signed_by")
    control?.set_value?.(next)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  clearTimeout(previewTimer)
  teardownAllControls()
})

function bindHost(key, el) {
  if (el) {
    hosts.set(key, el)
    scheduleRender()
    return
  }
  hosts.delete(key)
  teardownControl(key)
}

function scheduleRender() {
  if (renderQueued) return
  renderQueued = true
  Promise.resolve().then(async () => {
    renderQueued = false
    await renderControls()
  })
}

function teardownControl(key) {
  const control = controls.get(key)
  if (!control) return
  try {
    control.$wrapper?.remove()
  } catch (e) {
    /* no-op */
  }
  controls.delete(key)
}

function teardownAllControls() {
  for (const key of controls.keys()) {
    teardownControl(key)
  }
}

function controlDef(fieldname) {
  const readOnly = props.readOnly ? 1 : 0
  if (fieldname === "consent_form_template") {
    return {
      fieldname,
      fieldtype: "Link",
      options: "Consent Form Template",
      label: __("Consent Template"),
      reqd: 1,
      read_only: readOnly,
      onchange: handleFieldChange,
    }
  }

  if (fieldname === "procedure_selection") {
    return {
      fieldname,
      fieldtype: "MultiSelectList",
      label: __("Procedures"),
      reqd: 1,
      read_only: readOnly,
      get_data: () => props.procedureOptions || [],
      onchange: handleFieldChange,
    }
  }

  if (fieldname === "signed_by") {
    return {
      fieldname,
      fieldtype: "Data",
      label: __("Signed By"),
      reqd: 1,
      read_only: readOnly,
      onchange: handleFieldChange,
    }
  }

  if (fieldname === "relationship") {
    return {
      fieldname,
      fieldtype: "Data",
      label: __("Relationship to Patient"),
      read_only: readOnly,
      onchange: handleFieldChange,
    }
  }

  if (fieldname === "signature") {
    return {
      fieldname,
      fieldtype: "Signature",
      label: __("Signature"),
      read_only: readOnly,
      onchange: handleFieldChange,
    }
  }

  return null
}

async function renderControls() {
  if (!props.hasSessionContext) {
    teardownAllControls()
    return
  }

  await nextTick()
  renderingControls = true

  try {
    for (const fieldname of ["consent_form_template", "procedure_selection", "signed_by", "relationship", "signature"]) {
      const host = hosts.get(fieldname)
      if (!host) continue

      teardownControl(fieldname)
      host.innerHTML = ""

      const df = controlDef(fieldname)
      if (!df) continue

      const control = frappe.ui.form.make_control({
        parent: host,
        render_input: true,
        only_input: false,
        doc: { doctype: "Encounter Consent" },
        df,
      })

      controls.set(fieldname, control)

      const value = localValues.value[fieldname]
      if (value !== undefined && value !== null && value !== "") {
        control.set_value?.(value)
      } else if (fieldname === "signed_by" && props.defaultSignedBy) {
        control.set_value?.(props.defaultSignedBy)
        localValues.value.signed_by = props.defaultSignedBy
      }
    }

    syncProcedureOptions()
  } finally {
    renderingControls = false
  }
}

function syncProcedureOptions() {
  const field = controls.get("procedure_selection")
  if (!field) return
  const options = props.procedureOptions || []
  const values = field.get_value ? field.get_value() : localValues.value.procedure_selection || []
  field._options = options
  field._selected_values = field._options.filter((opt) => values.includes(opt.value))
  if (field.set_selectable_items) {
    field.set_selectable_items(field._options)
  }
}

function readValues() {
  const consentTemplate = controls.get("consent_form_template")?.get_value?.() || ""
  const selection = controls.get("procedure_selection")?.get_value?.() || []
  const signedBy = controls.get("signed_by")?.get_value?.() || ""
  const relationship = controls.get("relationship")?.get_value?.() || ""
  const signature = controls.get("signature")?.get_value?.() || ""

  localValues.value = {
    consent_form_template: consentTemplate,
    procedure_selection: Array.isArray(selection) ? selection : [],
    signed_by: signedBy,
    relationship,
    signature,
  }

  return { ...localValues.value }
}

function handleFieldChange() {
  if (renderingControls) return
  readValues()
  clearTimeout(previewTimer)
  previewTimer = setTimeout(() => {
    const values = readValues()
    const previewKey = JSON.stringify({
      consent_form_template: values.consent_form_template || "",
      procedure_selection: values.procedure_selection || [],
    })
    if (!values.consent_form_template || previewKey === lastPreviewKey) return
    lastPreviewKey = previewKey
    emit("request-preview", {
      consent_form_template: values.consent_form_template,
      procedure_selection: values.procedure_selection,
    })
  }, 160)
}

function emitCreate() {
  if (!canCreate.value || props.loading || props.saving) return
  const values = readValues()
  if (!values.consent_form_template) {
    frappe.show_alert({ message: __("Consent template is required."), indicator: "orange" })
    return
  }
  if (!values.procedure_selection.length) {
    frappe.show_alert({ message: __("Select at least one procedure."), indicator: "orange" })
    return
  }
  if (!values.signed_by) {
    frappe.show_alert({ message: __("Signed By is required."), indicator: "orange" })
    return
  }

  emit("create", values)
}

function consentMeta(row) {
  const parts = [row.status, row.signed_by, row.signed_on].filter(Boolean)
  return parts.join(" · ") || "—"
}
</script>

<style scoped>
.workspace-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}

.panel-header {
  display: flex;
  justify-content: end;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.panel-header .meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.actions {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

button {
  border-radius: 8px;
  border: 1px solid #d1d5db;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

button.ghost {
  background: #f8fafc;
  color: #334155;
}

button.primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-text {
  color: #b91c1c;
  font-size: 12px;
  margin: 0 0 8px;
}

.empty-state {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 12px;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
}

.consent-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.compose-column,
.preview-column {
  min-width: 0;
}

.field-host:deep(.frappe-control) {
  margin-bottom: 10px;
}

.preview-column h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.preview-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  min-height: 90px;
  background: #f8fafc;
  margin-bottom: 10px;
}

.preview-box.text-muted {
  color: #64748b;
}

.consent-list {
  display: grid;
  gap: 8px;
}

.consent-row {
  display: grid;
  gap: 2px;
  text-align: left;
  width: 100%;
  background: #fff;
}

.consent-row .name {
  font-weight: 600;
  color: #0f172a;
}

.consent-row .meta {
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 1024px) {
  .consent-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

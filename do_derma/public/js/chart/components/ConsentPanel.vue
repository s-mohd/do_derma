<template>
  <section class="workspace-panel consent-panel" data-test="consent-panel">
    <header class="panel-header">
      <div class="actions">
        <button
          type="button"
          class="ghost"
          :disabled="loading || saving || sending || !canCreate"
          @click="emitSend"
        >
          {{ sending ? __("Sending...") : __("Send via WhatsApp") }}
        </button>
        <button
          type="button"
          class="primary"
          data-test="consent-create"
          :disabled="loading || saving || sending || !canCreate"
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
      <div class="consent-workspace">
        <div class="setup-row">
          <div class="field-host" data-test="consent-template-host" :ref="(el) => bindHost('consent_form_template', el)"></div>
          <div class="field-host" :ref="(el) => bindHost('procedure_selection', el)"></div>
        </div>

        <div class="document-grid">
          <div class="preview-column">
            <h4>{{ __("Consent Form") }}</h4>
            <div class="preview-box" v-if="previewLoading">{{ __("Rendering preview...") }}</div>
            <div
              v-else
              ref="previewBoxRef"
              class="preview-box"
              data-test="consent-preview"
              :class="{ editable: hasEditableFields }"
              v-html="previewMarkup"
            ></div>
          </div>

          <div class="history-column">
            <h4>{{ __("Existing Consents") }}</h4>
            <div v-if="consents.length" class="consent-list">
              <div v-for="row in consents" :key="row.name" class="consent-row" data-test="consent-row">
                <button type="button" class="consent-row-main" @click="$emit('open-consent', row)">
                  <span class="name">{{ row.consent_form_template || row.name }}</span>
                  <span class="meta">{{ consentMeta(row) }}</span>
                </button>
                <div v-if="canManageRemote(row)" class="consent-row-actions">
                  <button type="button" class="ghost" :disabled="sending" @click="$emit('resend-consent', row)">{{ __("Resend") }}</button>
                  <button type="button" class="ghost danger" :disabled="sending" @click="$emit('cancel-consent', row)">{{ __("Cancel") }}</button>
                </div>
              </div>
            </div>
            <div v-else class="preview-box text-muted">{{ __("No consents yet.") }}</div>
          </div>
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
  sending: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  encounterName: { type: String, default: "" },
  consents: { type: Array, default: () => [] },
  procedureOptions: { type: Array, default: () => [] },
  previewHtml: { type: String, default: "" },
  previewLoading: { type: Boolean, default: false },
  defaultSignedBy: { type: String, default: "" },
  resetKey: { type: Number, default: 0 },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["request-preview", "create", "send-whatsapp", "open-consent", "resend-consent", "cancel-consent"])

const hosts = new Map()
const controls = new Map()
const hostTeardownTimers = new Map()
let renderQueued = false
let previewTimer = null
let signaturePadCleanup = null
const previewBoxRef = ref(null)
const hasEditableFields = ref(false)
const formFieldValues = ref({})
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
  () => props.readOnly,
  () => syncControlReadOnly()
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
  },
  { immediate: true }
)

watch(
  () => props.resetKey,
  () => resetDraft()
)

watch(
  () => [props.previewHtml, props.previewLoading, props.readOnly],
  () => {
    nextTick(() => initializeEditablePreview())
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  clearTimeout(previewTimer)
  teardownSignaturePad()
  clearHostTeardownTimers()
  teardownAllControls()
})

function bindHost(key, el) {
  if (el) {
    clearHostTeardownTimer(key)
    if (hosts.get(key) === el) return
    hosts.set(key, el)
    scheduleRender()
    return
  }
  if (!hosts.has(key)) return
  clearHostTeardownTimer(key)
  hostTeardownTimers.set(
    key,
    setTimeout(() => {
      hostTeardownTimers.delete(key)
      hosts.delete(key)
      teardownControl(key)
    }, 0)
  )
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
  clearHostTeardownTimers()
  for (const key of controls.keys()) {
    teardownControl(key)
  }
}

function clearHostTeardownTimer(key) {
  const timer = hostTeardownTimers.get(key)
  if (!timer) return
  clearTimeout(timer)
  hostTeardownTimers.delete(key)
}

function clearHostTeardownTimers() {
  for (const timer of hostTeardownTimers.values()) {
    clearTimeout(timer)
  }
  hostTeardownTimers.clear()
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
      read_only: readOnly,
      get_data: () => props.procedureOptions || [],
      onchange: handleProcedureChange,
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

  for (const fieldname of ["consent_form_template", "procedure_selection"]) {
    const host = hosts.get(fieldname)
    if (!host) continue

    const existing = controls.get(fieldname)
    if (existing && existing.__consentPanelHost === host) {
      continue
    }

    if (existing) teardownControl(fieldname)
    host.innerHTML = ""

    const df = controlDef(fieldname)
    if (!df) continue

    const control = frappe.ui.form.make_control({
      parent: host,
      render_input: true,
      only_input: false,
      doc: { doctype: "Consent Form" },
      df,
    })

    control.__consentPanelHost = host
    controls.set(fieldname, control)

    if (fieldname === "procedure_selection") {
      bindProcedureChangeEvents(control)
    }

    const value = localValues.value[fieldname]
    if (value !== undefined && value !== null && value !== "") {
      control.set_value?.(value)
    }
  }

  syncProcedureOptions()
}

function syncControlReadOnly(fieldname = null) {
  const entries = fieldname ? [[fieldname, controls.get(fieldname)]] : Array.from(controls.entries())
  for (const [, control] of entries) {
    if (!control) continue
    const readOnly = props.readOnly ? 1 : 0
    if (control.df) control.df.read_only = readOnly
    control.refresh?.()
    control.$input?.prop?.("disabled", Boolean(readOnly))
  }
}

function normalizeSelection(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (!value) return []
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return parsed.filter(Boolean)
    } catch (e) {
      /* fall through */
    }
    return value
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean)
  }
  return []
}

function syncProcedureOptions() {
  const field = controls.get("procedure_selection")
  if (!field) return
  const options = props.procedureOptions || []
  const values = normalizeSelection(field.get_value ? field.get_value() : localValues.value.procedure_selection)
  field._options = options
  field._selected_values = field._options.filter((opt) => values.includes(opt.value))
  if (field.set_selectable_items) {
    field.set_selectable_items(field._options)
  }
}

function resetDraft() {
  clearTimeout(previewTimer)
  teardownSignaturePad()
  formFieldValues.value = {}
  localValues.value = {
    consent_form_template: "",
    procedure_selection: [],
    signed_by: props.defaultSignedBy || "",
    relationship: "",
    signature: "",
  }
  controls.get("consent_form_template")?.set_value?.("")
  const procedureControl = controls.get("procedure_selection")
  if (procedureControl) {
    procedureControl._selected_values = []
    procedureControl.set_value?.([])
    procedureControl.refresh?.()
  }
  nextTick(() => initializeEditablePreview())
}

function readValues() {
  const consentTemplate = controls.get("consent_form_template")?.get_value?.() || ""
  const selection = normalizeSelection(controls.get("procedure_selection")?.get_value?.())
  const inlineValues = formFieldValues.value || {}
  const signedBy = inlineValues.signed_by || inlineValues.patient_name || props.defaultSignedBy || ""
  const relationship = inlineValues.relationship || ""
  const signature = inlineValues.signature || ""

  localValues.value = {
    consent_form_template: consentTemplate,
    procedure_selection: selection,
    signed_by: signedBy,
    relationship,
    signature,
  }

  return { ...localValues.value }
}

function handleFieldChange() {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(() => {
    const values = readValues()
    emit("request-preview", {
      consent_form_template: values.consent_form_template,
      procedure_selection: values.procedure_selection,
    })
  }, 160)
}

function handleProcedureChange() {
  // Procedure placeholders come from the selected procedure rows. Discard the
  // previous rendered value so the refreshed server preview can replace it.
  const nextValues = { ...(formFieldValues.value || {}) }
  delete nextValues.procedure
  delete nextValues.procedures
  formFieldValues.value = nextValues
  handleFieldChange()
}

function bindProcedureChangeEvents(control) {
  const wrapper = control?.$list_wrapper
  if (!wrapper?.on) return

  // Frappe's MultiSelectList writes an empty model value for each toggle, so
  // its normal onchange callback stops firing after the first selection.
  // Listen to its actual selection actions to keep the preview synchronized.
  wrapper.on(
    "click.consentPreview",
    ".selectable-item, .clear-selections, .select-all-options",
    () => setTimeout(handleProcedureChange, 0)
  )
  wrapper.on("keydown.consentPreview", "input", (event) => {
    if (event.key === "Enter") setTimeout(handleProcedureChange, 0)
  })
}

function emitCreate() {
  if (!canCreate.value || props.loading || props.saving) return
  const values = readValues()
  if (!values.consent_form_template) {
    frappe.show_alert({ message: __("Consent template is required."), indicator: "orange" })
    return
  }
  if (!values.signed_by) {
    frappe.show_alert({ message: __("Patient name is required on the consent form."), indicator: "orange" })
    return
  }
  if (!values.signature) {
    frappe.show_alert({ message: __("Signature is required on the consent form."), indicator: "orange" })
    return
  }

  emit("create", { ...values, rendered_html: collectRenderedHtml() })
}

function emitSend() {
  if (!canCreate.value || props.loading || props.saving || props.sending) return
  const values = readValues()
  if (!values.consent_form_template) {
    frappe.show_alert({ message: __("Consent template is required."), indicator: "orange" })
    return
  }
  emit("send-whatsapp", { ...values, rendered_html: collectRenderedHtml() })
}

function initializeEditablePreview() {
  teardownSignaturePad()
  const host = previewBoxRef.value
  if (!host || props.previewLoading) {
    hasEditableFields.value = false
    return
  }

  const fields = Array.from(host.querySelectorAll("[data-consent-field]"))
  hasEditableFields.value = fields.length > 0

  for (const field of fields) {
    const name = getFieldName(field)
    if (!name) continue
    if (name === "signature") {
      setupInlineSignature(field)
      continue
    }
    const storageName = canonicalFieldName(name)

    if (formFieldValues.value[storageName] && field.textContent !== formFieldValues.value[storageName]) {
      field.textContent = formFieldValues.value[storageName]
    } else if (!formFieldValues.value[storageName]) {
      const initialValue = field.textContent.trim()
      if (initialValue) {
        formFieldValues.value = {
          ...formFieldValues.value,
          [storageName]: initialValue,
        }
      }
    }
    field.classList.add("consent-inline-field")
    field.setAttribute("role", "textbox")
    field.setAttribute("tabindex", props.readOnly ? "-1" : "0")
    field.setAttribute("spellcheck", "false")
    field.toggleAttribute("contenteditable", !props.readOnly)
    field.oninput = () => {
      const value = field.textContent.trim()
      formFieldValues.value = {
        ...formFieldValues.value,
        [storageName]: value,
      }
      syncMatchingInlineFields(storageName, value, field)
    }
  }
}

function getFieldName(element) {
  return String(element?.dataset?.consentField || "").trim()
}

function canonicalFieldName(fieldname) {
  return String(fieldname || "").replace(/_ar$/, "")
}

function syncMatchingInlineFields(fieldname, value, sourceElement) {
  const host = previewBoxRef.value
  if (!host) return
  for (const field of host.querySelectorAll("[data-consent-field]")) {
    if (field === sourceElement) continue
    if (canonicalFieldName(getFieldName(field)) !== fieldname) continue
    field.textContent = value
  }
}

function setupInlineSignature(container) {
  container.classList.add("consent-inline-field", "consent-inline-signature")
  container.innerHTML = ""

  if (props.readOnly) {
    if (formFieldValues.value.signature) {
      const img = document.createElement("img")
      img.src = formFieldValues.value.signature
      img.alt = __("Signature")
      container.appendChild(img)
    }
    return
  }

  const canvas = document.createElement("canvas")
  const clearButton = document.createElement("button")
  clearButton.type = "button"
  clearButton.className = "signature-clear"
  clearButton.textContent = __("Clear")
  container.appendChild(canvas)
  container.appendChild(clearButton)

  const ctx = canvas.getContext("2d")
  let drawing = false
  let hasStroke = false

  const resizeCanvas = () => {
    const rect = container.getBoundingClientRect()
    const width = Math.max(Math.round(rect.width || 220), 180)
    const height = Math.max(Math.round(rect.height || 72), 64)
    const ratio = window.devicePixelRatio || 1
    canvas.width = width * ratio
    canvas.height = height * ratio
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    ctx.lineWidth = 2
    ctx.strokeStyle = "#111827"
    if (formFieldValues.value.signature) {
      drawSignatureImage(ctx, canvas, formFieldValues.value.signature)
    }
  }

  const pointFromEvent = (event) => {
    const rect = canvas.getBoundingClientRect()
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
  }

  const persistSignature = () => {
    const signature = hasStroke || formFieldValues.value.signature ? canvas.toDataURL("image/png") : ""
    formFieldValues.value = { ...formFieldValues.value, signature }
    localValues.value.signature = signature
  }

  const begin = (event) => {
    event.preventDefault()
    drawing = true
    hasStroke = true
    const point = pointFromEvent(event)
    ctx.beginPath()
    ctx.moveTo(point.x, point.y)
    canvas.setPointerCapture?.(event.pointerId)
  }

  const move = (event) => {
    if (!drawing) return
    event.preventDefault()
    const point = pointFromEvent(event)
    ctx.lineTo(point.x, point.y)
    ctx.stroke()
  }

  const end = (event) => {
    if (!drawing) return
    drawing = false
    canvas.releasePointerCapture?.(event.pointerId)
    persistSignature()
  }

  const clear = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    hasStroke = false
    formFieldValues.value = { ...formFieldValues.value, signature: "" }
    localValues.value.signature = ""
  }

  resizeCanvas()
  canvas.addEventListener("pointerdown", begin)
  canvas.addEventListener("pointermove", move)
  canvas.addEventListener("pointerup", end)
  canvas.addEventListener("pointercancel", end)
  clearButton.addEventListener("click", clear)

  signaturePadCleanup = () => {
    canvas.removeEventListener("pointerdown", begin)
    canvas.removeEventListener("pointermove", move)
    canvas.removeEventListener("pointerup", end)
    canvas.removeEventListener("pointercancel", end)
    clearButton.removeEventListener("click", clear)
  }
}

function drawSignatureImage(ctx, canvas, source) {
  const img = new Image()
  img.onload = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const width = Number.parseFloat(canvas.style.width) || canvas.width
    const height = Number.parseFloat(canvas.style.height) || canvas.height
    ctx.drawImage(img, 0, 0, width, height)
  }
  img.src = source
}

function teardownSignaturePad() {
  if (signaturePadCleanup) {
    signaturePadCleanup()
    signaturePadCleanup = null
  }
}

function collectRenderedHtml() {
  const host = previewBoxRef.value
  if (!host) return props.previewHtml || ""

  const clone = host.cloneNode(true)
  for (const field of clone.querySelectorAll("[data-consent-field]")) {
    field.removeAttribute("contenteditable")
    field.removeAttribute("role")
    field.removeAttribute("tabindex")
    field.removeAttribute("spellcheck")
    const name = getFieldName(field)
    if (name === "signature" && formFieldValues.value.signature) {
      field.innerHTML = `<img src="${formFieldValues.value.signature}" alt="${__("Signature")}">`
    }
  }
  for (const button of clone.querySelectorAll(".signature-clear")) {
    button.remove()
  }
  for (const canvas of clone.querySelectorAll("canvas")) {
    canvas.remove()
  }
  return clone.innerHTML
}

function consentMeta(row) {
  const request = row.remote_request || {}
  const parts = [row.status, row.signed_by, row.signed_on, request.expires_on ? `${__("Expires")} ${request.expires_on}` : ""].filter(Boolean)
  return parts.join(" · ") || "—"
}

function canManageRemote(row) {
  return row?.docstatus === 0 && ["Pending Signature", "Expired", "Delivery Failed"].includes(row?.status)
}
</script>

<style scoped>
.workspace-panel {
  border: 1px solid #d9e2ef;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
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
  border-radius: 6px;
  border: 1px solid #d1d5db;
  min-height: 30px;
  padding: 6px 11px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

button.ghost {
  background: #ffffff;
  color: #334155;
}

button.primary {
  border-color: #0f766e;
  background: #0f766e;
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
  border-radius: 8px;
  padding: 12px;
  color: #475569;
  font-size: 13px;
  background: #f8fafc;
}

.consent-workspace,
.preview-column,
.history-column {
  min-width: 0;
}

.setup-row {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(260px, 1.3fr);
  gap: 12px;
  align-items: end;
  padding: 10px 12px 2px;
  margin-bottom: 12px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.document-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 280px);
  gap: 14px;
  align-items: start;
}

.history-column {
  position: sticky;
  top: 12px;
}

.field-host:deep(.frappe-control) {
  margin-bottom: 10px;
}

.field-host:deep(.control-label) {
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.field-host:deep(.form-control),
.field-host:deep(.input-with-feedback) {
  border-color: #cfd8e3;
  border-radius: 7px;
}

.preview-column h4,
.history-column h4 {
  margin: 0 0 8px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.preview-box {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  padding: 14px;
  min-height: 120px;
  background: #f8fafc;
  margin-bottom: 14px;
  max-height: min(72vh, 820px);
  overflow: auto;
}

.preview-box.editable {
  background: linear-gradient(180deg, #f8fafc 0, #eef6f6 100%);
}

.preview-box.text-muted {
  color: #64748b;
}

.preview-box:deep(.page) {
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.12);
}

.preview-box:deep(.consent-inline-field) {
  outline: none;
  transition: box-shadow 120ms ease, background-color 120ms ease;
}

.preview-box:deep(.consent-inline-field[contenteditable="true"]) {
  cursor: text;
}

.preview-box:deep(.consent-inline-field[contenteditable="true"]:focus) {
  background: #fff;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18);
}

.preview-box:deep(.consent-inline-signature) {
  position: relative;
  display: inline-flex;
  align-items: stretch;
  justify-content: stretch;
  min-width: 190px;
  min-height: 64px;
  background: #fff;
  cursor: crosshair;
}

.preview-box:deep(.consent-inline-signature canvas) {
  width: 100%;
  height: 100%;
  touch-action: none;
}

.preview-box:deep(.consent-inline-signature img) {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-box:deep(.signature-clear) {
  position: absolute;
  top: 4px;
  right: 4px;
  min-height: 22px;
  padding: 2px 7px;
  border-color: #cbd5e1;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.92);
  color: #475569;
  font-size: 10px;
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
  border-color: #dbe3ee;
  border-radius: 7px;
  padding: 8px 10px;
}

.consent-row-main {
  display: grid;
  gap: 2px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
}

.consent-row-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.consent-row-actions button {
  min-height: 28px;
  padding: 3px 9px;
  font-size: 12px;
}

.consent-row-actions .danger { color: #b42318; }

.consent-row .name {
  font-weight: 600;
  color: #0f172a;
}

.consent-row .meta {
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 1024px) {
  .setup-row,
  .document-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .history-column {
    position: static;
  }
}
</style>

<template>
  <section ref="panelRef" class="workspace-panel consent-panel" data-test="consent-panel" @keydown.esc.stop="emitCancel">
    <header class="panel-header">
      <h3>{{ __("New Consent") }}</h3>
      <div class="actions">
        <button type="button" class="ghost" data-test="consent-cancel" :disabled="saving" @click="emitCancel">
          {{ __("Cancel") }}
        </button>
        <button
          type="button"
          class="ghost"
          data-test="consent-print-blank"
          :disabled="!previewHtml || isPreviewStale"
          @click="emitPrintBlank"
        >
          {{ __("Print blank") }}
        </button>
        <button
          v-if="enableWhatsappConsent"
          type="button"
          class="ghost"
          data-test="consent-send-whatsapp"
          :disabled="saving || sending || !canCreate"
          @click="emitSend"
        >
          {{ sending ? __("Sending...") : __("Send via WhatsApp") }}
        </button>
        <button
          type="button"
          class="primary"
          data-test="consent-create"
          :disabled="saving || sending || !canCreate || isPreviewStale"
          @click="emitCreate"
        >
          {{ saving ? __("Creating...") : __("Create") }}
        </button>
      </div>
    </header>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div v-if="!hasSessionContext" class="empty-state">
      {{ __("Consents are visit-scoped. Select or start an appointment session first.") }}
    </div>
    <div v-else>
      <div class="consent-workspace">
        <div class="setup-row">
          <div class="field-host" data-test="consent-template-host" :ref="(el) => bindHost('consent_form_template', el)"></div>
          <fieldset class="procedure-checklist" data-test="consent-procedures">
            <legend>{{ __("Procedures") }}</legend>
            <label v-for="option in procedureOptions" :key="option.value" class="procedure-option">
              <input
                v-model="selectedProcedures"
                type="checkbox"
                :value="option.value"
                :disabled="readOnly"
                @change="handleProcedureChange"
              />
              <span class="name">{{ option.label }}</span>
              <span v-if="option.description" class="meta">{{ option.description }}</span>
            </label>
            <p v-if="!procedureOptions.length" class="text-muted">{{ __("No procedures on this visit.") }}</p>
          </fieldset>
        </div>

        <div class="waiver-row" data-test="consent-waiver">
          <label class="waiver-toggle">
            <input v-model="waiver.enabled" type="checkbox" :disabled="readOnly" />
            <span>{{ __("Skip digital signature") }}</span>
          </label>
          <template v-if="waiver.enabled">
            <label v-for="option in WAIVER_REASONS" :key="option" class="waiver-option">
              <input v-model="waiver.choice" type="radio" :value="option" :disabled="readOnly" />
              <span>{{ __(option) }}</span>
            </label>
            <input
              v-if="waiver.choice === OTHER_REASON"
              v-model="waiver.other"
              type="text"
              class="form-control waiver-other"
              data-test="consent-waiver-other"
              :placeholder="__('Reason')"
              :disabled="readOnly"
            />
          </template>
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
              :class="{ editable: hasEditableFields, 'signature-waived': waiver.enabled }"
              v-html="previewMarkup"
            ></div>
            <div
              v-if="!previewLoading && previewHtml && !hasSignatureField && !waiver.enabled"
              class="consent-signature-block"
              data-test="consent-fallback-signature"
            >
              <span class="label">{{ __("Patient Signature") }}</span>
              <div ref="fallbackSignatureRef"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  saving: { type: Boolean, default: false },
  sending: { type: Boolean, default: false },
  error: { type: String, default: "" },
  hasSessionContext: { type: Boolean, default: false },
  procedureOptions: { type: Array, default: () => [] },
  preselected: { type: Array, default: () => [] },
  previewHtml: { type: String, default: "" },
  previewLoading: { type: Boolean, default: false },
  defaultSignedBy: { type: String, default: "" },
  resetKey: { type: Number, default: 0 },
  readOnly: { type: Boolean, default: false },
  enableWhatsappConsent: { type: Boolean, default: false },
})

const emit = defineEmits(["request-preview", "create", "send-whatsapp", "cancel", "print-blank"])

const SIGNATURE_LINE =
  '<span style="display:inline-block;min-width:240px;height:40px;border-bottom:1px solid #111827;"></span>'
const OTHER_REASON = "Other"
const WAIVER_REASONS = ["Signed on paper", "Verbal", OTHER_REASON]

const hosts = new Map()
const controls = new Map()
const hostTeardownTimers = new Map()
let renderQueued = false
let previewTimer = null
let signaturePadCleanup = null
const panelRef = ref(null)
const previewBoxRef = ref(null)
const hasEditableFields = ref(false)
// Templates without a signature slot get the panel's own pad below the preview.
const hasSignatureField = ref(true)
const fallbackSignatureRef = ref(null)
const formFieldValues = ref({})
const selectedProcedures = ref([...props.preselected])
const waiver = ref(emptyWaiver())
const localValues = ref({
  consent_form_template: "",
  signed_by: "",
  relationship: "",
  signature: "",
})

const previewPending = ref(false)
const canCreate = computed(() => props.hasSessionContext && !props.readOnly)
const isPreviewStale = computed(() => props.previewLoading || previewPending.value)
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

onMounted(() => {
  panelRef.value?.querySelector("button:not(:disabled), input, [tabindex]")?.focus()
})

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

async function renderControls() {
  if (!props.hasSessionContext) {
    teardownAllControls()
    return
  }

  await nextTick()

  const host = hosts.get("consent_form_template")
  if (!host) return
  const existing = controls.get("consent_form_template")
  if (existing && existing.__consentPanelHost === host) return

  if (existing) teardownControl("consent_form_template")
  host.innerHTML = ""

  const control = frappe.ui.form.make_control({
    parent: host,
    render_input: true,
    only_input: false,
    doc: { doctype: "Consent Form" },
    df: {
      fieldname: "consent_form_template",
      fieldtype: "Link",
      options: "Consent Form Template",
      label: __("Consent Template"),
      reqd: 1,
      read_only: props.readOnly ? 1 : 0,
      onchange: handleFieldChange,
    },
  })

  control.__consentPanelHost = host
  controls.set("consent_form_template", control)

  const value = localValues.value.consent_form_template
  if (value) control.set_value?.(value)
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

function resetDraft() {
  clearTimeout(previewTimer)
  previewPending.value = false
  teardownSignaturePad()
  formFieldValues.value = {}
  localValues.value = {
    consent_form_template: "",
    signed_by: props.defaultSignedBy || "",
    relationship: "",
    signature: "",
  }
  controls.get("consent_form_template")?.set_value?.("")
  selectedProcedures.value = [...props.preselected]
  waiver.value = emptyWaiver()
  nextTick(() => initializeEditablePreview())
}

function readValues() {
  const consentTemplate = controls.get("consent_form_template")?.get_value?.() || ""
  const selection = [...selectedProcedures.value]
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
  previewPending.value = true
  previewTimer = setTimeout(() => {
    previewPending.value = false
    const values = readValues()
    emit("request-preview", {
      consent_form_template: values.consent_form_template,
      procedure_selection: values.procedure_selection,
    })
  }, 160)
}

function handleProcedureChange() {
  // Drop rendered procedure text so the refreshed preview replaces it.
  const nextValues = { ...(formFieldValues.value || {}) }
  delete nextValues.procedure
  delete nextValues.procedures
  formFieldValues.value = nextValues
  handleFieldChange()
}

function emitCreate() {
  if (!canCreate.value || props.saving || isPreviewStale.value) return
  const values = readValues()
  if (!values.consent_form_template) {
    frappe.show_alert({ message: __("Consent template is required."), indicator: "orange" })
    return
  }
  if (!values.procedure_selection.length) {
    frappe.show_alert({ message: __("Select at least one procedure."), indicator: "orange" })
    return
  }
  if (waiver.value.enabled) return emitWaivedCreate(values)
  if (!values.signed_by) {
    frappe.show_alert({ message: __("Patient name is required on the consent form."), indicator: "orange" })
    return
  }
  if (!values.signature) {
    frappe.show_alert({ message: __("Signature is required on the consent form."), indicator: "orange" })
    return
  }

  emit("create", { ...values, rendered_html: collectRenderedHtml(values.signed_by) })
}

function emitWaivedCreate(values) {
  const reason = waiver.value.choice === OTHER_REASON ? waiver.value.other.trim() : waiver.value.choice
  if (!reason) {
    frappe.show_alert({ message: __("Give a reason for skipping the signature."), indicator: "orange" })
    return
  }
  emit("create", {
    ...values,
    signature: "",
    signature_waived: 1,
    waiver_reason: reason,
    rendered_html: collectRenderedHtml("", { signature: false }),
  })
}

function emitPrintBlank() {
  if (!props.previewHtml || isPreviewStale.value) return
  emit("print-blank", collectRenderedHtml("", { blank: true }))
}

function emptyWaiver() {
  return { enabled: false, choice: WAIVER_REASONS[0], other: "" }
}

function emitSend() {
  if (!canCreate.value || props.saving || props.sending) return
  const values = readValues()
  if (!values.consent_form_template) {
    frappe.show_alert({ message: __("Consent template is required."), indicator: "orange" })
    return
  }
  emit("send-whatsapp", { ...values, rendered_html: collectRenderedHtml(values.signed_by) })
}

function emitCancel() {
  if (!formFieldValues.value.signature) return emit("cancel")
  frappe.confirm(__("Discard this signed consent draft?"), () => emit("cancel"))
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
  hasSignatureField.value = fields.some((field) => getFieldName(field) === "signature")
  if (!hasSignatureField.value) {
    nextTick(() => {
      if (fallbackSignatureRef.value) setupInlineSignature(fallbackSignatureRef.value)
    })
  }

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

/**
 * The preview as a document. `signature` fills the signature slots with the drawn pad;
 * `blank` leaves a line to sign on paper; neither (a waived consent) leaves them empty.
 */
function collectRenderedHtml(signedBy = "", { signature = true, blank = false } = {}) {
  const host = previewBoxRef.value
  if (!host) return props.previewHtml || ""
  const drawn = signature && !blank ? formFieldValues.value.signature : ""
  const clone = host.cloneNode(true)
  for (const field of clone.querySelectorAll("[data-consent-field]")) {
    for (const attribute of ["contenteditable", "role", "tabindex", "spellcheck"]) field.removeAttribute(attribute)
    if (getFieldName(field) !== "signature") continue
    if (blank) field.innerHTML = SIGNATURE_LINE
    else if (drawn) field.innerHTML = `<img src="${drawn}" alt="${__("Signature")}">`
  }
  for (const leftover of clone.querySelectorAll(".signature-clear, canvas")) leftover.remove()
  return clone.innerHTML + appendedSignatureBlock(signedBy, drawn, blank)
}

/** Templates without a signature slot carry the signature after the document. */
function appendedSignatureBlock(signedBy, drawn, blank) {
  if (hasSignatureField.value) return ""
  if (blank) {
    return `<div class="consent-signature-block"><p>${__("Patient Signature")}: ${SIGNATURE_LINE}</p><p>${__("Date")}: ${SIGNATURE_LINE}</p></div>`
  }
  if (!drawn) return ""
  return `<div class="consent-signature-block"><p>${__("Signed by")}: ${frappe.utils.escape_html(signedBy)}</p><img src="${drawn}" alt="${__("Signature")}"></div>`
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
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
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
.preview-column {
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
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  align-items: start;
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

.preview-column h4 {
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

.preview-box:deep(.consent-inline-signature),
.consent-signature-block:deep(.consent-inline-signature) {
  position: relative;
  display: inline-flex;
  align-items: stretch;
  justify-content: stretch;
  min-width: 190px;
  min-height: 64px;
  background: #fff;
  cursor: crosshair;
}

.preview-box:deep(.consent-inline-signature canvas),
.consent-signature-block:deep(.consent-inline-signature canvas) {
  width: 100%;
  height: 100%;
  touch-action: none;
}

.preview-box:deep(.consent-inline-signature img),
.consent-signature-block:deep(.consent-inline-signature img) {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-box:deep(.signature-clear),
.consent-signature-block:deep(.signature-clear) {
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

.consent-signature-block {
  display: grid;
  gap: 6px;
  justify-items: start;
  margin-bottom: 14px;
}

.consent-signature-block .label {
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.consent-signature-block:deep(.consent-inline-signature) {
  width: 260px;
  height: 90px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
}

.waiver-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  color: #0f172a;
}

.waiver-toggle,
.waiver-option {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  margin: 0;
}

.waiver-toggle {
  font-weight: 700;
}

.waiver-other {
  max-width: 280px;
}

.preview-box.signature-waived:deep(.consent-inline-signature) {
  visibility: hidden;
}

.procedure-checklist {
  display: grid;
  gap: 6px;
  min-width: 0;
  margin: 0 0 10px;
  padding: 0;
  border: 0;
}

.procedure-checklist legend {
  margin-bottom: 4px;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.procedure-option {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 8px;
  align-items: baseline;
  font-size: 13px;
  color: #0f172a;
}

.procedure-option .meta {
  grid-column: 2;
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 1024px) {
  .setup-row,
  .document-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

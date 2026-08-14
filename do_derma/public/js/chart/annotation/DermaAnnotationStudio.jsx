import React, { useEffect, useMemo, useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import EmbeddedExcalidraw, { BADGE_KIND, TEMPLATE_PART_KIND, isAreaBehavior, isFreehandBehavior } from "../excalidraw/EmbeddedExcalidraw.jsx"

/** Layers the studio derives and re-renders on every load, so none of them mean "unsaved work". */
const DERIVED_KINDS = new Set([BADGE_KIND, TEMPLATE_PART_KIND, "derma_template"])

const __ = window.__ || ((text) => text)

function ensureProcessEnv() {
  if (!globalThis.process) {
    globalThis.process = { env: { NODE_ENV: "production" } }
  } else if (!globalThis.process.env) {
    globalThis.process.env = { NODE_ENV: "production" }
  } else if (!globalThis.process.env.NODE_ENV) {
    globalThis.process.env.NODE_ENV = "production"
  }
}

function makeId(prefix = "derma-annotation") {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function getContrastText(hexColor = "#0f766e") {
  const hex = String(hexColor || "#0f766e").replace("#", "")
  if (hex.length !== 6) return "#ffffff"
  const r = parseInt(hex.substring(0, 2), 16)
  const g = parseInt(hex.substring(2, 4), 16)
  const b = parseInt(hex.substring(4, 6), 16)
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5 ? "#ffffff" : "#172033"
}

function normalizeOptions(options) {
  if (Array.isArray(options)) return options
  return String(options || "")
    .split("\n")
    .map((option) => option.trim())
    .filter(Boolean)
}

function normalizeFieldname(label) {
  return String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

function groupedTemplates(templates = []) {
  const groups = new Map()
  for (const template of templates.filter((row) => row.image)) {
    const key = templateGroup(template)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(template)
  }
  return [...groups.entries()].map(([label, rows]) => ({
    label,
    rows: rows.sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0) || String(a.title || a.name).localeCompare(String(b.title || b.name))),
  }))
}

function templateGroup(template) {
  const type = String(template.template_type || template.view_key || template.title || "").toLowerCase()
  if (/face|head|ear|nose|neck/i.test(type)) return __("Head / Face")
  if (/scalp/i.test(type)) return __("Scalp")
  if (/hand|foot|feet/i.test(type)) return __("Hands / Feet")
  if (/body|chest|back|abdomen|arm|leg|groin/i.test(type)) return __("Body")
  return __("Other")
}

function procedureLabel(procedure = {}) {
  return procedure.template || procedure.title || procedure.name || ""
}

function procedureColor(procedure = {}) {
  return procedure.custom_derma_marker_color || procedure.color || "#0ea5e9"
}

function procedureVariables(procedure = {}) {
  return procedure.derma_variables || procedure.variables || []
}

function taggingHint(procedure, label) {
  if (isAreaBehavior(procedure)) {
    return __("Tagging as: {0} - drag on the canvas to outline the treated area.").replace("{0}", label)
  }
  if (isFreehandBehavior(procedure)) {
    return __("Tagging as: {0} - draw over the affected skin.").replace("{0}", label)
  }
  return __("Tagging as: {0} - click the canvas to place a mark.").replace("{0}", label)
}

function anchorDescription(context = {}) {
  if (context.clinicalProcedure) {
    return `${__("Procedure")} — ${context.procedureLabel || context.clinicalProcedure}`
  }
  return `${__("Consultation")} — ${context.patientName || context.patient || ""}`.trim()
}

function resumedTemplateName(annotation) {
  if (!annotation?.json) return ""
  try {
    return JSON.parse(annotation.json)?.derma_template?.name || ""
  } catch {
    return ""
  }
}

function collectBadgeItems(elements, partValues, parts, procedures) {
  const items = []
  const seenMarks = new Set()
  for (const element of elements || []) {
    if (element.isDeleted || element.customData?.kind !== "derma_mark") continue
    const procedureTemplateName = element.customData?.procedure_template
    if (!procedureTemplateName) continue
    const params = element.customData?.procedure_variables || element.customData?.variables || {}
    const hasParams = Object.values(params).some((value) => value !== "" && value !== null && value !== undefined)
    if (!hasParams) continue
    // A stamp is several elements sharing one group - a dot, its ring, its number - and they
    // are one clinical mark, so they get one badge between them.
    const markKey = markIdentity(element)
    if (seenMarks.has(markKey)) continue
    seenMarks.add(markKey)
    const centroid = elementCentroid(element)
    const procedure = procedures.find((row) => row.name === procedureTemplateName)
    items.push({
      type: "Procedure",
      name: procedureLabel(procedure) || procedureTemplateName,
      color: element.customData?.marker_color || procedureColor(procedure),
      params,
      ...centroid,
    })
  }
  for (const [partName, values] of Object.entries(partValues || {})) {
    const hasValues = values && Object.values(values).some((value) => value !== "" && value !== null && value !== undefined)
    if (!hasValues) continue
    const part = parts.find((row) => row.part_name === partName)
    const partElement = elements.find((element) => element.customData?.kind === "derma_template_part" && element.customData?.partName === partName && !element.isDeleted)
    items.push({
      type: "Area",
      name: partName,
      color: part?.color || "#38bdf8",
      params: values,
      ...elementCentroid(partElement),
    })
  }
  items.sort((a, b) => a.centroidY - b.centroidY || a.centroidX - b.centroidX)
  return items.map((item, index) => ({ ...item, badgeNum: index + 1 }))
}

function sanitizeMarkVariables(values = {}) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== ""))
}

function markIdentity(element = {}) {
  const custom = element.customData || {}
  return custom.derma_chart_mark || custom.mark_name || element.groupIds?.[0] || element.id
}

function elementCentroid(element = {}) {
  if (element.points?.length) {
    const avgX = element.points.reduce((sum, point) => sum + point[0], 0) / element.points.length
    const avgY = element.points.reduce((sum, point) => sum + point[1], 0) / element.points.length
    return {
      centroidX: element.x + avgX,
      centroidY: element.y + avgY,
      topY: element.y + Math.min(...element.points.map((point) => point[1])),
      boundsW: element.width || 0,
    }
  }
  return {
    centroidX: (element.x || 0) + (element.width || 0) / 2,
    centroidY: (element.y || 0) + (element.height || 0) / 2,
    topY: element.y || 0,
    boundsW: element.width || 0,
  }
}

function generateAnnotationDataHTML(items) {
  if (!items?.length) return ""
  const rows = items.map((item) => {
    const params = Object.entries(item.params || {})
      .filter(([, value]) => value !== "" && value !== null && value !== undefined)
      .map(([key, value]) => `<b>${escapeHtml(key)}</b>: ${escapeHtml(value)}`)
      .join(", ")
    const contrast = getContrastText(item.color)
    return `<tr style="border-bottom:1px solid #e5e7eb;">
      <td style="padding:6px 10px;"><span style="display:inline-block;width:22px;height:22px;border-radius:50%;background:${item.color};color:${contrast};text-align:center;line-height:22px;font-weight:bold;font-size:11px;">${item.badgeNum}</span></td>
      <td style="padding:6px 10px;">${escapeHtml(item.type)}</td>
      <td style="padding:6px 10px;font-weight:600;">${escapeHtml(item.name)}</td>
      <td style="padding:6px 10px;">${params}</td>
    </tr>`
  }).join("")
  return `<table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:13px;">
    <thead><tr style="background:#f8fafc;border-bottom:2px solid #dbe5ef;">
      <th style="padding:6px 10px;text-align:left;width:40px;">#</th>
      <th style="padding:6px 10px;text-align:left;width:90px;">Type</th>
      <th style="padding:6px 10px;text-align:left;">Name</th>
      <th style="padding:6px 10px;text-align:left;">Parameters</th>
    </tr></thead><tbody>${rows}</tbody></table>`
}

function escapeHtml(value) {
  const text = String(value ?? "")
  const frappeEscape = window.frappe?.utils?.escape_html
  if (frappeEscape) return frappeEscape(text)
  return text.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char])
}

function isTextEntry(element) {
  if (!element) return false
  const tag = element.tagName
  return tag === "INPUT" || tag === "TEXTAREA" || element.isContentEditable
}

function badgeElements(items) {
  const now = Date.now()
  return items.flatMap((item) => {
    const label = `${item.badgeNum}`
    const color = item.color || "#0ea5e9"
    const x = item.centroidX - 11
    const y = item.topY - 30
    // Deterministic, so an unchanged badge layer produces an unchanged signature and the
    // canvas can skip the redraw instead of looping on its own onChange.
    const groupId = `derma-badge-${item.badgeNum}`
    return [
      {
        id: `${groupId}-rect`,
        type: "ellipse",
        x,
        y,
        width: 22,
        height: 22,
        angle: 0,
        strokeColor: color,
        backgroundColor: color,
        fillStyle: "solid",
        strokeWidth: 0,
        strokeStyle: "solid",
        roughness: 0,
        opacity: 100,
        groupIds: [groupId],
        frameId: null,
        roundness: null,
        seed: now,
        version: 1,
        versionNonce: now + item.badgeNum,
        isDeleted: false,
        boundElements: null,
        updated: now,
        link: null,
        locked: true,
        customData: { kind: BADGE_KIND },
      },
      {
        id: `${groupId}-text`,
        type: "text",
        x: x + 7,
        y: y + 2,
        width: 8,
        height: 16,
        angle: 0,
        strokeColor: getContrastText(color),
        backgroundColor: "transparent",
        fillStyle: "solid",
        strokeWidth: 1,
        strokeStyle: "solid",
        roughness: 0,
        opacity: 100,
        groupIds: [groupId],
        frameId: null,
        roundness: null,
        seed: now + 1,
        version: 1,
        versionNonce: now + item.badgeNum + 1000,
        isDeleted: false,
        boundElements: null,
        updated: now,
        link: null,
        locked: true,
        text: label,
        fontSize: 13,
        fontFamily: 1,
        textAlign: "center",
        verticalAlign: "middle",
        containerId: null,
        originalText: label,
        // Excalidraw 0.17 still measures text against this legacy field. Without it the number
        // renders blank on the live canvas while appearing in the export, which is why the
        // badge layer looked unnumbered on screen.
        baseline: 11,
        lineHeight: 1.25,
        customData: { kind: BADGE_KIND },
      },
    ]
  })
}

function DermaAnnotationStudio({ context, bodyTemplates, procedureTemplates, annotation, marks, onClose, onSaved }) {
  ensureProcessEnv()
  const embeddedRef = useRef(null)
  const [drawer, setDrawer] = useState("")
  const [annotationName, setAnnotationName] = useState(annotation?.name || "")
  const [selectedTemplateName, setSelectedTemplateName] = useState(() => resumedTemplateName(annotation))
  const [selectedProcedures, setSelectedProcedures] = useState([])
  const [activeProcedure, setActiveProcedure] = useState("")
  const [procedureValues, setProcedureValues] = useState({})
  const [partValues, setPartValues] = useState({})
  const [selectedPart, setSelectedPart] = useState(null)
  const [saving, setSaving] = useState(false)
  const [includeBadges, setIncludeBadges] = useState(true)
  const [showAllTemplates, setShowAllTemplates] = useState(false)
  const [areasHidden, setAreasHidden] = useState(false)
  // Bumped by the canvas on every scene change, so the badge layer follows what is drawn.
  const [sceneRevision, setSceneRevision] = useState(0)
  // Set while the variable editor is bound to an existing mark rather than to the next one.
  const [editingMark, setEditingMark] = useState(null)
  // Signature of the drawing as last saved, so closing knows whether anything is at stake.
  const savedSignature = useRef(null)
  // Templates whose image failed to load this session, and the last one that did.
  const [unavailableTemplates, setUnavailableTemplates] = useState(() => new Set())
  const lastLoadedTemplateName = useRef("")
  const [renderedPartCount, setRenderedPartCount] = useState(0)

  // The consultation popup is a plain sketchpad: no procedure tagging, no badges
  // control, no right sidebar. Only a procedure anchor gets the full studio.
  const isProcedureAnchor = Boolean(context.clinicalProcedure)
  const anchorDoctype = isProcedureAnchor ? "Clinical Procedure" : "Patient Encounter"
  const anchorName = context.clinicalProcedure || context.encounter || ""
  const allTemplates = useMemo(() => (bodyTemplates || []).filter((template) => template.image), [bodyTemplates])
  // Default to the patient's sex; never an empty picker (unknown sex or zero matches shows all).
  const sexMatchedTemplates = useMemo(() => {
    const sex = context.patientSex
    if (!sex) return allTemplates
    const matched = allTemplates.filter((template) => !template.gender || template.gender === sex)
    return matched.length ? matched : allTemplates
  }, [allTemplates, context.patientSex])
  const templates = showAllTemplates ? allTemplates : sexMatchedTemplates
  const isSexFiltered = sexMatchedTemplates.length < allTemplates.length
  const procedures = useMemo(() => (procedureTemplates || []).filter((procedure) => procedure.name), [procedureTemplates])
  const templateGroups = useMemo(() => groupedTemplates(templates), [templates])
  // Resolve the selection against every template, so resuming a drawing made on an
  // off-sex template never silently swaps its background.
  const selectedTemplate =
    allTemplates.find((template) => template.name === selectedTemplateName) || templates[0] || null
  const selectedParts = selectedTemplate?.parts || []
  const activeProcedureDoc = procedures.find((procedure) => procedureLabel(procedure) === activeProcedure)
  // The editor binds to the mark being edited first, the armed procedure second.
  const editorProcedureName = editingMark?.procedure || activeProcedure
  const editorProcedureDoc = procedures.find((procedure) => procedureLabel(procedure) === editorProcedureName)

  useEffect(() => {
    if (!selectedTemplateName && templates[0]?.name) setSelectedTemplateName(templates[0].name)
  }, [selectedTemplateName, templates])

  useEffect(() => {
    if (!selectedTemplate?.image) return
    embeddedRef.current?.setBodyTemplate?.(selectedTemplate)
  }, [selectedTemplate?.name])

  useEffect(() => {
    // EmbeddedExcalidraw's "selectedTemplate" drives stamp shape/color (custom_derma_marker_behavior
    // etc. live on the Clinical Procedure Template, not the body-silhouette template above).
    embeddedRef.current?.setSelectedTemplate?.(activeProcedureDoc || null)
  }, [activeProcedureDoc])

  useEffect(() => {
    if (!activeProcedure) return
    const procedure = procedures.find((row) => procedureLabel(row) === activeProcedure)
    if (!procedure) return
    setProcedureValues((current) => {
      if (current[activeProcedure]) return current
      return {
        ...current,
        [activeProcedure]: Object.fromEntries(procedureVariables(procedure).map((field) => [field.variable_name || field.fieldname, ""])),
      }
    })
  }, [activeProcedure, procedures])

  useEffect(() => {
    embeddedRef.current?.setDermaTool?.(activeProcedure ? "mark" : "select")
  }, [activeProcedure])

  useEffect(() => {
    embeddedRef.current?.setProcedureVariables?.(procedureValues[activeProcedure] || {})
  }, [activeProcedure, procedureValues])

  const badgeItems = useMemo(() => {
    if (!includeBadges) return []
    const elements = (embeddedRef.current?.getElements?.() || []).filter((element) => !element.isDeleted)
    return collectBadgeItems(elements, partValues, selectedParts, procedures)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneRevision, includeBadges, partValues, selectedParts, procedures])

  useEffect(() => {
    embeddedRef.current?.setBadgeElements?.(badgeElements(badgeItems))
  }, [badgeItems])

  // Counts what is actually on the canvas, not what this session placed.
  const markCount = useMemo(() => {
    const elements = (embeddedRef.current?.getElements?.() || []).filter(
      (element) => !element.isDeleted && element.customData?.kind === "derma_mark"
    )
    return new Set(elements.map(markIdentity)).size
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneRevision])

  useEffect(() => {
    const filled = Object.entries(partValues)
      .filter(([, values]) => values && Object.values(values).some((value) => value !== "" && value !== null && value !== undefined))
      .map(([partName]) => partName)
    embeddedRef.current?.setPartStates?.({
      selected: selectedPart?.part_name || selectedPart?.partName || "",
      filled,
    })
  }, [selectedPart, partValues, selectedTemplate?.name])

  useEffect(() => {
    embeddedRef.current?.setPartsHidden?.(areasHidden)
  }, [areasHidden])

  // Marks, badges, area outlines and the template image are all re-derived on every load, so a
  // signature over them would prompt on a drawing nobody touched. Only what was drawn counts.
  function userSignature() {
    return (embeddedRef.current?.getElements?.() || [])
      .filter((element) => !element.isDeleted)
      .filter((element) => !element.customData?.generated_by && !DERIVED_KINDS.has(element.customData?.kind))
      .map((element) => `${element.id}:${element.version}`)
      .join("|")
  }

  // The canvas reports when its first scene has settled; anything after that is the
  // practitioner's. Taking the baseline off sceneRevision instead would swallow the
  // very first stroke, because that stroke is what bumps it.
  function handleSceneReady() {
    lastLoadedTemplateName.current = selectedTemplateName
    // Offer the areas toggle only when outlines are actually drawn, not merely configured on
    // the template. Read here rather than off sceneRevision: the canvas only signals a change
    // when the *mark* layer moves, so a part-only render would never reach a memo.
    setRenderedPartCount(embeddedRef.current?.getRenderedPartCount?.() || 0)
    if (savedSignature.current === null) savedSignature.current = userSignature()
  }

  /**
   * A body template whose image cannot be fetched (deleted file, or a /private/files URL the
   * session may not read) used to leave the old canvas in place and say nothing. Refuse the
   * selection out loud instead, and stop offering that card.
   */
  function handleTemplateLoadFailed(template) {
    const failedName = template?.name || ""
    if (failedName) setUnavailableTemplates((current) => new Set(current).add(failedName))
    window.frappe?.show_alert?.({
      message: __("Could not load {0}. Its image is unavailable.").replace("{0}", template?.title || failedName),
      indicator: "red",
    })
    setSelectedTemplateName(lastLoadedTemplateName.current || "")
  }

  /** The one way out. Closing is only unguarded when there is nothing to lose. */
  function requestClose() {
    if (savedSignature.current === null || userSignature() === savedSignature.current) {
      onClose?.()
      return
    }
    window.frappe.confirm(__("Discard this drawing? Unsaved changes will be lost."), () => onClose?.())
  }

  // The studio sits at z-index 2000 and Frappe's dialogs at 1050, so anything it raises -
  // the discard confirm, a save error - would open underneath it, invisible. The class lifts
  // them for as long as the studio is mounted and no longer.
  useEffect(() => {
    document.body.classList.add("derma-annotation-open")
    return () => document.body.classList.remove("derma-annotation-open")
  }, [])

  // Escape closes the studio, except while Excalidraw owns it - it ends text editing there.
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key !== "Escape" || isTextEntry(document.activeElement)) return
      requestClose()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleProcedure(procedure) {
    const name = procedureLabel(procedure)
    // Arming a procedure means "the next mark", so it ends any edit of an existing one.
    setEditingMark(null)
    setSelectedProcedures((current) => current.includes(name) ? current.filter((row) => row !== name) : [...current, name])
    setActiveProcedure((current) => (current === name ? "" : name))
  }

  function updateProcedureValue(procedureName, field, value) {
    const key = field.variable_name || field.fieldname
    setProcedureValues((current) => {
      const next = { ...current, [procedureName]: { ...(current[procedureName] || {}), [key]: value } }
      if (editingMark?.procedure === procedureName) persistMarkVariables(next[procedureName])
      return next
    })
  }

  /**
   * The Derma Chart Mark owns a mark's variables; the canvas element caches them so badges and
   * the legend can read them without a round trip. Written in that order, never one alone.
   */
  async function persistMarkVariables(values) {
    const target = editingMark
    if (!target?.name) return
    try {
      await window.frappe.call({
        method: "do_derma.api.save_chart_mark",
        args: { values: { name: target.name, patient: context.patient, ...sanitizeMarkVariables(values) } },
      })
      embeddedRef.current?.updateMarkVariables?.({ markName: target.name, variables: values })
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to update mark"), message: error.message || String(error), indicator: "red" })
    }
  }

  function updatePartValue(partName, field, value) {
    setPartValues((current) => ({
      ...current,
      [partName]: {
        ...(current[partName] || {}),
        [field.variable_name || field.fieldname]: value,
      },
    }))
  }

  async function handleMarkPlaced(payload) {
    if (!context?.encounter) {
      window.frappe?.msgprint?.(__("A Patient Encounter is required before placing a mark."))
      return
    }
    try {
      const response = await window.frappe.call({
        method: "do_derma.api.save_chart_mark",
        args: {
          values: {
            patient: context.patient,
            appointment: context.appointment,
            encounter: context.encounter,
            clinical_procedure: context.clinicalProcedure || null,
            procedure_template: payload.procedure_template,
            category: payload.category,
            marker_behavior: payload.marker_behavior,
            marker_color: payload.marker_color,
            body_template: payload.body_template,
            body_view: payload.body_view,
            body_region: payload.body_region,
            region_label: payload.region_label,
            x_percent: payload.x_percent,
            y_percent: payload.y_percent,
            // Present for drawn marks (area, freehand). It is the idempotency key the annotation
            // fan-out matches elements to marks by.
            annotation_json: payload.annotation_json || null,
            ...(payload.procedure_variables || {}),
          },
        },
      })
      const mark = response.message
      embeddedRef.current?.linkMarkElements?.({ mark, elementIds: payload.temp_element_ids })
      window.frappe.show_alert?.({ message: __("Mark saved"), indicator: "green" })
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to save mark"), message: error.message || String(error), indicator: "red" })
    }
  }

  /**
   * Clicking a mark reopens the variable editor bound to it, so a stroke or stamp can be
   * corrected after the fact instead of being redrawn. It edits only: placement mode is
   * armed exclusively by choosing a procedure in the drawer, and the drawer stays put.
   */
  function handleMarkSelected({ mark, element }) {
    if (!isProcedureAnchor) return
    const custom = element?.customData || {}
    const procedureTemplateName = custom.procedure_template
    const procedure = procedures.find((row) => row.name === procedureTemplateName)
    if (!procedure) {
      window.frappe?.show_alert?.({ message: __("Selected mark {0}").replace("{0}", mark), indicator: "blue" })
      return
    }
    const name = procedureLabel(procedure)
    setEditingMark({ name: mark, elementId: element?.id, procedure: name })
    // Editing replaces placing: a click on a mark must never leave a stamp armed.
    setActiveProcedure("")
    setProcedureValues((current) => ({ ...current, [name]: { ...(custom.procedure_variables || {}) } }))
  }

  function handleRegionSelected(region) {
    setSelectedPart(region || null)
  }

  async function save() {
    if (!anchorName) {
      window.frappe?.msgprint?.(__("A Patient Encounter is required before saving annotation."))
      return
    }
    setSaving(true)
    try {
      // The badges on screen are already in the scene, so they are the badges that export and
      // the badges this table describes - one computation, three outputs that cannot disagree.
      const exported = await embeddedRef.current?.exportScene?.()
      if (!exported) {
        window.frappe?.msgprint?.(__("The drawing surface is still loading."))
        return
      }
      const response = await window.frappe.call({
        method: "do_derma.api.save_derma_annotation",
        args: {
          payload: {
            patient: context.patient,
            appointment: context.appointment,
            encounter: context.encounter,
            doctype: anchorDoctype,
            docname: anchorName,
            clinical_procedure: context.clinicalProcedure || null,
            annotation_name: annotationName || null,
            annotation_template: selectedTemplate?.annotation_template || "",
            body_template: selectedTemplate?.name || "",
            body_template_title: selectedTemplate?.title || "",
            body_template_image: selectedTemplate?.image || "",
            annotation_type: badgeItems.length ? "Predefined Annotations" : "Free Drawing",
            // Left blank for a procedure anchor so the server owns the one rule that
            // procedure-anchored rows are typed "Treatment".
            encounter_type: context.clinicalProcedure ? "" : "Derma Annotation",
            annotation_data: generateAnnotationDataHTML(badgeItems),
            json_text: exported.json_text,
            file_data: exported.file_data,
          },
        },
      })
      window.frappe.show_alert?.({ message: __("Annotation saved"), indicator: "green" })
      if (response.message?.name) setAnnotationName(response.message.name)
      savedSignature.current = userSignature()
      onSaved?.(response.message)
      onClose?.()
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to save annotation"), message: error.message || String(error), indicator: "red" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="derma-annotation-modal" role="dialog" aria-modal="true">
      <div className="derma-annotation-backdrop" />
      <section
        className={`derma-annotation-shell ${drawer ? "drawer-open" : ""} ${activeProcedure || editingMark ? "tagging" : ""} ${isProcedureAnchor ? "" : "no-right"}`}
      >
        <header className="derma-annotation-header">
          <div>
            <strong data-test="annotation-anchor">{anchorDescription(context)}</strong>
            <span>
              {annotationName
                ? __("Editing the saved drawing. Saving updates it in place.")
                : __("New drawing. Use the template and procedure buttons when you need to change context.")}
            </span>
          </div>
          <div className="derma-annotation-header-actions">
            <button type="button" className={drawer === "templates" ? "active" : "ghost"} onClick={() => setDrawer(drawer === "templates" ? "" : "templates")}>{__("Templates")}</button>
            {isProcedureAnchor ? (
              <button type="button" className={drawer === "procedures" ? "active" : "ghost"} onClick={() => setDrawer(drawer === "procedures" ? "" : "procedures")}>{__("Procedures")}</button>
            ) : null}
            <button
              type="button"
              className="ghost"
              data-test="annotation-fit-template"
              title={__("Fit the body template back into view")}
              onClick={() => embeddedRef.current?.resetView?.()}
            >
              {__("Fit")}
            </button>
            {renderedPartCount ? (
              <button
                type="button"
                className={areasHidden ? "active" : "ghost"}
                data-test="annotation-hide-areas"
                title={__("Fade the predefined area outlines for a clean view")}
                onClick={() => setAreasHidden((hidden) => !hidden)}
              >
                {areasHidden ? __("Show Areas") : __("Hide Areas")}
              </button>
            ) : null}
            {isProcedureAnchor ? (
              <label data-test="annotation-badges-toggle" data-badge-count={badgeItems.length}>
                <input type="checkbox" checked={includeBadges} onChange={(event) => setIncludeBadges(event.target.checked)} />
                {badgeItems.length ? `${__("Badges")} (${badgeItems.length})` : __("Badges")}
              </label>
            ) : null}
            <button type="button" className="ghost" data-test="annotation-cancel" onClick={requestClose}>{__("Cancel")}</button>
            <button type="button" className="primary" disabled={saving || !selectedTemplate} onClick={save}>{saving ? __("Saving...") : __("Save Annotation")}</button>
          </div>
        </header>

        {activeProcedure || editingMark ? (
          <div className="derma-annotation-tagging-banner" data-test="annotation-tagging-mode">
            <span>
              {editingMark
                ? __("Editing a saved {0} mark - changes save as you type.").replace("{0}", editingMark.procedure)
                : taggingHint(activeProcedureDoc, activeProcedure)}
            </span>
            <button
              type="button"
              className="ghost small stop-tagging"
              onClick={() => {
                setEditingMark(null)
                setActiveProcedure("")
              }}
            >
              {editingMark ? __("Done") : __("Stop Tagging")}
            </button>
          </div>
        ) : null}

        {drawer ? <aside className="derma-annotation-left">
          {drawer === "templates" ? <div className="derma-annotation-panel">
            <h3>{__("Image Template")}</h3>
            {isSexFiltered || showAllTemplates ? (
              <label className="derma-template-show-all" data-test="annotation-show-all-templates">
                <input
                  type="checkbox"
                  checked={showAllTemplates}
                  onChange={(event) => setShowAllTemplates(event.target.checked)}
                />
                {showAllTemplates
                  ? __("Showing all templates")
                  : __("Show all (matching {0} only)").replace("{0}", __(context.patientSex || ""))}
              </label>
            ) : null}
            {templateGroups.map((group) => (
              <div className="derma-template-group" key={group.label}>
                <h4>{group.label}</h4>
                <div className="derma-template-list">
                  {group.rows.map((template) => {
                    const isUnavailable = unavailableTemplates.has(template.name)
                    return (
                      <button
                        type="button"
                        key={template.name}
                        className={`${selectedTemplate?.name === template.name ? "active" : ""} ${isUnavailable ? "unavailable" : ""}`.trim()}
                        disabled={isUnavailable}
                        data-test-unavailable={isUnavailable ? "true" : undefined}
                        onClick={() => setSelectedTemplateName(template.name)}
                      >
                        <TemplateThumbnail
                          template={template}
                          broken={isUnavailable}
                          onBroken={() => setUnavailableTemplates((current) => new Set(current).add(template.name))}
                        />
                        <b>{template.title || template.name}</b>
                        <small>{[template.gender, template.template_type].filter(Boolean).join(" / ")}</small>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
            {!templates.length ? <p className="derma-annotation-empty">{__("No derma body templates with images are configured.")}</p> : null}
          </div> : null}

          {drawer === "procedures" ? <div className="derma-annotation-panel">
            <h3>{__("Procedures")}</h3>
            <div className="derma-treatment-list">
              {procedures.map((procedure) => {
                const name = procedureLabel(procedure)
                return (
                  <button
                    type="button"
                    key={procedure.name}
                    className={`${selectedProcedures.includes(name) ? "selected" : ""} ${activeProcedure === name ? "active" : ""}`}
                    onClick={() => toggleProcedure(procedure)}
                    style={{ "--treatment-color": procedureColor(procedure) }}
                  >
                    <span />
                    <b>{name}</b>
                    <small>{procedureVariables(procedure).length ? `${procedureVariables(procedure).length} ${__("variable(s)")}` : __("No variables")}</small>
                  </button>
                )
              })}
            </div>
          </div> : null}
        </aside> : null}

        <main className="derma-annotation-canvas">
          <EmbeddedExcalidraw
            ref={embeddedRef}
            selectedTemplate={selectedTemplate}
            bodyTemplate={selectedTemplate}
            procedureVariables={procedureValues[activeProcedure] || {}}
            initialAnnotation={annotation}
            marks={marks || []}
            onMarkPlaced={handleMarkPlaced}
            onMarkSelected={handleMarkSelected}
            onRegionSelected={handleRegionSelected}
            onSceneChanged={() => setSceneRevision((revision) => revision + 1)}
            onSceneReady={handleSceneReady}
            onTemplateLoadFailed={handleTemplateLoadFailed}
          />
        </main>

        {isProcedureAnchor ? <aside className="derma-annotation-right">
          <div className="derma-annotation-panel">
            <h3>{editingMark ? __("Editing Mark") : __("Procedure Variables")}</h3>
            {editorProcedureDoc ? (
              <div data-test="annotation-variable-editor" data-editing-mark={editingMark?.name || ""}>
                <VariableEditor
                  title={editorProcedureName}
                  fields={procedureVariables(editorProcedureDoc)}
                  values={procedureValues[editorProcedureName] || {}}
                  onChange={(field, value) => updateProcedureValue(editorProcedureName, field, value)}
                />
              </div>
            ) : <p className="derma-annotation-empty">{__("Select a procedure, then click the canvas to place a tagged mark.")}</p>}
          </div>

          <div className="derma-annotation-panel">
            <h3>{__("Selected Area")}</h3>
            {selectedPart ? (
              <VariableEditor
                title={selectedPart.partName || selectedPart.part_name}
                fields={selectedPart.variables || []}
                values={partValues[selectedPart.partName || selectedPart.part_name] || {}}
                onChange={(field, value) => updatePartValue(selectedPart.partName || selectedPart.part_name, field, value)}
              />
            ) : <p className="derma-annotation-empty">{__("Click a predefined image part to fill area variables.")}</p>}
          </div>

          <div className="derma-annotation-panel">
            <h3>{__("Marks Placed")}</h3>
            <p className="derma-annotation-empty" data-test="annotation-mark-count" data-mark-count={markCount}>
              {markCount ? __("{0} tagged mark(s) on this drawing.").replace("{0}", markCount) : __("No marks placed yet.")}
            </p>
          </div>
        </aside> : null}
      </section>
    </div>
  )
}

/** `broken` is owned by the studio once a load has failed, so the card and the canvas agree. */
function TemplateThumbnail({ template, broken, onBroken }) {
  if (!template.image || broken) {
    return <span className="derma-template-thumb-missing">{__("Image unavailable")}</span>
  }
  return (
    <span>
      <img src={template.image} alt="" onError={onBroken} />
    </span>
  )
}

function VariableEditor({ title, fields, values, onChange }) {
  return (
    <div className="derma-variable-editor">
      <strong>{title}</strong>
      {(fields || []).map((field) => {
        const key = field.variable_name || field.fieldname || normalizeFieldname(field.label)
        const options = normalizeOptions(field.options)
        const type = field.type || field.fieldtype || "Data"
        return (
          <label key={key}>
            <span>{field.variable_name || field.label || key}</span>
            {type === "Select" ? (
              <select value={values[key] || ""} onChange={(event) => onChange(field, event.target.value)}>
                <option value="">{__("Select")}</option>
                {options.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            ) : type === "Check" ? (
              <input type="checkbox" checked={Boolean(values[key])} onChange={(event) => onChange(field, event.target.checked ? 1 : 0)} />
            ) : (
              <input value={values[key] || ""} onChange={(event) => onChange(field, event.target.value)} />
            )}
          </label>
        )
      })}
      {!fields?.length ? <p className="derma-annotation-empty">{__("No variables configured.")}</p> : null}
    </div>
  )
}

export function openDermaAnnotationStudio(options = {}) {
  const mount = document.createElement("div")
  document.body.appendChild(mount)
  const root = createRoot(mount)
  const close = () => {
    root.unmount()
    mount.remove()
  }
  root.render(
    <DermaAnnotationStudio
      context={options.context || {}}
      bodyTemplates={options.bodyTemplates || []}
      procedureTemplates={options.procedureTemplates || []}
      annotation={options.annotation || null}
      marks={options.marks || []}
      onSaved={options.onSaved}
      onClose={close}
    />
  )
  return { close }
}

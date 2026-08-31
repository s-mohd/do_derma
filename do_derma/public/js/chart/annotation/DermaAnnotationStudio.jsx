import React, { useEffect, useMemo, useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import EmbeddedExcalidraw, { BADGE_KIND, TEMPLATE_PART_KIND, isAreaBehavior, isFreehandBehavior } from "../excalidraw/EmbeddedExcalidraw.jsx"
import { variableFieldname } from "../../shared/variable_fieldname.js"
import { isBodyTemplateAllowed } from "../../shared/allowed_body_templates.js"
import { MARKER_SIZE_DEFAULT, MARKER_SIZE_STEP, markerSizeOf, steppedMarkerSize } from "../../shared/marker_size.js"
import MarkerSizeControl from "./MarkerSizeControl.jsx"
import { usePhotoCapture } from "./use_photo_capture.js"
import { describeError } from "../../shared/error_text.js"

/** Layers the studio derives and re-renders on every load, so none of them mean "unsaved work". */
const DERIVED_KINDS = new Set([BADGE_KIND, TEMPLATE_PART_KIND, "derma_template"])

const BADGE_DIAMETER = 22
const BADGE_FONT_SIZE = 13
const BADGE_MIN_DIAMETER = 18
const BADGE_MAX_DIAMETER = 34
const BADGE_MIN_FONT_SIZE = 11
const BADGE_MAX_FONT_SIZE = 16
const BADGE_GAP = 8

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

/** The key a variable's value is stored under - the studio, the mark and the badge all use it. */
function variableKey(field = {}) {
  return field.variable_name || field.fieldname || variableFieldname(field.label)
}

function variableLabel(field = {}) {
  return field.variable_name || field.label || variableKey(field)
}

/** One line of what a mark records, for a list that has no room for a form. */
function variableSummary(values = {}) {
  return Object.entries(values)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${value}`)
    .join(" · ")
}

/**
 * Empty is what the creation gate calls empty: unset or blank. The count speaks for the values
 * typed here, so a variable named outside the mark's own fieldnames (`product` for `product_name`)
 * can read filled while the gate still refuses it - the builder owns that collision.
 */
function missingRequiredVariables(variables, values = {}) {
  return (variables || []).filter((variable) => {
    if (!variable.required) return false
    const value = values[variableKey(variable)]
    return value === undefined || value === null || value === ""
  })
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

function procedureSearchText(procedure = {}) {
  return [procedureLabel(procedure), procedure.custom_derma_category, procedure.description]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
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

/** A Clinical Procedure names its patient ("Amina Haddad - Laser"); the header already does. */
function procedureAnchorLabel(context = {}) {
  const label = context.procedureTemplate || context.procedureLabel || context.clinicalProcedure || ""
  const patientName = context.patientName || ""
  const prefix = `${patientName} - `
  return patientName && label.startsWith(prefix) ? label.slice(prefix.length) : label
}

function anchorDescription(context = {}) {
  const patientName = context.patientName || context.patient || ""
  const anchor = context.clinicalProcedure
    ? `${__("Procedure")}: ${procedureAnchorLabel(context)}`
    : __("Consultation")
  return [patientName, anchor].filter(Boolean).join(" — ")
}

function parseAnnotationScene(annotation) {
  if (!annotation?.json) return null
  try {
    return JSON.parse(annotation.json)
  } catch {
    return null
  }
}

function resumedTemplateName(annotation) {
  return parseAnnotationScene(annotation)?.derma_template?.name || ""
}

function hasAreaValues(values) {
  return Boolean(values) && Object.values(values).some((value) => value !== "" && value !== null && value !== undefined)
}

function collectBadgeItems(elements, partValues, parts, procedures, selectedAreas) {
  const selected = new Set(selectedAreas || [])
  const markItems = []
  const areaItems = []
  const seenMarks = new Set()
  for (const element of elements || []) {
    if (element.isDeleted || element.customData?.kind !== "derma_mark") continue
    const procedureTemplateName = element.customData?.procedure_template
    if (!procedureTemplateName) continue
    // A tagged mark is legend-worthy on its template alone - unfilled variables must not drop it
    // from the numbering, or the sheet prints a mark with no row. Areas below differ: an untouched
    // outline came from the template, the practitioner never placed it.
    const params = element.customData?.procedure_variables || element.customData?.variables || {}
    // A stamp is several elements sharing one group - a dot, its ring, its number - and they
    // are one clinical mark, so they get one badge between them.
    const markKey = markIdentity(element)
    if (seenMarks.has(markKey)) continue
    seenMarks.add(markKey)
    const centroid = elementCentroid(element)
    const procedure = procedures.find((row) => row.name === procedureTemplateName)
    markItems.push({
      type: "Procedure",
      name: procedureLabel(procedure) || procedureTemplateName,
      color: element.customData?.marker_color || procedureColor(procedure),
      size: element.customData?.marker_size,
      markName: markNameOf(element),
      elementId: element.id,
      params,
      ...centroid,
    })
  }
  // Only the selected areas reach the exported image, so numbering an unselected one would
  // point the legend at an outline the image does not show.
  for (const [partName, values] of Object.entries(partValues || {})) {
    if (!selected.has(partName) || !hasAreaValues(values)) continue
    const part = parts.find((row) => row.part_name === partName)
    const partElement = elements.find((element) => element.customData?.kind === "derma_template_part" && element.customData?.partName === partName && !element.isDeleted)
    areaItems.push({
      type: "Area",
      name: partName,
      color: part?.color || "#38bdf8",
      params: values,
      ...elementCentroid(partElement),
    })
  }
  // Numbered in the order the marks were made - Derma Chart Mark names are a zero-padded
  // sequence, so sorting on them is creation order and survives both a canvas rebuild and
  // any z-order change. Sorting by position instead renumbered marks the practitioner had
  // already read off the legend every time a new mark or area landed above them. A mark
  // whose save is still in flight has no name yet and sits last, ahead of the areas.
  markItems.sort((a, b) => String(a.markName || "~").localeCompare(String(b.markName || "~")))
  return [...markItems, ...areaItems].map((item, index) => ({ ...item, badgeNum: index + 1 }))
}

function findTemplatePart(parts, partName) {
  if (!partName) return null
  return (parts || []).find((part) => (part.part_name || part.partName) === partName) || null
}

/**
 * One row per variable declared on the area, blanks included: dropping the empties would make
 * "measured and found normal" indistinguishable from "never looked". Null means the area
 * declares no variables, which leaves the mark's existing rows alone.
 */
function buildAreaVariableRows(part, values = {}) {
  if (!part?.variables?.length) return null
  return part.variables.map((variable) => ({
    fieldname: variable.fieldname || variable.variable_name,
    label: variable.variable_name || variable.fieldname,
    value: values[variable.variable_name] ?? values[variable.fieldname] ?? "",
  }))
}

/**
 * What the drawing already carries, so reopening shows what was typed. The saved scene owns
 * the areas nobody placed a mark on; the marks own the rest and win where both speak.
 */
function seedPartValues(marks, annotation) {
  const stored = parseAnnotationScene(annotation)?.derma_area_values
  const seeded = {}
  for (const [partName, values] of Object.entries(stored && typeof stored === "object" ? stored : {})) {
    if (values && typeof values === "object") seeded[partName] = { ...values }
  }
  for (const mark of marks || []) {
    if (!mark?.region_label || !mark.area_variables?.length) continue
    const values = { ...(seeded[mark.region_label] || {}) }
    for (const row of mark.area_variables) values[row.label || row.fieldname] = row.value
    seeded[mark.region_label] = values
  }
  return seeded
}

/**
 * The areas this drawing is about. A drawing saved before selection was stored says nothing,
 * so its value-holding areas stand in - resaving it must not strip them out of its image. A
 * stored empty list is a deliberate "none" and is honoured as such.
 */
function seedSelectedAreas(annotation, partValues) {
  const stored = parseAnnotationScene(annotation)?.derma_selected_areas
  if (Array.isArray(stored)) return stored.filter((partName) => typeof partName === "string" && partName)
  return Object.entries(partValues).filter(([, values]) => hasAreaValues(values)).map(([partName]) => partName)
}

function seedAreaMarks(marks) {
  const byPart = new Map()
  for (const mark of marks || []) {
    if (!mark?.name || !mark.region_label) continue
    byPart.set(mark.region_label, new Set(byPart.get(mark.region_label) || []).add(mark.name))
  }
  return byPart
}

function sanitizeMarkVariables(values = {}) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== ""))
}

/** The Derma Chart Mark an element belongs to, empty for an element that stands for no record. */
function markNameOf(element = {}) {
  const custom = element.customData || {}
  return custom.derma_chart_mark || custom.mark_name || ""
}

function markIdentity(element = {}) {
  return markNameOf(element) || element.groupIds?.[0] || element.id
}

/** Marks carried over from an earlier visit, drawn as an overlay. They are nobody's to edit. */
function isHistoryMark(name) {
  return String(name || "").startsWith("history:")
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
      <td style="padding:6px 10px;">${params || "\u2014"}</td>
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

/**
 * A badge grows with the mark it labels, but numbering is legibility rather than anatomy:
 * below the floor it is unreadable on a printed chart, above the ceiling it swallows the
 * mark beside it.
 */
function badgeGeometry(size) {
  const scale = markerSizeOf(size)
  const diameter = clampToRange(BADGE_DIAMETER * scale, BADGE_MIN_DIAMETER, BADGE_MAX_DIAMETER)
  const fontSize = clampToRange(BADGE_FONT_SIZE * scale, BADGE_MIN_FONT_SIZE, BADGE_MAX_FONT_SIZE)
  return { diameter, fontSize, offset: diameter + BADGE_GAP }
}

function clampToRange(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function badgeElements(items) {
  const now = Date.now()
  return items.flatMap((item) => {
    const label = `${item.badgeNum}`
    const color = item.color || "#0ea5e9"
    const { diameter, fontSize, offset } = badgeGeometry(item.size)
    const x = item.centroidX - diameter / 2
    const y = item.topY - offset
    // Deterministic, so an unchanged badge layer produces an unchanged signature and the
    // canvas can skip the redraw instead of looping on its own onChange.
    const groupId = `derma-badge-${item.badgeNum}`
    return [
      {
        id: `${groupId}-rect`,
        type: "ellipse",
        x,
        y,
        width: diameter,
        height: diameter,
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
        x: x + (diameter - fontSize * 0.62) / 2,
        y: y + (diameter - fontSize * 1.25) / 2,
        width: fontSize * 0.62,
        height: fontSize * 1.25,
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
        fontSize,
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
  const [partValues, setPartValues] = useState(() => seedPartValues(marks, annotation))
  // The areas the drawing is about: styled bold, exported, and saved with the annotation.
  const [selectedAreas, setSelectedAreas] = useState(() => seedSelectedAreas(annotation, seedPartValues(marks, annotation)))
  // The one area the variable editor is bound to. Transient - never saved.
  const [focusedArea, setFocusedArea] = useState("")
  const [saving, setSaving] = useState(false)
  const [discarding, setDiscarding] = useState(false)
  const [includeBadges, setIncludeBadges] = useState(true)
  const [showAllTemplates, setShowAllTemplates] = useState(false)
  const [showAllProcedures, setShowAllProcedures] = useState(false)
  const [procedureSearch, setProcedureSearch] = useState("")
  const [areasHidden, setAreasHidden] = useState(false)
  // Bumped by the canvas on every scene change, so the badge layer follows what is drawn.
  const [sceneRevision, setSceneRevision] = useState(0)
  // Set while the variable editor is bound to an existing mark rather than to the next one.
  const [editingMark, setEditingMark] = useState(null)
  // The multiplier the next stamp lands at, or the selected mark's own while one is edited.
  const [markerSize, setMarkerSize] = useState(MARKER_SIZE_DEFAULT)
  // The live size, for callers that must not read a value a pending render still holds.
  const markerSizeRef = useRef(MARKER_SIZE_DEFAULT)
  // Signature of the drawing as last saved, so closing knows whether anything is at stake.
  const savedSignature = useRef(null)
  // Marks this session wrote to the server before any annotation was saved. Discarding the
  // drawing has to take them with it, or the chart keeps a record nobody meant to make.
  const sessionMarks = useRef(new Set())
  // Every mark name that has been on the canvas this session. One missing at save time was
  // deleted by the practitioner, and its record has to go with it or it haunts the chart.
  const seenMarks = useRef(new Set())
  // The mark the last stamp created while its procedure is still armed. Values typed after
  // the click belong to that mark, not only to the next one.
  const lastPlacedMark = useRef(null)
  // Which marks sit on which area, so values typed after a mark was placed still reach it,
  // and which areas were edited this session - the untouched ones are already stored.
  const areaMarks = useRef(seedAreaMarks(marks))
  const touchedAreas = useRef(new Set())
  // Every write to a Derma Chart Mark queues here. Two saves of one mark in flight together
  // make the second one fail on the timestamp the first has already moved.
  const markWrites = useRef(Promise.resolve())
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
  const anchorProcedureDoc = useMemo(
    () => procedures.find((row) => row.name === context.procedureTemplate) || null,
    [procedures, context.procedureTemplate],
  )
  const anchorProcedureCategory = anchorProcedureDoc?.custom_derma_category || ""
  // Same rule the template picker uses for sex: filter to what this anchor is for, never to nothing.
  const categoryMatchedProcedures = useMemo(() => {
    if (!anchorProcedureCategory) return procedures
    const matched = procedures.filter((row) => row.custom_derma_category === anchorProcedureCategory)
    return matched.length ? matched : procedures
  }, [procedures, anchorProcedureCategory])
  const isCategoryFiltered = categoryMatchedProcedures.length < procedures.length
  const visibleProcedures = useMemo(() => {
    const pool = showAllProcedures ? procedures : categoryMatchedProcedures
    const needle = procedureSearch.trim().toLowerCase()
    if (!needle) return pool
    return pool.filter((row) => procedureSearchText(row).includes(needle))
  }, [procedures, categoryMatchedProcedures, showAllProcedures, procedureSearch])
  // The anchor's own procedure template decides which body map the studio opens on: save_chart_mark
  // refuses a map outside its allowed list, so opening on one would lose the first mark placed.
  // Same rule the pickers use for sex and category - narrow to the scope, never to nothing.
  const scopedTemplates = useMemo(() => {
    const matched = templates.filter((template) => isBodyTemplateAllowed(anchorProcedureDoc, template.name))
    return matched.length ? matched : templates
  }, [templates, anchorProcedureDoc])
  const templateGroups = useMemo(() => groupedTemplates(templates), [templates])
  // Resolve the selection against every template, so resuming a drawing made on an
  // off-sex template never silently swaps its background.
  const selectedTemplate =
    allTemplates.find((template) => template.name === selectedTemplateName) || scopedTemplates[0] || null
  const selectedParts = selectedTemplate?.parts || []
  // The area the variable editor is bound to, resolved against the template so the editor and
  // the canvas always describe the same row.
  const focusedPart = findTemplatePart(selectedParts, focusedArea)
  const activeProcedureDoc = procedures.find((procedure) => procedureLabel(procedure) === activeProcedure)
  // The editor binds to the mark being edited first, the armed procedure second.
  const editorProcedureName = editingMark?.procedure || activeProcedure
  const editorProcedureDoc = procedures.find((procedure) => procedureLabel(procedure) === editorProcedureName)
  // Areas and freehand strokes take their size from the gesture that drew them, so there is
  // nothing for the control to act on.
  const sizedBehavior = editingMark
    ? { custom_derma_marker_behavior: editingMark.behavior }
    : activeProcedureDoc
  const isSizeableMark = Boolean(
    sizedBehavior && !isAreaBehavior(sizedBehavior) && !isFreehandBehavior(sizedBehavior)
  )
  const photoCapture = usePhotoCapture({
    context,
    bodyTemplate: selectedTemplate,
    chartMarkName: editingMark?.name || "",
    embeddedRef,
  })

  // Opening from a procedure row already claims "Procedure: X" in the header, so the
  // canvas has to agree: list that procedure once, exactly as a click on it would.
  // Listing only - never arming. An armed procedure holds the canvas in mark-placement,
  // so the first click stamps a mark instead of selecting one, whether the drawing is
  // new or resumed. Tagging starts when the practitioner picks the procedure.
  const hasListedAnchor = useRef(false)
  useEffect(() => {
    if (hasListedAnchor.current || !isProcedureAnchor || !anchorProcedureDoc) return
    hasListedAnchor.current = true
    const name = procedureLabel(anchorProcedureDoc)
    setSelectedProcedures((current) => (current.includes(name) ? current : [...current, name]))
  }, [isProcedureAnchor, anchorProcedureDoc])

  useEffect(() => {
    if (!selectedTemplateName && scopedTemplates[0]?.name) setSelectedTemplateName(scopedTemplates[0].name)
  }, [selectedTemplateName, scopedTemplates])

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
        [activeProcedure]: Object.fromEntries(procedureVariables(procedure).map((field) => [variableKey(field), ""])),
      }
    })
  }, [activeProcedure, procedures])

  useEffect(() => {
    embeddedRef.current?.setDermaTool?.(activeProcedure ? "mark" : "select")
  }, [activeProcedure])

  // A size chosen for filler must not carry over onto the next procedure's marks, so
  // arming a procedure starts from that procedure's own default.
  useEffect(() => {
    if (!activeProcedure) return
    applyMarkerSize(markerSizeOf(activeProcedureDoc?.custom_derma_marker_size))
  }, [activeProcedure, activeProcedureDoc])

  useEffect(() => {
    embeddedRef.current?.setMarkerSize?.(markerSize)
  }, [markerSize])

  useEffect(() => {
    embeddedRef.current?.setProcedureVariables?.(procedureValues[activeProcedure] || {})
  }, [activeProcedure, procedureValues])

  // Numbered whether or not the badges are drawn: the marks panel lists them either way.
  const legendItems = useMemo(() => {
    const elements = (embeddedRef.current?.getElements?.() || []).filter((element) => !element.isDeleted)
    return collectBadgeItems(elements, partValues, selectedParts, procedures, selectedAreas)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneRevision, partValues, selectedParts, procedures, selectedAreas])
  const badgeItems = includeBadges ? legendItems : []

  useEffect(() => {
    embeddedRef.current?.setBadgeElements?.(badgeElements(badgeItems))
  }, [badgeItems])

  /** The real record names currently drawn, history overlays excluded. */
  function canvasMarkNames() {
    const names = new Set()
    for (const element of embeddedRef.current?.getElements?.() || []) {
      if (element.isDeleted || element.customData?.kind !== "derma_mark") continue
      const name = markNameOf(element)
      if (name && !isHistoryMark(name)) names.add(name)
    }
    return names
  }

  // A mark element deleted from the canvas takes its bindings with it: the variable editor
  // must not keep writing to a record whose drawing is gone.
  useEffect(() => {
    const live = canvasMarkNames()
    seenMarks.current = new Set([...seenMarks.current, ...live])
    if (editingMark?.name && !live.has(editingMark.name)) setEditingMark(null)
    if (lastPlacedMark.current?.name && !live.has(lastPlacedMark.current.name)) lastPlacedMark.current = null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneRevision, editingMark])

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
      .filter(([, values]) => hasAreaValues(values))
      .map(([partName]) => partName)
    embeddedRef.current?.setPartStates?.({ selected: selectedAreas, filled })
  }, [selectedAreas, partValues, selectedTemplate?.name])

  // A selection can only name areas that are on screen, so switching body template drops
  // whatever the previous template's areas contributed. Opening a drawing on the template it
  // was made with prunes nothing: an area disabled since then is still that drawing's, and
  // rewriting the stored selection behind the practitioner's back is not this effect's job.
  const seededTemplateName = useRef("")
  useEffect(() => {
    if (!selectedTemplate?.name) return
    const previous = seededTemplateName.current
    seededTemplateName.current = selectedTemplate.name
    if (!previous) return
    const declared = new Set(selectedParts.map((part) => part.part_name || part.partName))
    setSelectedAreas((current) =>
      current.every((partName) => declared.has(partName)) ? current : current.filter((partName) => declared.has(partName))
    )
    setFocusedArea((current) => (declared.has(current) ? current : ""))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplate?.name])

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
    photoCapture.rememberLoadedPhotos()
    // The mark layer is rebuilt for the template now on screen, and it only renders marks
    // belonging to it. Anything remembered from the previous template is absent by design,
    // not deleted by the practitioner, and pruning would destroy those records on save.
    seenMarks.current = canvasMarkNames()
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
    if (discarding) return
    const placedMarks = [...sessionMarks.current]
    const capturedPhotos = photoCapture.sessionPhotoCount()
    const isDrawingDirty = savedSignature.current !== null && userSignature() !== savedSignature.current
    if (!isDrawingDirty && !placedMarks.length && !capturedPhotos) {
      onClose?.()
      return
    }
    window.frappe.confirm(discardPrompt(placedMarks.length, capturedPhotos), () =>
      discardDrawing(placedMarks)
    )
  }

  /** Discarding costs whatever this session already wrote to the chart, so it says how much. */
  function discardPrompt(markCount, photoCount) {
    if (markCount && photoCount) {
      return __("Discard this drawing? The {0} mark(s) and {1} photo(s) added here are removed from the chart too.", [markCount, photoCount])
    }
    if (photoCount) {
      return __("Discard this drawing? The {0} photo(s) taken here are removed from the chart too.", [photoCount])
    }
    if (markCount) {
      return __("Discard this drawing? The {0} mark(s) placed here are removed from the chart too.", [markCount])
    }
    return __("Discard this drawing? Unsaved changes will be lost.")
  }

  /**
   * Marks are written at placement time, so discarding has to undo them itself. The server keeps
   * any the rest of the record depends on - say so rather than closing on a half-kept promise.
   */
  async function discardDrawing(markNames) {
    const hadPhotos = photoCapture.sessionPhotoCount() > 0
    let kept = []
    setDiscarding(true)
    try {
      if (markNames.length) {
        const response = await window.frappe.call({
          method: "do_derma.api.discard_chart_marks",
          args: { names: markNames },
        })
        kept = response.message?.kept || []
      }
      await photoCapture.discardSessionPhotos()
    } catch (error) {
      // Closing now would lose the drawing and keep the marks - the very thing being fixed.
      window.frappe?.msgprint?.({
        title: __("Unable to discard the marks"),
        message: `${describeError(error)}<br>${__("The drawing is still open, so nothing is lost.")}`,
        indicator: "red",
      })
      return
    } finally {
      setDiscarding(false)
    }
    sessionMarks.current = new Set(kept)
    onClose?.({ marksChanged: Boolean(markNames.length), photosChanged: hadPhotos })
    if (kept.length) {
      window.frappe?.msgprint?.({
        title: __("Some marks were kept"),
        message: __("{0} mark(s) are part of the record already and stay on the chart.").replace("{0}", kept.length),
        indicator: "orange",
      })
    }
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
    lastPlacedMark.current = null
    setSelectedProcedures((current) => current.includes(name) ? current.filter((row) => row !== name) : [...current, name])
    setActiveProcedure((current) => (current === name ? "" : name))
  }

  function updateProcedureValue(procedureName, field, value) {
    const key = variableKey(field)
    // The write stays out of the state updater: React runs an updater twice for one change
    // - once eagerly, once while rendering - and each run would be its own save.
    const next = { ...(procedureValues[procedureName] || {}), [key]: value }
    setProcedureValues((current) => ({ ...current, [procedureName]: { ...(current[procedureName] || {}), [key]: value } }))
    if (editingMark?.procedure === procedureName) {
      persistMarkVariables(editingMark.name, next)
    } else if (lastPlacedMark.current?.procedure === procedureName) {
      // Typing right after a stamp lands means "that mark": write behind so the value
      // reaches the record instead of only the next placement.
      persistMarkVariables(lastPlacedMark.current.name, next)
    }
  }

  /** Marks are saved one at a time, in the order the clinician typed them. */
  function queueMarkWrite(write) {
    markWrites.current = markWrites.current.then(write, write)
    return markWrites.current
  }

  /**
   * The Derma Chart Mark owns a mark's variables; the canvas element caches them so badges and
   * the legend can read them without a round trip. Written in that order, never one alone.
   */
  function persistMarkVariables(markName, values) {
    if (!markName) return Promise.resolve()
    return queueMarkWrite(async () => {
      try {
        await window.frappe.call({
          method: "do_derma.api.save_chart_mark",
          args: {
            values: {
              name: markName,
              patient: context.patient,
              ...sanitizeMarkVariables(values),
              // The whole dict, blanks included - the splat above feeds the mark's own
              // fields, this one owns the stored variable rows.
              procedure_variables: values,
            },
          },
        })
        embeddedRef.current?.updateMarkVariables?.({ markName, variables: values })
      } catch (error) {
        window.frappe?.msgprint?.({ title: __("Unable to update mark"), message: describeError(error), indicator: "red" })
      }
    })
  }

  /**
   * While a mark is selected the control belongs to that mark: the record owns its size and
   * the canvas redraws from what the record now says.
   */
  function applyMarkerSize(size) {
    markerSizeRef.current = size
    setMarkerSize(size)
  }

  function changeMarkerSize(value) {
    const size = steppedMarkerSize(value)
    applyMarkerSize(size)
    if (editingMark?.name) persistMarkSize(size)
  }

  /** Stepping reads the ref: two clicks inside one render both compute from the size
   * before either of them otherwise. */
  function stepMarkerSize(steps) {
    changeMarkerSize(markerSizeRef.current + steps * MARKER_SIZE_STEP)
  }

  function persistMarkSize(size) {
    const target = editingMark
    if (!target?.name) return Promise.resolve()
    return queueMarkWrite(async () => {
      try {
        await window.frappe.call({
          method: "do_derma.api.save_chart_mark",
          args: { values: { name: target.name, patient: context.patient, marker_size: size } },
        })
        embeddedRef.current?.resizeMarkElements?.({ markName: target.name, size })
      } catch (error) {
        window.frappe?.msgprint?.({
          title: __("Unable to resize mark"),
          message: describeError(error),
          indicator: "red",
        })
      }
    })
  }

  function rememberAreaMark(partName, markName) {
    if (!partName || !markName) return
    const next = new Map(areaMarks.current)
    next.set(partName, new Set(next.get(partName) || []).add(markName))
    areaMarks.current = next
  }

  /**
   * Area values are stored on the marks placed on that area, so a value typed after the mark
   * was placed has to be written back before the drawing is saved.
   */
  async function persistAreaVariables() {
    for (const partName of touchedAreas.current) {
      const rows = buildAreaVariableRows(findTemplatePart(selectedParts, partName), partValues[partName])
      if (!rows) continue
      try {
        for (const markName of areaMarks.current.get(partName) || []) {
          await queueMarkWrite(() =>
            window.frappe.call({
              method: "do_derma.api.save_chart_mark",
              args: { values: { name: markName, patient: context.patient, area_variables: rows } },
            })
          )
        }
      } catch (error) {
        // The drawing still saves below - losing it over an area value would cost more.
        window.frappe?.msgprint?.({
          title: __("Unable to save the area values for {0}").replace("{0}", partName),
          message: describeError(error),
          indicator: "orange",
        })
      }
    }
    touchedAreas.current = new Set()
  }

  function updatePartValue(partName, field, value) {
    touchedAreas.current = new Set(touchedAreas.current).add(partName)
    setPartValues((current) => ({
      ...current,
      [partName]: {
        ...(current[partName] || {}),
        [variableKey(field)]: value,
      },
    }))
  }

  async function handleMarkPlaced(payload) {
    if (!context?.encounter) {
      window.frappe?.msgprint?.(__("A Patient Encounter is required before placing a mark."))
      return
    }
    const areaRows = buildAreaVariableRows(
      findTemplatePart(selectedParts, payload.region_label),
      partValues[payload.region_label]
    )
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
            marker_size: payload.marker_size,
            body_template: payload.body_template,
            body_view: payload.body_view,
            body_region: payload.body_region,
            region_label: payload.region_label,
            // The exact area. body_region stays the coarse vocabulary, region_label the text.
            body_template_part: payload.template_part || null,
            x_percent: payload.x_percent,
            y_percent: payload.y_percent,
            // Present for drawn marks (area, freehand). It is the idempotency key the annotation
            // fan-out matches elements to marks by.
            annotation_json: payload.annotation_json || null,
            ...(payload.procedure_variables || {}),
            // The splat above feeds the mark's own fields; this key owns the variable rows.
            procedure_variables: payload.procedure_variables || {},
            // Omitted, not emptied, when the area declares nothing - an absent key leaves
            // whatever rows the mark already carries alone.
            ...(areaRows ? { area_variables: areaRows } : {}),
          },
        },
      })
      const mark = response.message
      if (mark?.name) {
        sessionMarks.current = new Set(sessionMarks.current).add(mark.name)
        lastPlacedMark.current = { name: mark.name, procedure: activeProcedure }
        rememberAreaMark(payload.region_label, mark.name)
      }
      embeddedRef.current?.linkMarkElements?.({ mark, elementIds: payload.temp_element_ids })
      // The link writes the mark's name onto elements the canvas already holds, which is
      // not a scene change it announces. Without this the panel lists one mark fewer than
      // the drawing shows until the next stroke.
      setSceneRevision((revision) => revision + 1)
      window.frappe.show_alert?.({ message: __("Mark saved"), indicator: "green" })
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to save mark"), message: describeError(error), indicator: "red" })
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
    setEditingMark({ name: mark, elementId: element?.id, procedure: name, behavior: custom.marker_behavior || "" })
    applyMarkerSize(markerSizeOf(custom.marker_size))
    // Editing replaces placing: a click on a mark must never leave a stamp armed.
    setActiveProcedure("")
    setProcedureValues((current) => ({ ...current, [name]: { ...(custom.procedure_variables || {}) } }))
  }

  /**
   * Clicking an area selects it and opens its editor; clicking the area already open closes
   * it and unselects it. Reopening a selected area never costs the selection - correcting a
   * typed value must not be a trap - and a click on bare canvas only closes the editor.
   */
  function handleRegionSelected(region, { isPlacingMark } = {}) {
    const partName = region?.partName || region?.part_name || ""
    if (!partName) {
      setFocusedArea("")
      return
    }
    if (!selectedAreas.includes(partName)) {
      setSelectedAreas((current) => [...current, partName])
      setFocusedArea(partName)
      return
    }
    // The same click also places a mark while a procedure is armed. Unselecting there would
    // drop the area from the image on the second stamp inside it.
    if (focusedArea !== partName || isPlacingMark) {
      setFocusedArea(partName)
      return
    }
    unselectArea(partName)
  }

  /** Values typed into the area stay behind, so reselecting it shows them again. */
  function unselectArea(partName) {
    setSelectedAreas((current) => current.filter((name) => name !== partName))
    setFocusedArea((current) => (current === partName ? "" : current))
  }

  /**
   * The marks the badge layer numbers, in badge order. A mark under an area outline is hard
   * to click - the part wins the hit-test - so the list is also the way to reach one.
   */
  const placedMarkItems = useMemo(
    () =>
      legendItems.filter(
        (item) => item.type === "Procedure" && item.markName && !isHistoryMark(item.markName)
      ),
    [legendItems],
  )

  /** Picking a mark from the list is the same act as clicking it on the canvas. */
  function focusMark(item) {
    embeddedRef.current?.selectMark?.(item.markName)
    const element = (embeddedRef.current?.getElements?.() || []).find((row) => row.id === item.elementId)
    if (element) handleMarkSelected({ mark: item.markName, element })
  }

  /** Marks whose procedure declares required variables the canvas cache leaves blank. */
  function requiredVariableGaps() {
    const gaps = []
    const counted = new Set()
    for (const element of embeddedRef.current?.getElements?.() || []) {
      if (element.isDeleted || element.customData?.kind !== "derma_mark") continue
      const markKey = markIdentity(element)
      if (counted.has(markKey) || isHistoryMark(markKey)) continue
      counted.add(markKey)
      const procedure = procedures.find((row) => row.name === element.customData?.procedure_template)
      if (!procedure) continue
      const missing = missingRequiredVariables(
        procedureVariables(procedure),
        element.customData?.procedure_variables || {}
      )
      if (missing.length) {
        gaps.push({ procedure: procedureLabel(procedure), missing: missing.map(variableLabel) })
      }
    }
    return gaps
  }

  /** Saving with blanks stays allowed - mid-procedure is no time for a locked form - but not unannounced. */
  function confirmRequiredGaps(gaps) {
    const summary = gaps
      .map((gap) => `${escapeHtml(gap.procedure)}: ${escapeHtml(gap.missing.join(", "))}`)
      .join("<br>")
    return new Promise((resolve) => {
      window.frappe.confirm(
        `${__("{0} mark(s) are missing required values:", [gaps.length])}<br>${summary}<br>${__("Save anyway?")}`,
        () => resolve(true),
        () => resolve(false)
      )
    })
  }

  /**
   * A mark element deleted from the drawing means the record goes too - the same contract
   * photos honour. The server still refuses marks an active procedure depends on.
   */
  async function reconcileDeletedMarks(savedAnnotationName) {
    const live = canvasMarkNames()
    const removed = [...seenMarks.current].filter((name) => !live.has(name))
    if (!removed.length) return false
    let kept = []
    try {
      const response = await queueMarkWrite(() =>
        window.frappe.call({
          method: "do_derma.api.prune_chart_marks",
          args: { names: removed, annotation: savedAnnotationName || null },
        })
      )
      kept = response?.message?.kept || []
    } catch (error) {
      window.frappe?.msgprint?.({
        title: __("Unable to remove the deleted marks"),
        message: describeError(error),
        indicator: "orange",
      })
      return false
    }
    seenMarks.current = live
    sessionMarks.current = new Set([...sessionMarks.current].filter((name) => live.has(name)))
    if (kept.length) {
      window.frappe?.msgprint?.({
        title: __("Some deleted marks were kept"),
        message: __("{0} mark(s) are part of the record already and stay on the chart.").replace("{0}", kept.length),
        indicator: "orange",
      })
    }
    return true
  }

  async function save() {
    if (!anchorName) {
      window.frappe?.msgprint?.(__("A Patient Encounter is required before saving annotation."))
      return
    }
    const gaps = requiredVariableGaps()
    if (gaps.length && !(await confirmRequiredGaps(gaps))) return
    setSaving(true)
    try {
      // The badges on screen are already in the scene, so they are the badges that export and
      // the badges this table describes - one computation, three outputs that cannot disagree.
      const exported = await embeddedRef.current?.exportScene?.()
      if (!exported) {
        window.frappe?.msgprint?.(__("The drawing surface is still loading."))
        return
      }
      await persistAreaVariables()
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
            // The durable owner of area values: a mark carries them only where one was placed.
            area_values: partValues,
            // What the exported image shows, so a reopen comes back looking like the file.
            selected_areas: selectedAreas,
            json_text: exported.json_text,
            file_data: exported.file_data,
          },
        },
      })
      // Claimed before the reconciliations below: they can throw, and a retry that still
      // thought the drawing was unsaved would file a second annotation for it.
      const savedName = response.message?.name || annotationName
      if (response.message?.name) setAnnotationName(response.message.name)
      savedSignature.current = userSignature()
      // Saved marks belong to the annotation now; a later discard must not reach for them.
      sessionMarks.current = new Set()
      // A photo deleted from the canvas is deleted from the record here, and nowhere earlier:
      // undo before saving gives both the element and the photo back, and a save that failed
      // above leaves the photo alone.
      await photoCapture.reconcileDeletedPhotos()
      const marksPruned = await reconcileDeletedMarks(savedName)
      window.frappe.show_alert?.({ message: __("Annotation saved"), indicator: "green" })
      onSaved?.(response.message)
      onClose?.({ marksChanged: marksPruned })
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to save annotation"), message: describeError(error), indicator: "red" })
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
            <button type="button" className="ghost" data-test="annotation-cancel" disabled={discarding} onClick={requestClose}>{discarding ? __("Discarding...") : __("Cancel")}</button>
            <button type="button" className="primary" disabled={saving || discarding || !selectedTemplate} onClick={save}>{saving ? __("Saving...") : __("Save Annotation")}</button>
          </div>
        </header>

        {activeProcedure || editingMark ? (
          <div className="derma-annotation-tagging-banner" data-test="annotation-tagging-mode">
            <span>
              {editingMark
                ? __("Editing a saved {0} mark - changes save as you type.").replace("{0}", editingMark.procedure)
                : taggingHint(activeProcedureDoc, activeProcedure)}
            </span>
            {isSizeableMark ? <MarkerSizeControl size={markerSize} onChange={changeMarkerSize} onStep={stepMarkerSize} /> : null}
            <button
              type="button"
              className="ghost small stop-tagging"
              onClick={() => {
                setEditingMark(null)
                setActiveProcedure("")
                lastPlacedMark.current = null
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
            <input
              type="search"
              className="derma-annotation-search"
              data-test="annotation-procedure-search"
              value={procedureSearch}
              placeholder={__("Search procedures")}
              onChange={(event) => setProcedureSearch(event.target.value)}
            />
            {isCategoryFiltered || showAllProcedures ? (
              <label className="derma-template-show-all" data-test="annotation-show-all-procedures">
                <input
                  type="checkbox"
                  checked={showAllProcedures}
                  onChange={(event) => setShowAllProcedures(event.target.checked)}
                />
                {showAllProcedures
                  ? __("Showing all categories")
                  : __("Show all ({0} only)").replace("{0}", anchorProcedureCategory)}
              </label>
            ) : null}
            <div className="derma-treatment-list">
              {visibleProcedures.map((procedure) => {
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
            {!visibleProcedures.length ? (
              <p className="derma-annotation-empty" data-test="annotation-procedure-empty">
                {procedures.length
                  ? __("No procedure template matches this search.")
                  : __("No derma procedure templates are configured.")}
              </p>
            ) : null}
          </div> : null}
        </aside> : null}

        <main className="derma-annotation-canvas">
          <button
            type="button"
            className="derma-photo-capture"
            data-test="annotation-capture-photo"
            disabled={photoCapture.isBusy}
            title={__("Photograph the lesion into this drawing")}
            onClick={photoCapture.capture}
          >
            <PhotoCaptureIcon />
            <span>{photoCapture.isBusy ? __("Saving...") : __("Photo")}</span>
          </button>
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
            <p
              className="derma-annotation-empty"
              data-test="annotation-selected-area-count"
              data-selected-count={selectedAreas.length}
            >
              {selectedAreas.length
                ? __("{0} area(s) selected. The saved image shows these only.").replace("{0}", selectedAreas.length)
                : __("No areas selected. Click a predefined image part to select it and fill its variables.")}
            </p>
            {focusedPart ? (
              <>
                <VariableEditor
                  title={focusedArea}
                  fields={focusedPart.variables || []}
                  values={partValues[focusedArea] || {}}
                  onChange={(field, value) => updatePartValue(focusedArea, field, value)}
                />
                <button
                  type="button"
                  className="ghost"
                  data-test="annotation-unselect-area"
                  title={__("Take this area out of the saved image. Its values are kept.")}
                  onClick={() => unselectArea(focusedArea)}
                >
                  {__("Unselect this area")}
                </button>
              </>
            ) : null}
          </div>

          <div className="derma-annotation-panel">
            <h3>{__("Marks Placed")}</h3>
            <p className="derma-annotation-empty" data-test="annotation-mark-count" data-mark-count={markCount}>
              {markCount ? __("{0} tagged mark(s) on this drawing.").replace("{0}", markCount) : __("No marks placed yet.")}
            </p>
            {placedMarkItems.length ? (
              <ul className="derma-mark-list" data-test="annotation-mark-list">
                {placedMarkItems.map((item) => (
                  <li key={item.markName || item.elementId}>
                    <button
                      type="button"
                      className={editingMark?.name === item.markName ? "active" : ""}
                      title={__("Show this mark on the drawing")}
                      onClick={() => focusMark(item)}
                    >
                      <span className="derma-mark-badge" style={{ background: item.color, color: getContrastText(item.color) }}>
                        {item.badgeNum}
                      </span>
                      <b>{item.name}</b>
                      <small>{variableSummary(item.params) || __("No values recorded")}</small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </aside> : null}
      </section>
    </div>
  )
}

function PhotoCaptureIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.2-2h8.2l1.2 2h2.2A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z" />
      <circle cx="12" cy="13" r="3.4" />
    </svg>
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

/** Required is shown, never enforced: placing a mark mid-procedure must not be refused. */
function VariableEditor({ title, fields, values, onChange }) {
  const missing = missingRequiredVariables(fields, values)
  return (
    <div className="derma-variable-editor">
      <strong>{title}</strong>
      {missing.length ? (
        <p
          className="derma-variable-required-note"
          data-test="annotation-variable-required-note"
          data-missing-count={missing.length}
        >
          {__("{0} required variable(s) missing: {1}", [missing.length, missing.map(variableLabel).join(", ")])}
        </p>
      ) : null}
      {(fields || []).map((field) => {
        const key = variableKey(field)
        const options = normalizeOptions(field.options)
        const type = field.type || field.fieldtype || "Data"
        return (
          <label key={key} data-test="annotation-variable-row" data-fieldname={key} data-required={field.required ? "1" : "0"}>
            <span>
              {variableLabel(field)}
              {field.required ? (
                <abbr className="derma-variable-required" title={__("Required")} data-test="annotation-variable-required">*</abbr>
              ) : null}
            </span>
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
  // `result` carries what closing changed on the server (a discard deletes the marks it placed),
  // so the host chart knows whether it has to reload.
  const close = (result) => {
    root.unmount()
    mount.remove()
    options.onClose?.(result || {})
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

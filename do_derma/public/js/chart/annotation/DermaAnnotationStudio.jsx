import React, { useEffect, useMemo, useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import EmbeddedExcalidraw, { isAreaBehavior } from "../excalidraw/EmbeddedExcalidraw.jsx"

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
  for (const element of elements || []) {
    if (element.isDeleted || element.customData?.kind !== "derma_mark") continue
    const procedureTemplateName = element.customData?.procedure_template
    if (!procedureTemplateName) continue
    const params = element.customData?.procedure_variables || element.customData?.variables || {}
    const hasParams = Object.values(params).some((value) => value !== "" && value !== null && value !== undefined)
    if (!hasParams) continue
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

function badgeElements(items) {
  const now = Date.now()
  return items.flatMap((item) => {
    const label = `${item.badgeNum}`
    const color = item.color || "#0ea5e9"
    const x = item.centroidX - 11
    const y = item.topY - 30
    const groupId = makeId("badge")
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
        customData: { _badge: true },
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
        lineHeight: 1.25,
        customData: { _badge: true },
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
  const [placedMarkCount, setPlacedMarkCount] = useState(0)

  const anchorDoctype = context.clinicalProcedure ? "Clinical Procedure" : "Patient Encounter"
  const anchorName = context.clinicalProcedure || context.encounter || ""
  const templates = useMemo(() => (bodyTemplates || []).filter((template) => template.image), [bodyTemplates])
  const procedures = useMemo(() => (procedureTemplates || []).filter((procedure) => procedure.name), [procedureTemplates])
  const templateGroups = useMemo(() => groupedTemplates(templates), [templates])
  const selectedTemplate = templates.find((template) => template.name === selectedTemplateName) || templates[0] || null
  const selectedParts = selectedTemplate?.parts || []
  const activeProcedureDoc = procedures.find((procedure) => procedureLabel(procedure) === activeProcedure)

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

  function toggleProcedure(procedure) {
    const name = procedureLabel(procedure)
    setSelectedProcedures((current) => current.includes(name) ? current.filter((row) => row !== name) : [...current, name])
    setActiveProcedure((current) => (current === name ? "" : name))
  }

  function updateProcedureValue(procedureName, field, value) {
    setProcedureValues((current) => ({
      ...current,
      [procedureName]: {
        ...(current[procedureName] || {}),
        [field.variable_name || field.fieldname]: value,
      },
    }))
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
            ...(payload.procedure_variables || {}),
          },
        },
      })
      const mark = response.message
      embeddedRef.current?.linkMarkElements?.({ mark, elementIds: payload.temp_element_ids })
      setPlacedMarkCount((count) => count + 1)
      window.frappe.show_alert?.({ message: __("Mark saved"), indicator: "green" })
    } catch (error) {
      window.frappe?.msgprint?.({ title: __("Unable to save mark"), message: error.message || String(error), indicator: "red" })
    }
  }

  function handleMarkSelected({ mark }) {
    window.frappe?.show_alert?.({ message: __("Selected mark {0}").replace("{0}", mark), indicator: "blue" })
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
      const elements = (embeddedRef.current?.getElements?.() || []).filter((element) => !element.isDeleted)
      const badgeItems = collectBadgeItems(elements, partValues, selectedParts, procedures)
      const addedBadges = includeBadges ? badgeElements(badgeItems) : []
      const exported = await embeddedRef.current?.exportScene?.({ extraElements: addedBadges })
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
      <div className="derma-annotation-backdrop" onClick={onClose} />
      <section className={`derma-annotation-shell ${drawer ? "drawer-open" : ""} ${activeProcedure ? "tagging" : ""}`}>
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
            <button type="button" className={drawer === "procedures" ? "active" : "ghost"} onClick={() => setDrawer(drawer === "procedures" ? "" : "procedures")}>{__("Procedures")}</button>
            <button
              type="button"
              className="ghost"
              data-test="annotation-fit-template"
              title={__("Fit the body template back into view")}
              onClick={() => embeddedRef.current?.resetView?.()}
            >
              {__("Fit")}
            </button>
            <label>
              <input type="checkbox" checked={includeBadges} onChange={(event) => setIncludeBadges(event.target.checked)} />
              {__("Badges")}
            </label>
            <button type="button" className="ghost" onClick={onClose}>{__("Cancel")}</button>
            <button type="button" className="primary" disabled={saving || !selectedTemplate} onClick={save}>{saving ? __("Saving...") : __("Save Annotation")}</button>
          </div>
        </header>

        {activeProcedure ? (
          <div className="derma-annotation-tagging-banner">
            <span>
              {isAreaBehavior(activeProcedureDoc)
                ? __("Tagging as: {0} - drag on the canvas to outline the treated area.").replace("{0}", activeProcedure)
                : __("Tagging as: {0} - click the canvas to place a mark.").replace("{0}", activeProcedure)}
            </span>
            <button type="button" className="ghost small stop-tagging" onClick={() => setActiveProcedure("")}>{__("Stop Tagging")}</button>
          </div>
        ) : null}

        {drawer ? <div className="derma-annotation-drawer-scrim" onClick={() => setDrawer("")} /> : null}
        {drawer ? <aside className="derma-annotation-left">
          {drawer === "templates" ? <div className="derma-annotation-panel">
            <h3>{__("Image Template")}</h3>
            {templateGroups.map((group) => (
              <div className="derma-template-group" key={group.label}>
                <h4>{group.label}</h4>
                <div className="derma-template-list">
                  {group.rows.map((template) => (
                    <button
                      type="button"
                      key={template.name}
                      className={selectedTemplate?.name === template.name ? "active" : ""}
                      onClick={() => setSelectedTemplateName(template.name)}
                    >
                      <TemplateThumbnail template={template} />
                      <b>{template.title || template.name}</b>
                      <small>{[template.gender, template.template_type].filter(Boolean).join(" / ")}</small>
                    </button>
                  ))}
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
          />
        </main>

        <aside className="derma-annotation-right">
          <div className="derma-annotation-panel">
            <h3>{__("Procedure Variables")}</h3>
            {activeProcedureDoc ? (
              <VariableEditor
                title={activeProcedure}
                fields={procedureVariables(activeProcedureDoc)}
                values={procedureValues[activeProcedure] || {}}
                onChange={(field, value) => updateProcedureValue(activeProcedure, field, value)}
              />
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
            <p className="derma-annotation-empty">
              {placedMarkCount ? __("{0} mark(s) saved this session.").replace("{0}", placedMarkCount) : __("No marks placed yet.")}
            </p>
          </div>
        </aside>
      </section>
    </div>
  )
}

function TemplateThumbnail({ template }) {
  const [broken, setBroken] = useState(false)
  if (!template.image || broken) {
    return <span className="derma-template-thumb-missing">{__("Image unavailable")}</span>
  }
  return (
    <span>
      <img src={template.image} alt="" onError={() => setBroken(true)} />
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

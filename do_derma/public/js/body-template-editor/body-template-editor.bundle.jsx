import React, { useCallback, useEffect, useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import { Excalidraw } from "@excalidraw/excalidraw"

import { closeTolerance, validateAreaPolygon } from "./polygon"

const __ = window.__ || ((text) => text)
const generateId = () => `derma-part-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

/** Why a stroke was refused, in the words the practitioner needs to fix it. */
const outlineRefusalMessage = (reason) => {
  if (reason === "too_few_points") return __("Draw at least three points before closing the area.")
  if (reason === "self_intersecting") return __("The outline crosses itself. Redraw it without crossing.")
  return __("Finish the outline where it started. An open shape cannot become an area.")
}

const hexToRgba = (hex = "#4dabf7", opacity = 0.2) => {
  const clean = String(hex || "#4dabf7").replace("#", "")
  if (clean.length !== 6) return hex
  const red = parseInt(clean.slice(0, 2), 16)
  const green = parseInt(clean.slice(2, 4), 16)
  const blue = parseInt(clean.slice(4, 6), 16)
  return `rgba(${red}, ${green}, ${blue}, ${Math.min(1, Math.max(0, Number(opacity || 0)))})`
}

const toEditablePart = (part) => ({
  ...part,
  localId: generateId(),
  opacity: Number(part.opacity || 0.2),
  variables: part.variables || [],
})

/**
 * Merge the save response into the local rows by part_name, never by array index:
 * the response also carries retired regions, so index positions no longer line up.
 * @param {Array<object>} current
 * @param {Array<object>} saved
 * @returns {Array<object>}
 */
const mergeSavedParts = (current, saved) => {
  const pending = new Map()
  for (const part of saved) {
    if (part.disabled) continue
    const queue = pending.get(part.part_name) || []
    queue.push(part)
    pending.set(part.part_name, queue)
  }
  return current.map((part) => {
    const match = (pending.get(part.part_name) || []).shift()
    if (!match) return part
    return { ...part, name: match.name, variables: match.variables || part.variables }
  })
}

const convertBlobToDataUrl = (blob) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })

const loadImage = (src) =>
  new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = src
  })

const dataUrlFromImage = async (src) => {
  const response = await fetch(src)
  if (!response.ok) throw new Error(`Unable to load image ${response.status}`)
  const blob = await response.blob()
  const sourceURL = await convertBlobToDataUrl(blob)
  const image = await loadImage(sourceURL)
  const canvas = document.createElement("canvas")
  canvas.width = image.naturalWidth || image.width
  canvas.height = image.naturalHeight || image.height
  canvas.getContext("2d").drawImage(image, 0, 0)
  const mimeType = blob.type === "image/png" ? "image/png" : "image/jpeg"
  return {
    dataURL: canvas.toDataURL(mimeType, 0.92),
    width: canvas.width,
    height: canvas.height,
    mimeType,
  }
}

function DermaBodyTemplateEditor() {
  const [api, setApi] = useState(null)
  const [template, setTemplate] = useState(null)
  const [parts, setParts] = useState([])
  const [retiredParts, setRetiredParts] = useState([])
  const [retiredOpen, setRetiredOpen] = useState(false)
  const [selectedPartId, setSelectedPartId] = useState("")
  const [copyTargetIds, setCopyTargetIds] = useState([])
  const [outlineRefusal, setOutlineRefusal] = useState("")
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const elementToPartRef = useRef({})
  const partToElementRef = useRef({})
  const imageLayoutRef = useRef(null)
  const partsRef = useRef(parts)
  const initialPartsRenderedRef = useRef(false)
  // Element id -> the element version already refused, so an unchanged bad outline is
  // judged once instead of on every onChange.
  const refusedOutlinesRef = useRef({})

  const templateName = new URLSearchParams(window.location.search).get("template")
  const selectedPart = parts.find((part) => part.localId === selectedPartId)

  useEffect(() => {
    partsRef.current = parts
  }, [parts])

  useEffect(() => {
    if (!templateName) {
      setError("Open this designer with ?template=DERMA_BODY_TEMPLATE")
      setLoading(false)
      return
    }
    Promise.all([
      frappe.db.get_doc("Derma Body Template", templateName),
      frappe.call({
        method: "do_derma.api.get_derma_body_template_parts",
        args: { body_template: templateName, include_disabled: 1 },
      }),
    ])
      .then(([doc, response]) => {
        setTemplate(doc)
        const loaded = response.message || []
        setParts(loaded.filter((part) => !part.disabled).map(toEditablePart))
        setRetiredParts(loaded.filter((part) => part.disabled))
      })
      .catch((err) => setError(err?.message || "Unable to load body template."))
      .finally(() => setLoading(false))
  }, [templateName])

  useEffect(() => {
    if (!api || !template?.image) return
    loadTemplateImage(api, template, imageLayoutRef).catch(() => {
      setError("Unable to load template image.")
    })
  }, [api, template?.name])

  const renderPartElements = useCallback(
    (rows) => {
      const layout = imageLayoutRef.current
      if (!api || !layout) return
      const partElements = rows.map((part) => createPartElement(part, layout)).filter(Boolean)
      for (const element of partElements) {
        elementToPartRef.current[element.id] = element.customData.localId
        partToElementRef.current[element.customData.localId] = element.id
      }
      initialPartsRenderedRef.current = true
      if (!partElements.length) return
      api.updateScene({ elements: [...api.getSceneElements(), ...partElements], commitToHistory: true })
    },
    [api]
  )

  useEffect(() => {
    if (!api || !imageLayoutRef.current || initialPartsRenderedRef.current || !parts.length) return
    renderPartElements(parts)
  }, [api, parts.length, renderPartElements])

  useEffect(() => {
    if (!api || !selectedPart) return
    const elementId = partToElementRef.current[selectedPart.localId]
    if (!elementId) return
    api.updateScene({
      elements: api.getSceneElements().map((element) => {
        if (element.id !== elementId) return element
        return {
          ...element,
          strokeColor: selectedPart.color || "#4dabf7",
          backgroundColor: hexToRgba(selectedPart.color || "#4dabf7", selectedPart.opacity),
        }
      }),
      commitToHistory: false,
    })
  }, [api, selectedPart?.color, selectedPart?.opacity])

  const updatePart = (localId, values) => {
    setParts((current) => current.map((part) => (part.localId === localId ? { ...part, ...values } : part)))
  }

  const handleChange = useCallback((elements, appState) => {
    const drawing = new Set(
      [appState.multiElement?.id, appState.newElement?.id, appState.draggingElement?.id, appState.editingLinearElement?.elementId].filter(Boolean)
    )
    const lineElements = elements.filter(
      (element) => element.type === "line" && !element.isDeleted && !elementToPartRef.current[element.id] && !drawing.has(element.id)
    )
    if (!lineElements.length) {
      // Nothing left to judge: the refused stroke was deleted, or a new one is under way.
      setOutlineRefusal("")
      return
    }
    const tolerance = closeTolerance(imageLayoutRef.current)
    lineElements.forEach((element) => {
      const verdict = validateAreaPolygon(element.points, tolerance)
      if (!verdict.isValid) {
        if (refusedOutlinesRef.current[element.id] !== element.version) {
          refusedOutlinesRef.current[element.id] = element.version
          setOutlineRefusal(outlineRefusalMessage(verdict.reason))
        }
        return
      }
      delete refusedOutlinesRef.current[element.id]
      setOutlineRefusal("")
      const localId = generateId()
      elementToPartRef.current[element.id] = localId
      partToElementRef.current[localId] = element.id
      setParts((current) => [
        ...current,
        {
          localId,
          name: null,
          part_name: `Region ${current.length + 1}`,
          shape_json: "",
          color: "#4dabf7",
          opacity: 0.2,
          variables: [],
        },
      ])
      setSelectedPartId(localId)
    })
  }, [])

  const handlePointerDown = useCallback((_activeTool, pointerDownState) => {
    const hit = pointerDownState.hit?.element
    if (hit?.type === "line" && elementToPartRef.current[hit.id]) {
      setSelectedPartId(elementToPartRef.current[hit.id])
    }
  }, [])

  const deletePart = (localId) => {
    const elementId = partToElementRef.current[localId]
    if (elementId && api) {
      api.updateScene({
        elements: api.getSceneElements().map((element) => (element.id === elementId ? { ...element, isDeleted: true } : element)),
        commitToHistory: true,
      })
    }
    delete elementToPartRef.current[elementId]
    delete partToElementRef.current[localId]
    setParts((current) => current.filter((part) => part.localId !== localId))
    setCopyTargetIds((current) => current.filter((id) => id !== localId))
    if (selectedPartId === localId) setSelectedPartId("")
  }

  const toggleCopyTarget = (localId) => {
    setCopyTargetIds((current) => (current.includes(localId) ? current.filter((id) => id !== localId) : [...current, localId]))
  }

  /** Give every ticked area its own copy of this area's variables. Local until Save. */
  const copyVariablesToTargets = (source) => {
    const targetIds = copyTargetIds.filter((localId) => localId !== source.localId)
    if (!targetIds.length) return
    const variables = source.variables || []
    setParts((current) =>
      current.map((part) =>
        targetIds.includes(part.localId)
          ? { ...part, variables: variables.map((variable) => ({ ...variable })) }
          : part
      )
    )
    setCopyTargetIds([])
    frappe.show_alert({ message: __("Variables copied to {0} areas", [targetIds.length]), indicator: "green" })
  }

  const restorePart = (part) => {
    const restored = toEditablePart({ ...part, disabled: 0 })
    setRetiredParts((current) => current.filter((row) => row.name !== part.name))
    setParts((current) => [...current, restored])
    renderPartElements([restored])
    setSelectedPartId(restored.localId)
  }

  const addVariable = (localId) => {
    const part = parts.find((row) => row.localId === localId)
    updatePart(localId, {
      variables: [...(part?.variables || []), { variable_name: "", type: "Data", options: "" }],
    })
  }

  const updateVariable = (localId, index, field, value) => {
    const part = parts.find((row) => row.localId === localId)
    if (!part) return
    updatePart(localId, {
      variables: part.variables.map((variable, variableIndex) => (variableIndex === index ? { ...variable, [field]: value } : variable)),
    })
  }

  const removeVariable = (localId, index) => {
    const part = parts.find((row) => row.localId === localId)
    if (!part) return
    updatePart(localId, { variables: part.variables.filter((_, variableIndex) => variableIndex !== index) })
  }

  const saveParts = async () => {
    if (!api || !imageLayoutRef.current) return
    setSaving(true)
    try {
      const elements = api.getSceneElements()
      const layout = imageLayoutRef.current
      const payload = parts.map((part) => {
        const element = elements.find((row) => row.id === partToElementRef.current[part.localId])
        return {
          name: part.name || undefined,
          part_name: part.part_name,
          shape_json: element?.points ? JSON.stringify(element.points.map(([dx, dy]) => [(element.x + dx - layout.x) / layout.renderedWidth, (element.y + dy - layout.y) / layout.renderedHeight])) : part.shape_json,
          color: part.color,
          opacity: part.opacity,
          variables: (part.variables || []).filter((variable) => variable.variable_name),
        }
      })
      const response = await frappe.call({
        method: "do_derma.api.save_derma_body_template_parts",
        args: { body_template: templateName, parts: JSON.stringify(payload) },
      })
      const saved = response.message || []
      setParts((current) => mergeSavedParts(current, saved))
      setRetiredParts(saved.filter((part) => part.disabled))
      frappe.show_alert({ message: __("Body map regions saved"), indicator: "green" })
    } catch (err) {
      frappe.msgprint({ title: __("Unable to save regions"), message: err?.message || String(err), indicator: "red" })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="derma-map-editor-state">Loading body map designer...</div>
  if (error) return <div className="derma-map-editor-state error">{error}</div>

  return (
    <div className="derma-map-editor" data-test="body-map-designer">
      <main className="derma-map-editor-canvas">
        <Excalidraw
          excalidrawAPI={setApi}
          onChange={handleChange}
          onPointerDown={handlePointerDown}
          UIOptions={{
            canvasActions: {
              saveToActiveFile: false,
              loadScene: false,
              export: false,
              saveAsImage: false,
              toggleTheme: false,
              changeViewBackgroundColor: false,
            },
            tools: { image: false },
          }}
          initialData={{
            elements: [],
            appState: {
              activeTool: { type: "line" },
              currentItemStrokeColor: "#4dabf7",
              currentItemBackgroundColor: "transparent",
              viewBackgroundColor: "#ffffff",
            },
            scrollToContent: true,
          }}
        />
      </main>
      <aside className="derma-map-editor-panel">
        <header>
          <div>
            <strong>{template?.title || template?.name}</strong>
            <small>{[template?.gender, template?.template_type].filter(Boolean).join(" · ")}</small>
          </div>
          <button type="button" className="primary" data-test="save-areas" disabled={saving} onClick={saveParts}>
            {saving ? "Saving..." : "Save Regions"}
          </button>
        </header>
        <p className="editor-hint">Use the line tool to draw closed polygons. Click a region to edit its name, color, opacity, and variables.</p>
        {outlineRefusal && (
          <p className="editor-refusal" data-test="area-outline-refusal" role="alert">
            {outlineRefusal}
          </p>
        )}
        <div className="region-list">
          {parts.map((part) => {
            const copyTargetCount = copyTargetIds.filter((localId) => localId !== part.localId).length
            return (
            <article key={part.localId} data-test="area-row" data-area-name={part.part_name || ""} className={selectedPartId === part.localId ? "active" : ""} onClick={() => setSelectedPartId(part.localId)}>
              <div className="region-row">
                <input
                  type="checkbox"
                  data-test="area-copy-target"
                  title={__("Include this area when copying variables")}
                  checked={copyTargetIds.includes(part.localId)}
                  onClick={(event) => event.stopPropagation()}
                  onChange={() => toggleCopyTarget(part.localId)}
                />
                <span style={{ background: hexToRgba(part.color, part.opacity), borderColor: part.color }} />
                <b>{part.part_name || __("Unnamed Area")}</b>
                <button type="button" title={__("Retire this area")} onClick={(event) => { event.stopPropagation(); deletePart(part.localId) }}>x</button>
              </div>
              {selectedPartId === part.localId && (
                <div className="region-detail" onClick={(event) => event.stopPropagation()}>
                  <label>
                    <span>Region Name</span>
                    <input data-test="area-name" value={part.part_name || ""} onChange={(event) => updatePart(part.localId, { part_name: event.target.value })} />
                  </label>
                  <div className="region-two-col">
                    <label>
                      <span>Color</span>
                      <input type="color" value={part.color || "#4dabf7"} onChange={(event) => updatePart(part.localId, { color: event.target.value })} />
                    </label>
                    <label>
                      <span>Opacity {part.opacity}</span>
                      <input type="range" min="0" max="1" step="0.05" value={part.opacity} onChange={(event) => updatePart(part.localId, { opacity: Number(event.target.value) })} />
                    </label>
                  </div>
                  <div className="region-variables-head">
                    <strong>Variables</strong>
                    <button type="button" data-test="add-area-variable" onClick={() => addVariable(part.localId)}>Add</button>
                  </div>
                  {(part.variables || []).map((variable, index) => (
                    <div className="region-variable" key={`${part.localId}-${index}`}>
                      <input data-test="area-variable-name" placeholder="Variable name" value={variable.variable_name || ""} onChange={(event) => updateVariable(part.localId, index, "variable_name", event.target.value)} />
                      <select value={variable.type || "Data"} onChange={(event) => updateVariable(part.localId, index, "type", event.target.value)}>
                        <option value="Data">Data</option>
                        <option value="Select">Select</option>
                        <option value="Float">Float</option>
                        <option value="Int">Int</option>
                        <option value="Date">Date</option>
                        <option value="Check">Check</option>
                      </select>
                      {variable.type === "Select" && (
                        <textarea placeholder="Options, one per line" value={variable.options || ""} onChange={(event) => updateVariable(part.localId, index, "options", event.target.value)} />
                      )}
                      <button type="button" onClick={() => removeVariable(part.localId, index)}>Remove</button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="copy-variables"
                    data-test="copy-area-variables"
                    disabled={!copyTargetCount}
                    onClick={() => copyVariablesToTargets(part)}
                  >
                    {__("Copy variables to {0} ticked areas", [copyTargetCount])}
                  </button>
                </div>
              )}
            </article>
            )
          })}
          {!parts.length && <div className="editor-empty">No regions yet. Draw a closed polygon on the image.</div>}
        </div>
        {retiredParts.length > 0 && (
          <section className="retired-areas">
            <button type="button" className="retired-areas-toggle" data-test="retired-areas-toggle" onClick={() => setRetiredOpen((open) => !open)}>
              {retiredOpen ? "▾" : "▸"} {__("Retired areas")} ({retiredParts.length})
            </button>
            {retiredOpen && (
              <div className="retired-areas-list">
                {retiredParts.map((part) => (
                  <div className="retired-area" data-test="retired-area" data-area-name={part.part_name || ""} key={part.name}>
                    <b>{part.part_name || __("Unnamed Area")}</b>
                    <button type="button" data-test="restore-area" onClick={() => restorePart(part)}>{__("Restore")}</button>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </aside>
    </div>
  )
}

async function loadTemplateImage(api, template, layoutRef) {
  const image = await dataUrlFromImage(template.image)
  const fileId = `derma-editor-template-${template.name}`
  const appState = api.getAppState()
  const canvasWidth = appState.width || 1000
  const canvasHeight = appState.height || 720
  const scale = Math.min((canvasWidth - 180) / image.width, (canvasHeight - 80) / image.height, 1.1)
  const renderedWidth = image.width * scale
  const renderedHeight = image.height * scale
  const x = (canvasWidth - renderedWidth) / 2
  const y = 32
  layoutRef.current = { x, y, renderedWidth, renderedHeight }
  api.addFiles([{ id: fileId, mimeType: image.mimeType || "image/jpeg", dataURL: image.dataURL, created: Date.now(), lastRetrieved: Date.now() }])
  api.updateScene({
    elements: [
      {
        id: `${fileId}-element`,
        type: "image",
        x,
        y,
        width: renderedWidth,
        height: renderedHeight,
        angle: 0,
        strokeColor: "transparent",
        backgroundColor: "transparent",
        fillStyle: "solid",
        strokeWidth: 0,
        strokeStyle: "solid",
        roughness: 0,
        opacity: 100,
        groupIds: [],
        frameId: null,
        roundness: null,
        seed: 1,
        version: 1,
        versionNonce: Math.floor(Math.random() * 1000000000),
        isDeleted: false,
        boundElements: null,
        updated: Date.now(),
        link: null,
        locked: true,
        status: "pending",
        fileId,
        scale: [1, 1],
        customData: { kind: "derma_template_image" },
      },
    ],
    commitToHistory: true,
  })
  setTimeout(() => api.scrollToContent(api.getSceneElements(), { fitToViewport: true, viewportZoomFactor: 0.86 }), 100)
}

function createPartElement(part, layout) {
  let coords
  try {
    coords = typeof part.shape_json === "string" ? JSON.parse(part.shape_json) : part.shape_json
  } catch {
    return null
  }
  if (!Array.isArray(coords) || coords.length < 3) return null
  const absolute = coords.map(([rx, ry]) => [layout.x + Number(rx) * layout.renderedWidth, layout.y + Number(ry) * layout.renderedHeight])
  const originX = absolute[0][0]
  const originY = absolute[0][1]
  return {
    id: generateId(),
    type: "line",
    x: originX,
    y: originY,
    width: 0,
    height: 0,
    angle: 0,
    strokeColor: part.color || "#4dabf7",
    backgroundColor: hexToRgba(part.color, part.opacity),
    fillStyle: "solid",
    strokeWidth: 2,
    strokeStyle: "solid",
    roughness: 0,
    opacity: 100,
    groupIds: [],
    frameId: null,
    roundness: { type: 2 },
    seed: Math.floor(Math.random() * 1000000),
    version: 1,
    versionNonce: Math.floor(Math.random() * 1000000000),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
    points: absolute.map(([x, y]) => [x - originX, y - originY]),
    lastCommittedPoint: null,
    startBinding: null,
    endBinding: null,
    startArrowhead: null,
    endArrowhead: null,
    customData: { kind: "derma_body_template_part", localId: part.localId },
  }
}

class DermaBodyTemplateEditorPage {
  constructor({ wrapper }) {
    this.$wrapper = $(wrapper)
    this.root = createRoot(this.$wrapper.get(0))
    this.root.render(<DermaBodyTemplateEditor />)
  }
}

frappe.provide("frappe.ui")
frappe.ui.DermaBodyTemplateEditor = DermaBodyTemplateEditorPage
export default DermaBodyTemplateEditorPage

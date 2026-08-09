import React, { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react"
import { createRoot } from "react-dom/client"

const GENERATED_BY_MARKS = "render_chart_marks"

const convertBlobToDataUrl = (blob) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })

function parseAnnotation(annotation) {
  if (!annotation?.json) return null
  try {
    return JSON.parse(annotation.json)
  } catch {
    return null
  }
}

	const EmbeddedExcalidraw = forwardRef(({ initialAnnotation, selectedTemplate, bodyTemplate, procedureVariables, marks, onMarkPlaced, onMarkSelected, onRegionSelected }, ref) => {
	const [api, setApi] = useState(null)
	const [excalidrawModule, setExcalidrawModule] = useState(null)
	const [template, setTemplate] = useState(selectedTemplate || null)
	const [chartTemplate, setChartTemplate] = useState(bodyTemplate || null)
	const latestImported = useRef("")
	const latestTemplateImage = useRef("")
	const loadingTemplateImage = useRef("")
	const templateLoadGeneration = useRef(0)
	const stampSequence = useRef(0)
	const hostRef = useRef(null)
	const chartTemplateRef = useRef(bodyTemplate || null)
	const procedureVariablesRef = useRef(procedureVariables || {})
	const marksRef = useRef(marks || [])
	// Set while a saved annotation is being imported. insertTemplateImage() replaces the whole
	// scene, so it must not run against a canvas that is about to receive - or has just
	// received - a resumed drawing.
	const pendingSceneImport = useRef(initialAnnotation?.name || "")
	const dermaToolRef = useRef("draw")
	const requestedToolRef = useRef("draw")
	const previousDraggingIdRef = useRef(null)

	function applyDermaTool(nextTemplate) {
		const effectiveTemplate = nextTemplate !== undefined ? nextTemplate : template
		const requested = requestedToolRef.current
		const resolved = requested === "mark" && isAreaBehavior(effectiveTemplate) ? "area" : requested
		dermaToolRef.current = resolved
		if (api) setDermaTool(api, resolved, effectiveTemplate)
	}

	useEffect(() => {
		if (!globalThis.process) {
			globalThis.process = { env: { NODE_ENV: "production" } }
		} else if (!globalThis.process.env) {
			globalThis.process.env = { NODE_ENV: "production" }
		} else if (!globalThis.process.env.NODE_ENV) {
			globalThis.process.env.NODE_ENV = "production"
		}
		import("@excalidraw/excalidraw").then(setExcalidrawModule)
	}, [])

	useImperativeHandle(ref, () => ({
		getElements: () => api?.getSceneElements?.() || [],
		exportScene: async (options = {}) => {
			if (!api || !excalidrawModule?.exportToBlob) return null
			const elements = api.getSceneElements()
			const files = normalizeBinaryFiles(api.getFiles())
			if (!elements || !elements.length) {
				return { json_text: JSON.stringify({ elements: [], files: {} }), file_data: "" }
			}
			const extraElements = options.extraElements || []
			const blob = await excalidrawModule.exportToBlob({
        elements: extraElements.length ? [...elements, ...extraElements] : elements,
        appState: {
          ...api.getAppState(),
          exportBackground: true,
          viewBackgroundColor: "#ffffff",
        },
        files,
        mimeType: "image/png",
      })
			return {
        json_text: JSON.stringify({
          ...stripTemplateImagePayload(elements, files),
          derma_template: serializeTemplate(chartTemplate),
        }),
        file_data: await convertBlobToDataUrl(blob),
      }
    },
	    loadAnnotation: (annotation) => {
      const scene = parseAnnotation(annotation)
      if (!scene || !api) return
      loadSceneIntoApi(api, scene, true).then(() => {
        latestImported.current = annotation.name || ""
      })
    },
	    setSelectedTemplate: (nextTemplate) => {
	      setTemplate(nextTemplate)
	      applyDermaTool(nextTemplate)
	    },
		    setBodyTemplate: setChartTemplate,
	    setProcedureVariables: (variables) => {
	      procedureVariablesRef.current = variables || {}
	    },
	    setMarks: (nextMarks) => {
	      marksRef.current = nextMarks || []
	    },
		    loadTemplateImage: async (nextTemplate) => {
	    const target = nextTemplate || chartTemplate
	    if (!api || !target?.image) return
	      const loaded = await loadTemplateIntoCanvas(api, target, latestTemplateImage, loadingTemplateImage, templateLoadGeneration)
	      if (!loaded) return
	      setChartTemplate(target)
	    },
    linkMarkElements: (payload) => linkMarkElements(api, payload),
    selectMark: (markName) => selectMarkElement(api, markName),
    setDermaTool: (tool) => {
      requestedToolRef.current = tool || "select"
      applyDermaTool()
    },
    renderTemplateParts: (parts) => renderTemplateParts(api, parts),
    resetView: () => fitToTemplate(api),
  }))

  useEffect(() => {
    if (!api || !initialAnnotation?.name || latestImported.current === initialAnnotation.name) return
    pendingSceneImport.current = initialAnnotation.name
    const scene = parseAnnotation(initialAnnotation)
    if (!scene) {
      pendingSceneImport.current = ""
      return
    }
    loadSceneIntoApi(api, scene, false).then(() => {
      latestImported.current = initialAnnotation.name
      pendingSceneImport.current = ""
      adoptSceneTemplate(api, latestTemplateImage)
      renderChartMarks(api, marksRef.current)
    })
  }, [api, initialAnnotation?.name])

		async function loadSceneIntoApi(api, scene, commitToHistory) {
		  const hydrated = await hydrateTemplateImageFiles(scene)
      for (const file of Object.values(hydrated.files || {})) {
        api.addFiles([file])
      }
      api.updateScene({
        elements: hydrated.elements || [],
        files: hydrated.files || {},
        commitToHistory,
	      })
	      fitToTemplate(api)
	    }

	useEffect(() => {
		if (!api) return
    applyDermaTool()
  }, [api, template?.name])

		useEffect(() => {
			if (!api || !chartTemplate?.image || pendingSceneImport.current) return
			const signature = templateImageSignature(chartTemplate)
			if (latestTemplateImage.current === signature && getTemplateElement(api)) return
			loadTemplateIntoCanvas(api, chartTemplate, latestTemplateImage, loadingTemplateImage, templateLoadGeneration).then((loaded) => {
				if (!loaded) return
				renderTemplateParts(api, chartTemplate.parts || [])
				renderChartMarks(api, marksRef.current)
			})
		}, [api, chartTemplate?.name, chartTemplate?.image])

	useEffect(() => {
		procedureVariablesRef.current = procedureVariables || {}
	}, [procedureVariables])

	useEffect(() => {
		chartTemplateRef.current = chartTemplate || null
	}, [chartTemplate])

	useEffect(() => {
		marksRef.current = marks || []
		if (!api || pendingSceneImport.current) return
		renderChartMarks(api, marksRef.current)
	}, [api, marks])

	  useEffect(() => {
	    const host = hostRef.current
	    if (!host || !api || !globalThis.ResizeObserver) return
	    let timer = null
	    const observer = new ResizeObserver(() => {
	      clearTimeout(timer)
	      timer = setTimeout(() => {
	        ensureTemplateImage(api, chartTemplateRef.current, latestTemplateImage, loadingTemplateImage, templateLoadGeneration)
	      }, 240)
	    })
	    observer.observe(host)
	    return () => {
	      clearTimeout(timer)
	      observer.disconnect()
	    }
	  }, [api])

	const Excalidraw = excalidrawModule?.Excalidraw

	if (!Excalidraw) {
		return <div className="embedded-excalidraw loading">Loading drawing surface...</div>
	}

	return (
			<div
			  className="embedded-excalidraw"
			  ref={hostRef}
			>
      <Excalidraw
        excalidrawAPI={setApi}
        initialData={{
          appState: {
            viewBackgroundColor: "#ffffff",
            currentItemStrokeColor: "#0f766e",
            currentItemBackgroundColor: "transparent",
            activeTool: { type: "freedraw" },
            zoom: { value: 1 },
          },
        }}
        handleKeyboardGlobally={false}
        gridModeEnabled={false}
        objectsSnapModeEnabled={false}
        zenModeEnabled={false}
        viewModeEnabled={false}
        UIOptions={{ canvasActions: { saveToActiveFile: false } }}
        onPointerDown={(_activeTool, pointerDownState) => {
          const hitElement = pointerDownState?.hit?.element
          if (hitElement?.customData?.derma_history) return
	          const hitMark = hitElement?.customData?.mark_name || hitElement?.customData?.derma_chart_mark
	          if (hitMark) {
	            onMarkSelected?.({ mark: hitMark, elementId: hitElement.id })
	            return
	          }
	          if (!api) return
	          const origin = pointerDownState?.origin || pointerDownState?.lastCoords
	          const hitRegion = origin ? findTemplatePartAtPoint(api, origin.x, origin.y) : null
	          if (hitRegion) {
	            onRegionSelected?.(hitRegion)
	          }
	          if (dermaToolRef.current !== "mark" || !isStampBehavior(template)) return
	          if (pointerDownState?.scrollbars?.isOverEither) return
	          if (!getTemplateElement(api)) {
	            globalThis.frappe?.show_alert?.({ message: "Load a chart image before placing marks", indicator: "orange" })
	            return
	          }
	          if (!origin) return
	          stampSequence.current += 1
		          const stamp = insertProcedureStamp(api, template, origin, stampSequence.current, procedureVariablesRef.current)
		          if (stamp?.elementIds?.length) {
		            onMarkPlaced?.(buildPlacementPayload(api, template, chartTemplate, origin, stamp, procedureVariablesRef.current, hitRegion))
		          }
	        }}
	        onChange={(elements, appState) => {
	          if (dermaToolRef.current === "area") {
	            const draggingId = appState?.draggingElement?.id || appState?.newElement?.id || null
	            const previousId = previousDraggingIdRef.current
	            if (previousId && draggingId !== previousId) {
	              const finished = elements.find((element) => element.id === previousId)
	              if (finished && !finished.isDeleted && !finished.customData?.kind && (finished.width || finished.height)) {
	                tagAreaElement(api, finished, template, procedureVariablesRef.current)
	                onMarkPlaced?.(buildAreaPlacementPayload(api, template, chartTemplate, finished, procedureVariablesRef.current))
	              }
	            }
	            previousDraggingIdRef.current = draggingId
	          }
	        }}
	      />
	    </div>
	  )
	})

export default EmbeddedExcalidraw

function isStampBehavior(template) {
  // createStampElements() already has a complete fallback chain ending in createNumberedDot,
  // so any configured marker_behavior is stampable - no need to keep an allowlist in sync with it.
  return Boolean(String(template?.custom_derma_marker_behavior || "").trim())
}

export function isAreaBehavior(template) {
  // Coverage-style procedures (a laser pass, a scarred/pigmented patch) are drawn as a
  // drag-to-size rectangle over the actual treated region instead of a fixed-size point stamp.
  const behavior = String(template?.custom_derma_marker_behavior || "").toLowerCase()
  return behavior.includes("area") || behavior.includes("hatch") || behavior.includes("five_lines")
}

export function mountEmbeddedExcalidraw(element, props = {}) {
  const root = createRoot(element)
  const bridgeRef = React.createRef()
  root.render(<EmbeddedExcalidraw ref={bridgeRef} {...props} />)
  return {
    getElements: () => bridgeRef.current?.getElements?.() || [],
    exportScene: () => bridgeRef.current?.exportScene?.(),
    loadAnnotation: (annotation) => bridgeRef.current?.loadAnnotation?.(annotation),
    setSelectedTemplate: (template) => bridgeRef.current?.setSelectedTemplate?.(template),
    setBodyTemplate: (template) => bridgeRef.current?.setBodyTemplate?.(template),
    setProcedureVariables: (variables) => bridgeRef.current?.setProcedureVariables?.(variables),
    setMarks: (marks) => bridgeRef.current?.setMarks?.(marks),
    loadTemplateImage: (template) => bridgeRef.current?.loadTemplateImage?.(template),
    linkMarkElements: (payload) => bridgeRef.current?.linkMarkElements?.(payload),
    selectMark: (markName) => bridgeRef.current?.selectMark?.(markName),
    setDermaTool: (tool) => bridgeRef.current?.setDermaTool?.(tool),
    renderTemplateParts: (parts) => bridgeRef.current?.renderTemplateParts?.(parts),
    resetView: () => bridgeRef.current?.resetView?.(),
    unmount: () => root.unmount(),
  }
}

function setDermaTool(api, tool, template) {
  if (!api) return
  const color = template?.custom_derma_marker_color || "#0f766e"
  const typeMap = {
    select: "selection",
    mark: "selection",
    draw: "freedraw",
    area: "rectangle",
    text: "text",
  }
  api.updateScene({
    appState: {
      ...api.getAppState(),
      currentItemStrokeColor: color,
      currentItemBackgroundColor: tool === "area" ? color : "transparent",
      currentItemOpacity: tool === "area" ? 18 : 100,
      activeTool: { type: typeMap[tool] || "selection" },
    },
    commitToHistory: true,
  })
}

function insertProcedureStamp(api, template, origin, sequence, procedureVariables = {}) {
  const behavior = String(template?.custom_derma_marker_behavior || "").toLowerCase()
  const color = template?.custom_derma_marker_color || "#0f766e"
  const groupId = makeId("derma-mark-group")
  const elements = createStampElements({ behavior, color, origin, sequence, groupId, template, procedureVariables })
  if (!elements.length) return null
  api.updateScene({
    elements: [...api.getSceneElements(), ...elements],
    appState: {
      ...api.getAppState(),
      selectedElementIds: Object.fromEntries(elements.map((element) => [element.id, true])),
      activeTool: { type: "selection" },
    },
    commitToHistory: true,
  })
  return { elementIds: elements.map((element) => element.id), groupId }
}

function buildPlacementPayload(api, template, chartTemplate, origin, stamp, procedureVariables = {}, region = null) {
  const bounds = getTemplateBounds(api)
  const xPercent = bounds ? clamp(((origin.x - bounds.x) / bounds.width) * 100, 0, 100) : 50
  const yPercent = bounds ? clamp(((origin.y - bounds.y) / bounds.height) * 100, 0, 100) : 50
  return {
    temp_element_ids: stamp.elementIds,
    temp_group_id: stamp.groupId,
    scene_x: origin.x,
    scene_y: origin.y,
    x_percent: xPercent,
    y_percent: yPercent,
    procedure_template: template?.name,
    category: template?.custom_derma_category,
    marker_behavior: template?.custom_derma_marker_behavior,
    marker_color: template?.custom_derma_marker_color,
    body_template: chartTemplate?.name,
    body_view: chartTemplate?.title,
    body_region: region?.part_name || region?.partName,
    region_label: region?.part_name || region?.partName,
    template_part: region?.name || region?.partId,
    procedure_variables: sanitizeVariables(procedureVariables),
  }
}

function tagAreaElement(api, element, template, procedureVariables = {}) {
  if (!api) return
  const elements = api.getSceneElements().map((sceneElement) => {
    if (sceneElement.id !== element.id) return sceneElement
    return {
      ...sceneElement,
      customData: {
        ...(sceneElement.customData || {}),
        kind: "derma_mark",
        category: template?.custom_derma_category,
        procedure_template: template?.name,
        marker_behavior: template?.custom_derma_marker_behavior,
        marker_color: template?.custom_derma_marker_color,
        procedure_variables: sanitizeVariables(procedureVariables),
      },
    }
  })
  api.updateScene({ elements, commitToHistory: true })
}

function buildAreaPlacementPayload(api, template, chartTemplate, element, procedureVariables = {}) {
  const bounds = getTemplateBounds(api)
  const centerX = element.x + (element.width || 0) / 2
  const centerY = element.y + (element.height || 0) / 2
  const xPercent = bounds ? clamp(((centerX - bounds.x) / bounds.width) * 100, 0, 100) : 50
  const yPercent = bounds ? clamp(((centerY - bounds.y) / bounds.height) * 100, 0, 100) : 50
  return {
    temp_element_ids: [element.id],
    scene_x: centerX,
    scene_y: centerY,
    x_percent: xPercent,
    y_percent: yPercent,
    procedure_template: template?.name,
    category: template?.custom_derma_category,
    marker_behavior: template?.custom_derma_marker_behavior,
    marker_color: template?.custom_derma_marker_color,
    body_template: chartTemplate?.name,
    body_view: chartTemplate?.title,
    procedure_variables: sanitizeVariables(procedureVariables),
  }
}

function linkMarkElements(api, payload = {}) {
  if (!api || !payload?.mark?.name) return
  const elementIds = new Set(payload.elementIds || payload.temp_element_ids || [])
  const mark = payload.mark
  const elements = api.getSceneElements().map((element) => {
    if (!elementIds.has(element.id)) return element
    return {
      ...element,
      customData: {
        ...(element.customData || {}),
        kind: "derma_mark",
        mark_name: mark.name,
        derma_chart_mark: mark.name,
        sequence: mark.sequence,
        clinical_procedure: mark.clinical_procedure,
      },
    }
  })
  api.updateScene({
    elements,
    appState: {
      ...api.getAppState(),
      selectedElementIds: Object.fromEntries([...elementIds].map((id) => [id, true])),
    },
    commitToHistory: true,
  })
  api.refresh?.()
}

function selectMarkElement(api, markName) {
  if (!api || !markName) return
  const ids = api
    .getSceneElements()
    .filter((element) => element.customData?.mark_name === markName || element.customData?.derma_chart_mark === markName)
    .map((element) => element.id)
  if (!ids.length) return
  api.updateScene({
    appState: {
      ...api.getAppState(),
      selectedElementIds: Object.fromEntries(ids.map((id) => [id, true])),
    },
    commitToHistory: false,
  })
}

function renderChartMarks(api, marks = []) {
  if (!api) return
  const bounds = getTemplateBounds(api)
  if (!bounds) return
  // Own only what this function drew. Testing "is a mark" instead would swallow the
  // practitioner's own dragged area rectangles and freehand strokes, which carry the same
  // kind/mark_name once tagged, and replace them with a synthetic stamp at their centroid.
  const existing = api.getSceneElements().filter((element) => element.customData?.generated_by !== GENERATED_BY_MARKS)
  const alreadyDrawn = new Set(existing.map((element) => element.customData?.mark_name).filter(Boolean))
  const rendered = []
  for (const mark of marks || []) {
    if (!mark?.name || alreadyDrawn.has(mark.name)) continue
    if (mark.body_template && mark.body_template !== getTemplateElement(api)?.customData?.template?.name) continue
    const isHistory = Boolean(mark._history)
    const origin = {
      x: bounds.x + (Number(mark.x_percent || 0) / 100) * bounds.width,
      y: bounds.y + (Number(mark.y_percent || 0) / 100) * bounds.height,
    }
    const template = {
      name: mark.procedure_template,
      custom_derma_category: mark.category,
      custom_derma_marker_behavior: mark.marker_behavior,
      custom_derma_marker_color: isHistory ? "#64748b" : mark.marker_color,
    }
    const groupId = `derma-mark-${mark.name}`
    const procedureVariables = variablesFromMark(mark)
    const elements = createStampElements({
      behavior: String(mark.marker_behavior || "").toLowerCase(),
      color: isHistory ? "#64748b" : mark.marker_color || "#0f766e",
      origin,
      sequence: mark.sequence || "",
      groupId,
      template,
      procedureVariables,
    }).map((element) => ({
      ...element,
      id: `${element.id}-${mark.name}`,
      opacity: isHistory ? Math.min(element.opacity || 100, 34) : element.opacity,
      locked: isHistory ? true : element.locked,
      customData: {
        ...(element.customData || {}),
        generated_by: GENERATED_BY_MARKS,
        mark_name: isHistory ? `history:${mark.name}` : mark.name,
        derma_chart_mark: isHistory ? `history:${mark.name}` : mark.name,
        derma_history: isHistory,
        source_mark_name: isHistory ? mark.name : undefined,
        sequence: mark.sequence,
        clinical_procedure: mark.clinical_procedure,
      },
    }))
    rendered.push(...elements)
  }
  api.updateScene({ elements: [...existing, ...rendered], commitToHistory: false })
	  api.refresh?.()
	}

function renderTemplateParts(api, parts = []) {
  if (!api) return
  const bounds = getTemplateBounds(api)
  const existing = api
    .getSceneElements()
    .filter((element) => element.customData?.kind !== "derma_template_part")
  if (!bounds || !Array.isArray(parts) || !parts.length) {
    api.updateScene({ elements: existing, commitToHistory: false })
    return
  }
  const partElements = createTemplatePartElements(parts, bounds)
  api.updateScene({ elements: [...existing, ...partElements], commitToHistory: false })
  api.refresh?.()
}

function createTemplatePartElements(parts = [], bounds) {
  return parts
    .map((part, index) => {
      const points = parsePartPoints(part.shape_json)
      if (!points || points.length < 3) return null
      const firstX = bounds.x + points[0][0] * bounds.width
      const firstY = bounds.y + points[0][1] * bounds.height
      const relativePoints = points.map(([x, y]) => [bounds.x + x * bounds.width - firstX, bounds.y + y * bounds.height - firstY])
      if (!samePoint(relativePoints[0], relativePoints[relativePoints.length - 1])) {
        relativePoints.push([0, 0])
      }
      const color = part.color || "#4dabf7"
      return {
        id: `derma-part-${part.name || index}`,
        type: "line",
        x: firstX,
        y: firstY,
        width: Math.max(...relativePoints.map((point) => point[0])) - Math.min(...relativePoints.map((point) => point[0])),
        height: Math.max(...relativePoints.map((point) => point[1])) - Math.min(...relativePoints.map((point) => point[1])),
        angle: 0,
        strokeColor: withAlpha(color, 0.76),
        backgroundColor: withAlpha(color, Number(part.opacity || 0.14)),
        fillStyle: "solid",
        strokeWidth: 1,
        strokeStyle: "dashed",
        roughness: 0,
        opacity: 100,
        groupIds: [],
        frameId: null,
        roundness: null,
        seed: Math.floor(Math.random() * 1000000),
        version: 1,
        versionNonce: Math.floor(Math.random() * 1000000000),
        isDeleted: false,
        boundElements: null,
        updated: Date.now(),
        link: null,
        locked: true,
        points: relativePoints,
        lastCommittedPoint: null,
        startBinding: null,
        endBinding: null,
        startArrowhead: null,
        endArrowhead: null,
        customData: {
          kind: "derma_template_part",
          name: part.name,
          partId: part.name,
          part_name: part.part_name,
          partName: part.part_name,
          source: part.source,
          variables: part.variables || [],
        },
      }
    })
    .filter(Boolean)
}

function findTemplatePartAtPoint(api, sceneX, sceneY) {
  const elements = api?.getSceneElements?.() || []
  for (let i = elements.length - 1; i >= 0; i--) {
    const element = elements[i]
    if (element.isDeleted || element.customData?.kind !== "derma_template_part") continue
    if (pointInLinePolygon(element, sceneX, sceneY)) return element.customData
  }
  return null
}

function pointInLinePolygon(element, sceneX, sceneY) {
  const points = element.points || []
  if (points.length < 3) return false
  const localX = sceneX - element.x
  const localY = sceneY - element.y
  let inside = false
  for (let index = 0, previous = points.length - 1; index < points.length; previous = index++) {
    const [ax, ay] = points[index]
    const [bx, by] = points[previous]
    if ((ay > localY) !== (by > localY) && localX < ((bx - ax) * (localY - ay)) / (by - ay) + ax) {
      inside = !inside
    }
  }
  return inside
}

function parsePartPoints(value) {
  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value
    if (!Array.isArray(parsed)) return null
    return parsed
      .map((point) => [Number(point?.[0]), Number(point?.[1])])
      .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
  } catch {
    return null
  }
}

function samePoint(a, b) {
  return Boolean(a && b && Math.abs(a[0] - b[0]) < 0.0001 && Math.abs(a[1] - b[1]) < 0.0001)
}

function withAlpha(color, opacity = 1) {
  const hex = String(color || "#4dabf7").replace("#", "")
  if (hex.length !== 6) return color
  const alpha = Math.round(Math.min(1, Math.max(0, opacity)) * 255).toString(16).padStart(2, "0")
  return `#${hex}${alpha}`
}

function createStampElements({ behavior, color, origin, sequence, groupId, template, procedureVariables }) {
  const preset = createPresetElements(template, origin, color, groupId, procedureVariables)
  if (preset.length) return preset
  if (behavior.includes("x")) return createXMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("target")) return createTargetMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("hatch") || behavior.includes("five_lines")) return createHatchMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("area")) return createAreaMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("triangle")) return createTriangleCluster(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("finding_dot") || behavior.includes("three_dots")) return createDotCluster(origin, color, groupId, template, procedureVariables)
  return createNumberedDot(origin, color, groupId, template, sequence, procedureVariables)
}

function createPresetElements(template, origin, color, groupId, procedureVariables) {
  if (!template?.custom_derma_marker_preset_json) return []
  try {
    const preset = JSON.parse(template.custom_derma_marker_preset_json)
    const elements = Array.isArray(preset) ? preset : preset.elements || []
    return elements.map((element) => ({
      ...element,
      ...baseElement(
        element.type || "ellipse",
        origin.x + Number(element.x || 0),
        origin.y + Number(element.y || 0),
        Number(element.width || 12),
        Number(element.height || 12),
        element.strokeColor || color,
        groupId,
        template,
        procedureVariables,
        element
      ),
      id: makeId(`derma-${element.type || "preset"}`),
      groupIds: [groupId],
      customData: {
        ...(element.customData || {}),
        kind: "derma_mark",
        category: template?.custom_derma_category,
        procedure_template: template?.name,
        marker_behavior: template?.custom_derma_marker_behavior,
        procedure_variables: sanitizeVariables(procedureVariables),
      },
    }))
  } catch {
    return []
  }
}

function createNumberedDot(origin, color, groupId, template, sequence, procedureVariables) {
  const dot = ellipseElement(origin.x - 8, origin.y - 8, 16, 16, color, groupId, template, procedureVariables, { backgroundColor: color })
  const label = textElement(origin.x - 4, origin.y - 7, String(sequence), "#ffffff", groupId, template, procedureVariables)
  return [dot, label]
}

function createDotCluster(origin, color, groupId, template, procedureVariables) {
  const offsets = [[0, -12], [-12, 8], [12, 8]]
  return offsets.map(([x, y]) => ellipseElement(origin.x + x - 5, origin.y + y - 5, 10, 10, color, groupId, template, procedureVariables, { backgroundColor: color }))
}

function createTriangleCluster(origin, color, groupId, template, procedureVariables) {
  const offsets = [[0, -14], [-14, 10], [14, 10]]
  return offsets.flatMap(([x, y]) => triangleElements(origin.x + x, origin.y + y, 16, color, groupId, template, procedureVariables))
}

function createHatchMark(origin, color, groupId, template, procedureVariables) {
  return [-20, -10, 0, 10, 20].map((offset) =>
    lineElement(origin.x - 36, origin.y + offset + 18, origin.x + 36, origin.y + offset - 18, color, groupId, template, procedureVariables, 3)
  )
}

function createXMark(origin, color, groupId, template, procedureVariables) {
  return [
    lineElement(origin.x - 18, origin.y - 18, origin.x + 18, origin.y + 18, color, groupId, template, procedureVariables, 3),
    lineElement(origin.x + 18, origin.y - 18, origin.x - 18, origin.y + 18, color, groupId, template, procedureVariables, 3),
  ]
}

function createTargetMark(origin, color, groupId, template, procedureVariables) {
  return [
    ellipseElement(origin.x - 18, origin.y - 18, 36, 36, color, groupId, template, procedureVariables),
    ellipseElement(origin.x - 7, origin.y - 7, 14, 14, color, groupId, template, procedureVariables, { backgroundColor: color }),
    lineElement(origin.x - 26, origin.y, origin.x + 26, origin.y, color, groupId, template, procedureVariables, 2),
    lineElement(origin.x, origin.y - 26, origin.x, origin.y + 26, color, groupId, template, procedureVariables, 2),
  ]
}

function createAreaMark(origin, color, groupId, template, procedureVariables) {
  return [
    rectangleElement(origin.x - 40, origin.y - 28, 80, 56, color, groupId, template, procedureVariables, {
      backgroundColor: color,
      opacity: 18,
    }),
  ]
}

function triangleElements(x, y, size, color, groupId, template, procedureVariables) {
  const half = size / 2
  const height = size * 0.9
  return [
    lineElement(x, y - height / 2, x - half, y + height / 2, color, groupId, template, procedureVariables, 3),
    lineElement(x - half, y + height / 2, x + half, y + height / 2, color, groupId, template, procedureVariables, 3),
    lineElement(x + half, y + height / 2, x, y - height / 2, color, groupId, template, procedureVariables, 3),
  ]
}

function rectangleElement(x, y, width, height, color, groupId, template, procedureVariables = {}, overrides = {}) {
  return baseElement("rectangle", x, y, width, height, color, groupId, template, procedureVariables, overrides)
}

function ellipseElement(x, y, width, height, color, groupId, template, procedureVariables = {}, overrides = {}) {
  return baseElement("ellipse", x, y, width, height, color, groupId, template, procedureVariables, overrides)
}

function textElement(x, y, text, color, groupId, template, procedureVariables = {}) {
  return {
    ...baseElement("text", x, y, Math.max(8, text.length * 8), 14, color, groupId, template, procedureVariables, {
      strokeColor: color,
      backgroundColor: "transparent",
    }),
    text,
    originalText: text,
    fontSize: 12,
    fontFamily: 1,
    textAlign: "center",
    verticalAlign: "middle",
    baseline: 11,
    lineHeight: 1.25,
    containerId: null,
  }
}

function lineElement(x1, y1, x2, y2, color, groupId, template, procedureVariables = {}, strokeWidth = 2) {
  const x = Math.min(x1, x2)
  const y = Math.min(y1, y2)
  return {
    ...baseElement("line", x, y, Math.abs(x2 - x1), Math.abs(y2 - y1), color, groupId, template, procedureVariables, {
      strokeWidth,
    }),
    points: [
      [x1 - x, y1 - y],
      [x2 - x, y2 - y],
    ],
    lastCommittedPoint: null,
    startBinding: null,
    endBinding: null,
    startArrowhead: null,
    endArrowhead: null,
  }
}

function baseElement(type, x, y, width, height, color, groupId, template, procedureVariables = {}, overrides = {}) {
  return {
    id: makeId(`derma-${type}`),
    type,
    x,
    y,
    width,
    height,
    angle: 0,
    strokeColor: overrides.strokeColor || color,
    backgroundColor: overrides.backgroundColor || "transparent",
    fillStyle: "solid",
    strokeWidth: overrides.strokeWidth || 2,
    strokeStyle: "solid",
    roughness: 0,
    opacity: overrides.opacity ?? 100,
    groupIds: [groupId],
    frameId: null,
    roundness: null,
    seed: Math.floor(Math.random() * 1000000),
    version: 1,
    versionNonce: Math.floor(Math.random() * 1000000000),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
    customData: {
      kind: "derma_mark",
      category: template?.custom_derma_category,
      procedure_template: template?.name,
      marker_behavior: template?.custom_derma_marker_behavior,
      marker_color: color,
      procedure_variables: sanitizeVariables(procedureVariables),
    },
  }
}

function sanitizeVariables(variables = {}) {
  return Object.fromEntries(Object.entries(variables || {}).filter(([, value]) => value !== undefined && value !== null && value !== ""))
}

function variablesFromMark(mark = {}) {
  return sanitizeVariables({
    product_name: mark.product_name,
    dose: mark.dose,
    dose_unit: mark.dose_unit,
    lot_no: mark.lot_no,
    plane: mark.plane,
    technique: mark.technique,
    device: mark.device,
    settings: mark.settings,
    passes: mark.passes,
    lesion_id: mark.lesion_id,
    diagnosis: mark.diagnosis,
    severity: mark.severity,
    status: mark.status,
  })
}

function getTemplateElement(api) {
  return api?.getSceneElements?.().find((element) => element.customData?.kind === "derma_template")
}

function adoptSceneTemplate(api, latestTemplateImageRef) {
	const signature = getTemplateElement(api)?.customData?.signature
	if (signature) latestTemplateImageRef.current = signature
}

function getTemplateBounds(api) {
  const template = getTemplateElement(api)
  if (!template) return null
  return {
    x: template.x || 0,
    y: template.y || 0,
    width: template.width || 1,
    height: template.height || 1,
  }
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function makeId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`
}

function templateImageSignature(template) {
  return [template?.name, template?.image, template?.view_key].filter(Boolean).join("|")
}

async function loadTemplateIntoCanvas(api, template, latestTemplateImageRef, loadingTemplateImageRef, templateLoadGenerationRef) {
  if (!api || !template?.image) return false
  const signature = templateImageSignature(template)
  if (loadingTemplateImageRef.current === signature) return false
  loadingTemplateImageRef.current = signature
  const generation = (templateLoadGenerationRef.current || 0) + 1
  templateLoadGenerationRef.current = generation
  try {
    const loaded = await insertTemplateImage(api, template, { generation, templateLoadGenerationRef })
    if (!loaded) return false
    latestTemplateImageRef.current = signature
    return true
  } finally {
    if (loadingTemplateImageRef.current === signature) loadingTemplateImageRef.current = ""
  }
}

async function insertTemplateImage(api, template, guard = {}) {
  const signature = templateImageSignature(template)
  const { dataURL, width: naturalWidth, height: naturalHeight, mimeType } = await imageUrlToRenderableData(template.image)
  if (isStaleTemplateLoad(guard)) return false
  const key = String(template.name || template.view_key || Date.now()).replace(/[^a-zA-Z0-9_-]+/g, "-")
  const fileId = `derma-template-${key}`
  const imageFile = {
    id: fileId,
    mimeType,
    dataURL,
    created: Date.now(),
    lastRetrieved: Date.now(),
  }
  api.addFiles([imageFile])

  const appState = api.getAppState()
  if (isStaleTemplateLoad(guard)) return false
  const canvasWidth = appState.width || 900
  const canvasHeight = appState.height || 620
  const fit = getTemplateFitBounds(template, canvasWidth, canvasHeight)
  const scale = Math.min(fit.maxWidth / naturalWidth, fit.maxHeight / naturalHeight, 1.05)
  const width = naturalWidth * scale
  const height = naturalHeight * scale
  const x = fit.x + fit.width / 2 - width / 2
  const y = fit.y + fit.height / 2 - height / 2
  const existing = []
  const imageElement = {
    id: `${fileId}-element`,
    type: "image",
    x,
    y,
    width,
    height,
    angle: 0,
    strokeColor: "transparent",
    backgroundColor: "transparent",
    fillStyle: "solid",
    strokeWidth: 1,
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
    dataURL,
    status: "saved",
    fileId,
    scale: [1, 1],
    customData: {
      kind: "derma_template",
      template: serializeTemplate(template),
      signature,
    },
  }
  if (isStaleTemplateLoad(guard)) return false
  api.updateScene({
    elements: [imageElement, ...existing],
    commitToHistory: true,
  })
  fitToTemplate(api)
  api.refresh?.()
  return true
}

function isStaleTemplateLoad(guard = {}) {
  return Boolean(guard.templateLoadGenerationRef && guard.generation !== guard.templateLoadGenerationRef.current)
}

function ensureTemplateImage(api, template, latestTemplateImageRef, loadingTemplateImageRef, templateLoadGenerationRef) {
  if (!api || !template?.image) return
  const signature = templateImageSignature(template)
  if (loadingTemplateImageRef.current === signature) return
  const templateElement = getTemplateElement(api)
  const files = normalizeBinaryFiles(api.getFiles?.())
  const hasRenderableImage = templateElement?.fileId &&
    files[templateElement.fileId]?.dataURL &&
    templateElement.status === "saved" &&
    templateElement.customData?.signature === signature
  if (hasRenderableImage) return
  loadTemplateIntoCanvas(api, template, latestTemplateImageRef, loadingTemplateImageRef, templateLoadGenerationRef)
}

async function hydrateTemplateImageFiles(scene) {
  const elements = scene.elements || []
  const files = normalizeBinaryFiles(scene.files)
  const hydratedFiles = { ...files }
  const elementDataUrls = {}

  for (const element of elements) {
    if (element.type !== "image" || !element.fileId) continue
    if (hydratedFiles[element.fileId]?.dataURL) {
      elementDataUrls[element.fileId] = hydratedFiles[element.fileId].dataURL
      continue
    }
    // Only the body template may fall back to the scene-level template. A user-inserted photo
    // that lost its file entry must render as Excalidraw's placeholder, not as the silhouette -
    // a visibly missing image is safer than a confidently wrong one.
    const isTemplateImage = element.customData?.kind === "derma_template"
    const template = element.customData?.template || (isTemplateImage ? scene.derma_template : null)
    if (!template?.image) continue
    try {
      const { dataURL, mimeType } = await imageUrlToRenderableData(template.image)
      elementDataUrls[element.fileId] = dataURL
      hydratedFiles[element.fileId] = {
        id: element.fileId,
        mimeType,
        dataURL,
        created: Date.now(),
        lastRetrieved: Date.now(),
      }
    } catch {
      // Keep the element in place; Excalidraw will show its placeholder if the image URL is unavailable.
    }
  }

  return {
    ...scene,
    elements: elements.map((element) => {
      if (element.type !== "image" || !element.fileId || !elementDataUrls[element.fileId]) return element
      return {
        ...element,
        dataURL: element.dataURL || elementDataUrls[element.fileId],
        status: "saved",
      }
    }),
    files: hydratedFiles,
  }
}

function getTemplateFitBounds(template, canvasWidth, canvasHeight) {
  const type = String(template?.template_type || template?.title || "").toLowerCase()
  const isBody = type.includes("body")
  const isFace = type.includes("face")
  const isHands = type.includes("hand")
  const topSafeArea = canvasHeight < 520 ? 58 : 76
  const bottomSafeArea = canvasHeight < 520 ? 26 : 38
  const horizontalSafeArea = canvasWidth < 820 ? 30 : 72
  const availableWidth = Math.max(180, canvasWidth - horizontalSafeArea * 2)
  const availableHeight = Math.max(160, canvasHeight - topSafeArea - bottomSafeArea)
  const widthRatio = isBody ? 0.48 : isHands ? 0.60 : isFace ? 0.56 : 0.58
  const heightRatio = isBody ? 0.94 : isHands ? 0.82 : isFace ? 0.82 : 0.84

  return {
    x: horizontalSafeArea,
    y: topSafeArea,
    width: availableWidth,
    height: availableHeight,
    maxWidth: Math.max(140, Math.min(availableWidth, canvasWidth * widthRatio)),
    maxHeight: Math.max(140, Math.min(availableHeight, canvasHeight * heightRatio)),
  }
}

function normalizeBinaryFiles(files) {
  if (!files) return {}
  if (Array.isArray(files)) {
    return Object.fromEntries(files.filter((file) => file?.id).map((file) => [file.id, normalizeBinaryFile(file)]))
  }
  return Object.fromEntries(Object.entries(files).map(([id, file]) => [id, normalizeBinaryFile({ id, ...file })]))
}

function normalizeBinaryFile(file) {
  return {
    ...file,
    id: file.id,
    created: file.created || Date.now(),
    lastRetrieved: file.lastRetrieved || Date.now(),
  }
}

/**
 * Drop the body template's base64 payload from what gets persisted. hydrateTemplateImageFiles()
 * rebuilds it on load from the template's own URL, so the ~35 KB average it costs per annotation
 * buys nothing.
 *
 * Keyed strictly on the template element, never on "is an image": a photo the practitioner
 * inserted has no URL to rebuild from, so stripping it would destroy it. And the template
 * *element* must survive - _sync_chart_marks_for_annotation returns early without it, which
 * would silently stop every mark in the session being linked back to the annotation.
 */
function stripTemplateImagePayload(elements, files) {
  const templateFileIds = new Set(
    elements
      .filter((element) => element.customData?.kind === "derma_template" && element.fileId)
      .map((element) => element.fileId)
  )
  return {
    elements: elements.map((element) =>
      templateFileIds.has(element.fileId) ? { ...element, dataURL: undefined } : element
    ),
    files: Object.fromEntries(Object.entries(files).filter(([fileId]) => !templateFileIds.has(fileId))),
  }
}

function fitToTemplate(api) {
  if (!api) return
  const templateElement = getTemplateElement(api)
  const visibleElements = templateElement && !templateElement.isDeleted
    ? [templateElement]
    : api.getSceneElements().filter((element) => !element.isDeleted)
  if (!visibleElements.length) return
  api.scrollToContent(visibleElements, { fitToViewport: true, viewportZoomFactor: 0.72 })
}

async function imageUrlToRenderableData(url) {
  if (String(url || "").startsWith("data:")) {
    const image = await loadImage(url)
    const mimeType = mimeTypeFromDataUrl(url)
    return {
      dataURL: url,
      width: image.naturalWidth || image.width || 900,
      height: image.naturalHeight || image.height || 620,
      mimeType: mimeType === "image/jpeg" || mimeType === "image/png" ? mimeType : "image/png",
    }
  }
  const response = await fetch(url)
  const blob = await response.blob()
  const sourceURL = await convertBlobToDataUrl(blob)
  const image = await loadImage(sourceURL)
  const canvas = document.createElement("canvas")
  canvas.width = image.naturalWidth || image.width
  canvas.height = image.naturalHeight || image.height
  const context = canvas.getContext("2d")
  context.drawImage(image, 0, 0)
  const mimeType = blob.type && blob.type !== "image/svg+xml" ? blob.type : "image/jpeg"
  return {
    dataURL: canvas.toDataURL(mimeType === "image/png" ? "image/png" : "image/jpeg", 0.92),
    width: canvas.width,
    height: canvas.height,
    mimeType: mimeType === "image/png" ? "image/png" : "image/jpeg",
  }
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = src
  })
}

function mimeTypeFromDataUrl(dataURL) {
  const match = String(dataURL || "").match(/^data:([^;]+);/)
  return match?.[1] || "image/png"
}

function serializeTemplate(template) {
  if (!template) return null
  return {
    name: template.name,
    title: template.title,
    template_type: template.template_type,
    view_key: template.view_key,
	    image: template.image,
	    annotation_template: template.annotation_template,
	    parts: template.parts || [],
	  }
	}

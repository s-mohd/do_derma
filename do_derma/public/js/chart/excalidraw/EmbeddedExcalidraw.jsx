import React, { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react"
import { createRoot } from "react-dom/client"

const GENERATED_BY_MARKS = "render_chart_marks"
const MIN_DRAWN_MARK_SIZE = 6
export const BADGE_KIND = "derma_badge"
export const TEMPLATE_PART_KIND = "derma_template_part"
const FIT_RETRY_LIMIT = 3
const TEMPLATE_MEASURE_RETRY_LIMIT = 30

/**
 * Everything by which a drawing could enter or leave the app outside do_derma's own Save and
 * Print is off: loadScene would drop an arbitrary .excalidraw file onto a patient's chart, and
 * the export actions write patient imagery outside any audit path. Drawing tools, zoom and
 * undo/redo are untouched. The Library button is separate - renderTopRightUI displaces it.
 */
const CLINICAL_UI_OPTIONS = {
  canvasActions: {
    changeViewBackgroundColor: false,
    clearCanvas: false,
    export: false,
    loadScene: false,
    saveAsImage: false,
    saveToActiveFile: false,
    toggleTheme: false,
  },
}

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

	const EmbeddedExcalidraw = forwardRef(({ initialAnnotation, selectedTemplate, bodyTemplate, procedureVariables, marks, onMarkPlaced, onMarkSelected, onRegionSelected, onSceneChanged, onSceneReady, onTemplateLoadFailed }, ref) => {
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
	// Badge elements are pushed back into the scene, which re-fires onChange. Without a
	// signature to compare against, that is an endless updateScene loop.
	const badgeSignature = useRef("")
	const markLayerRef = useRef("")
	const selectedMarkRef = useRef("")
	const dermaToolRef = useRef("draw")
	const requestedToolRef = useRef("draw")
	const previousDraggingIdRef = useRef(null)
	// Selection / filled-values / hidden state for the template-part layer, kept in a
	// ref so a template reload can re-apply it after re-rendering the polygons.
	const partStateRef = useRef({ hidden: false, selected: "", filled: [] })

	function applyDermaTool(nextTemplate) {
		const effectiveTemplate = nextTemplate !== undefined ? nextTemplate : template
		const requested = requestedToolRef.current
		const resolved = requested === "mark" ? placementToolFor(effectiveTemplate) : requested
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
		exportScene: async () => {
			if (!api || !excalidrawModule?.exportToBlob) return null
			const elements = api.getSceneElements()
			const files = normalizeBinaryFiles(api.getFiles())
			if (!elements || !elements.length) {
				return { json_text: JSON.stringify({ elements: [], files: {} }), file_data: "" }
			}
			// Badges are already in the scene, so the export picks them up once.
			const blob = await excalidrawModule.exportToBlob({
        elements,
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
    renderTemplateParts: (parts) => {
      whenTemplateMeasured(api, Boolean(chartTemplateRef.current?.image)).then(() => {
        renderTemplateParts(api, parts)
        styleTemplateParts(api, partStateRef.current)
      })
    },
    setPartStates: (state) => {
      partStateRef.current = {
        ...partStateRef.current,
        selected: state?.selected || "",
        filled: state?.filled || [],
      }
      styleTemplateParts(api, partStateRef.current)
    },
    setPartsHidden: (hidden) => {
      partStateRef.current = { ...partStateRef.current, hidden: Boolean(hidden) }
      styleTemplateParts(api, partStateRef.current)
    },
    setBadgeElements: (badges) => syncBadgeLayer(api, badges, badgeSignature),
    updateMarkVariables: (payload) => updateMarkVariables(api, payload),
    resetView: () => fitToTemplate(api),
    // Counts outlines the practitioner can see. An area with degenerate bounds is not drawn,
    // and offering "Hide Areas" over it says the canvas holds something it does not.
    getRenderedPartCount: () =>
      (api?.getSceneElements?.() || []).filter(
        (element) =>
          !element.isDeleted &&
          element.customData?.kind === TEMPLATE_PART_KIND &&
          isPositiveSize(element.width) &&
          isPositiveSize(element.height)
      ).length,
  }))

  useEffect(() => {
    if (!api || !initialAnnotation?.name || latestImported.current === initialAnnotation.name) return
    pendingSceneImport.current = initialAnnotation.name
    const scene = parseAnnotation(initialAnnotation)
    if (!scene) {
      pendingSceneImport.current = ""
      return
    }
    loadSceneIntoApi(api, scene, false).then(async () => {
      latestImported.current = initialAnnotation.name
      pendingSceneImport.current = ""
      adoptSceneTemplate(api, latestTemplateImage)
      await rebuildUnrenderableTemplate()
      // Areas are derived from the template and stripped before persisting, so a resumed
      // scene never carries them - render them here or the drawing comes back without any.
      renderTemplateParts(api, chartTemplateRef.current?.parts || [])
      renderChartMarks(api, marksRef.current)
      styleTemplateParts(api, partStateRef.current)
      onSceneReady?.()
    })
  }, [api, initialAnnotation?.name])

	/**
	 * A resumed scene can carry a template element that cannot be painted - no file, and a
	 * template stub with no image URL to rebuild one from. Left alone it is a phantom: the fit
	 * lands on an invisible box, the areas trace it, and the resize-driven reload repairs it
	 * later by replacing the scene. Rebuild it here instead, in place, before anything is
	 * measured against it, and only when the body template on the chart is the same row.
	 */
	async function rebuildUnrenderableTemplate() {
		if (!api || isTemplateRenderable(api)) return
		const template = chartTemplateRef.current
		const sceneTemplateName = getTemplateElement(api)?.customData?.template?.name
		if (!template?.image) return
		if (sceneTemplateName && sceneTemplateName !== template.name) return
		await loadTemplateIntoCanvas(api, template, latestTemplateImage, loadingTemplateImage, templateLoadGeneration)
	}

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
	      await whenTemplateMeasured(api, hasTemplateElement(hydrated.elements))
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
				if (!loaded) {
					onTemplateLoadFailed?.(chartTemplate)
					return
				}
				renderTemplateParts(api, chartTemplate.parts || [])
				styleTemplateParts(api, partStateRef.current)
				renderChartMarks(api, marksRef.current)
				onSceneReady?.()
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
		whenTemplateMeasured(api, Boolean(chartTemplateRef.current?.image)).then(() =>
			renderChartMarks(api, marksRef.current)
		)
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
        UIOptions={CLINICAL_UI_OPTIONS}
        renderTopRightUI={() => null}
        onPointerDown={(_activeTool, pointerDownState) => {
          const hitElement = pointerDownState?.hit?.element
          if (hitElement?.customData?.derma_history) return
	          const hitMark = hitElement?.customData?.mark_name || hitElement?.customData?.derma_chart_mark
	          if (hitMark) {
	            onMarkSelected?.({ mark: hitMark, elementId: hitElement.id, element: hitElement })
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
	          // Excalidraw fires onChange on every appState tick, so signalling unconditionally
	          // would re-render the host, re-render Excalidraw and fire onChange again forever.
	          // Badges derive from the mark layer alone, so that is what is watched.
	          const signature = markLayerSignature(elements)
	          if (signature !== markLayerRef.current) {
	            markLayerRef.current = signature
	            onSceneChanged?.()
	          }
	          // Selecting a mark is Excalidraw's own hit-test, read back from appState. Only while
	          // no placement tool is armed, so the selection insertProcedureStamp makes on the
	          // stamp it just placed does not count as "edit this one".
	          if (dermaToolRef.current === "select") {
	            const selected = selectedMarkElement(elements, appState)
	            const selectedId = selected?.id || ""
	            if (selectedId !== selectedMarkRef.current) {
	              selectedMarkRef.current = selectedId
	              if (selected) {
	                const custom = selected.customData || {}
	                onMarkSelected?.({
	                  mark: custom.mark_name || custom.derma_chart_mark,
	                  elementId: selected.id,
	                  element: selected,
	                })
	              }
	            }
	          }
	          const drawingTool = dermaToolRef.current
	          if (drawingTool === "area" || drawingTool === "draw") {
	            const finished = findCommittedElement(elements, appState, previousDraggingIdRef)
	            if (finished) {
	              tagDrawnElement(api, finished, template, procedureVariablesRef.current, drawingTool)
	              onMarkPlaced?.(buildDrawnPlacementPayload(api, template, chartTemplate, finished, procedureVariablesRef.current, drawingTool))
	            }
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

export function isFreehandBehavior(template) {
  // Irregular regions - a graft, a scar, a patch of melasma - that a rectangle misrepresents.
  // The pen takes the procedure's colour and the finished stroke becomes one Derma Chart Mark.
  const behavior = String(template?.custom_derma_marker_behavior || "").toLowerCase()
  return behavior.includes("freehand") || behavior.includes("stroke") || behavior.includes("paint")
}

/** Which drawing tool a procedure's marker behaviour asks for. */
function placementToolFor(template) {
  if (isAreaBehavior(template)) return "area"
  if (isFreehandBehavior(template)) return "draw"
  return "mark"
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
    getRenderedPartCount: () => bridgeRef.current?.getRenderedPartCount?.() || 0,
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

/**
 * A stroke's true geometry lives in the scene; the mark carries its centroid, because
 * x_percent/y_percent are mandatory on Derma Chart Mark. Same compromise dragged areas
 * already make.
 */
function drawnElementCentre(element, shape) {
  const points = element.points || []
  if (shape !== "freehand" || !points.length) {
    return { x: element.x + (element.width || 0) / 2, y: element.y + (element.height || 0) / 2 }
  }
  return {
    x: element.x + points.reduce((sum, point) => sum + point[0], 0) / points.length,
    y: element.y + points.reduce((sum, point) => sum + point[1], 0) / points.length,
  }
}

/** The element the user just finished drawing, or null while they are still drawing it. */
function findCommittedElement(elements, appState, previousIdRef) {
  const draggingId = appState?.draggingElement?.id || appState?.newElement?.id || null
  const previousId = previousIdRef.current
  previousIdRef.current = draggingId
  if (!previousId || draggingId === previousId) return null
  const finished = elements.find((element) => element.id === previousId)
  if (!finished || finished.isDeleted || finished.customData?.kind) return null
  if (!finished.width && !finished.height) return null
  // A flick of the pen is not a clinical finding.
  if (Math.abs(finished.width || 0) < MIN_DRAWN_MARK_SIZE && Math.abs(finished.height || 0) < MIN_DRAWN_MARK_SIZE) return null
  return finished
}

function tagDrawnElement(api, element, template, procedureVariables = {}, tool = "area") {
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
        shape: tool === "draw" ? "freehand" : "area",
      },
    }
  })
  api.updateScene({ elements, commitToHistory: true })
}

function buildDrawnPlacementPayload(api, template, chartTemplate, element, procedureVariables = {}, tool = "area") {
  const shape = tool === "draw" ? "freehand" : "area"
  const bounds = getTemplateBounds(api)
  const centre = drawnElementCentre(element, shape)
  const centerX = centre.x
  const centerY = centre.y
  const xPercent = bounds ? clamp(((centerX - bounds.x) / bounds.width) * 100, 0, 100) : 50
  const yPercent = bounds ? clamp(((centerY - bounds.y) / bounds.height) * 100, 0, 100) : 50
  const region = findTemplatePartAtPoint(api, centerX, centerY)
  return {
    temp_element_ids: [element.id],
    annotation_json: JSON.stringify({ element_id: element.id, shape }),
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
    // A drawn mark has no click origin, so the area is resolved from where it landed.
    body_region: region?.part_name || region?.partName,
    region_label: region?.part_name || region?.partName,
    template_part: region?.name || region?.partId,
    procedure_variables: sanitizeVariables(procedureVariables),
  }
}

/** Refresh a mark's cached variables on canvas after the mark itself has been updated. */
function updateMarkVariables(api, payload = {}) {
  if (!api || !payload.markName) return
  const elements = api.getSceneElements().map((element) => {
    const custom = element.customData || {}
    if (custom.mark_name !== payload.markName && custom.derma_chart_mark !== payload.markName) return element
    return { ...element, customData: { ...custom, procedure_variables: sanitizeVariables(payload.variables) } }
  })
  api.updateScene({ elements, commitToHistory: false })
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
    .filter((element) => element.customData?.kind !== TEMPLATE_PART_KIND)
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
          kind: TEMPLATE_PART_KIND,
          name: part.name,
          partId: part.name,
          part_name: part.part_name,
          partName: part.part_name,
          source: part.source,
          variables: part.variables || [],
          base_color: color,
          base_opacity: Number(part.opacity || 0.14),
        },
      }
    })
    .filter(Boolean)
}

/**
 * Three-state styling for the part layer: selected (bold solid), holding values
 * (solid tint), empty (faint dashed) - plus a hide-all override. Geometry is
 * spread through untouched so restyling never moves a polygon.
 */
function styleTemplateParts(api, state = {}) {
  if (!api) return
  const filled = new Set(state.filled || [])
  let changed = false
  const elements = api.getSceneElements().map((element) => {
    if (element.isDeleted || element.customData?.kind !== TEMPLATE_PART_KIND) return element
    const partName = element.customData?.part_name || element.customData?.partName || ""
    const baseColor = element.customData?.base_color || "#4dabf7"
    const baseOpacity = Number(element.customData?.base_opacity || 0.14)
    const isSelected = Boolean(partName) && state.selected === partName
    const isFilled = filled.has(partName)
    const next = {
      opacity: state.hidden ? 0 : 100,
      strokeWidth: isSelected ? 3 : isFilled ? 2 : 1,
      strokeStyle: isSelected || isFilled ? "solid" : "dashed",
      strokeColor: withAlpha(baseColor, isSelected ? 1 : 0.76),
      backgroundColor: withAlpha(baseColor, isSelected ? 0.4 : isFilled ? 0.3 : baseOpacity),
    }
    const isSame = Object.entries(next).every(([key, value]) => element[key] === value)
    if (isSame) return element
    changed = true
    return { ...element, ...next, versionNonce: Math.floor(Math.random() * 1000000000) }
  })
  if (!changed) return
  api.updateScene({ elements, commitToHistory: false })
  api.refresh?.()
}

function findTemplatePartAtPoint(api, sceneX, sceneY) {
  const elements = api?.getSceneElements?.() || []
  for (let i = elements.length - 1; i >= 0; i--) {
    const element = elements[i]
    if (element.isDeleted || element.customData?.kind !== TEMPLATE_PART_KIND) continue
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

/**
 * The dot carries no number of its own. The badge layer numbers every mark 1..n and that is the
 * numbering the legend table and the printout quote, so a second number here - drawn from the
 * mark's own `sequence` - printed twice and could disagree with the legend. `sequence` still
 * reaches customData through renderChartMarks, which the fan-out and badge collector read.
 */
function createNumberedDot(origin, color, groupId, template, sequence, procedureVariables) {
  return [ellipseElement(origin.x - 8, origin.y - 8, 16, 16, color, groupId, template, procedureVariables, { backgroundColor: color })]
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

/**
 * Null until the template element is measured. A `|| 1` fallback here used to hand out a 1px
 * template, which draws every area outline degenerate and fits the view onto nothing.
 */
function getTemplateBounds(api) {
  const template = getTemplateElement(api)
  if (!template || template.isDeleted) return null
  if (!isPositiveSize(template.width) || !isPositiveSize(template.height)) return null
  return {
    x: template.x || 0,
    y: template.y || 0,
    width: template.width,
    height: template.height,
  }
}

function isPositiveSize(value) {
  return Number.isFinite(value) && value > 0
}

/** A template element the canvas can actually paint: measured, and holding a loaded image file. */
function isTemplateRenderable(api) {
  const template = getTemplateElement(api)
  if (!template || !getTemplateBounds(api)) return false
  return Boolean(template.fileId && normalizeBinaryFiles(api.getFiles?.())[template.fileId]?.dataURL)
}

/**
 * The scene Excalidraw reports back can lag an updateScene by a frame or more, so the template
 * element is unmeasured for a moment after a resumed drawing lands. Everything positioned
 * against it - the fit, the area outlines, the mark layer - waits here first.
 */
function whenTemplateMeasured(api, expectsTemplate = true) {
  if (!api || !expectsTemplate || getTemplateBounds(api)) return Promise.resolve()
  return new Promise((resolve) => {
    const settle = (attempt) => {
      if (getTemplateBounds(api) || attempt >= TEMPLATE_MEASURE_RETRY_LIMIT) {
        resolve()
        return
      }
      requestAnimationFrame(() => settle(attempt + 1))
    }
    settle(0)
  })
}

function hasTemplateElement(elements = []) {
  return elements.some((element) => element.customData?.kind === "derma_template" && !element.isDeleted)
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
  const previous = getTemplateElement(api)
  const { x, y, width, height } = templateGeometry(api, template, previous, naturalWidth, naturalHeight)
  // Everything already drawn stays. This used to hand updateScene the image alone, so a rebuild
  // of an unrenderable template - which is what the resize watcher asks for - took the
  // practitioner's drawing with it.
  const existing = api
    .getSceneElements()
    .filter((element) => element.customData?.kind !== "derma_template")
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
  await whenTemplateMeasured(api)
  fitToTemplate(api)
  api.refresh?.()
  return true
}

/**
 * Where the template image goes. Rebuilding the same template keeps the box the scene already
 * has: marks and strokes were placed against it, and moving it would slide them off the anatomy.
 * Anything else - a first insert, or a switch to another silhouette - is fitted to the canvas.
 */
function templateGeometry(api, template, previous, naturalWidth, naturalHeight) {
  const isRebuildInPlace =
    previous &&
    isPositiveSize(previous.width) &&
    isPositiveSize(previous.height) &&
    (!previous.customData?.template?.name || previous.customData.template.name === template.name)
  if (isRebuildInPlace) {
    return { x: previous.x || 0, y: previous.y || 0, width: previous.width, height: previous.height }
  }
  const appState = api.getAppState()
  const fit = getTemplateFitBounds(template, appState.width || 900, appState.height || 620)
  const scale = Math.min(fit.maxWidth / naturalWidth, fit.maxHeight / naturalHeight, 1.05)
  const width = naturalWidth * scale
  const height = naturalHeight * scale
  return {
    x: fit.x + fit.width / 2 - width / 2,
    y: fit.y + fit.height / 2 - height / 2,
    width,
    height,
  }
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
/**
 * Swap the badge layer for a freshly numbered one. Badges are ordinary scene elements so they
 * export with the drawing and are visible while working, but they are derived state: never
 * committed to undo history, and stripped from what gets persisted.
 */
/** The single selected element, when it is a mark the practitioner drew or stamped. */
function selectedMarkElement(elements = [], appState = {}) {
  const selectedIds = Object.entries(appState.selectedElementIds || {})
    .filter(([, isSelected]) => isSelected)
    .map(([id]) => id)
  if (selectedIds.length !== 1) return null
  const element = elements.find((candidate) => candidate.id === selectedIds[0])
  if (!element || element.isDeleted || element.customData?.kind !== "derma_mark") return null
  return element.customData?.mark_name || element.customData?.derma_chart_mark ? element : null
}

/** Everything a badge is derived from: which marks exist, where they are, what they carry. */
function markLayerSignature(elements = []) {
  return elements
    .filter((element) => !element.isDeleted && element.customData?.kind === "derma_mark")
    .map((element) => {
      const variables = JSON.stringify(element.customData?.procedure_variables || {})
      return `${element.id}:${Math.round(element.x || 0)}:${Math.round(element.y || 0)}:${variables}`
    })
    .join("|")
}

function syncBadgeLayer(api, badges = [], signatureRef) {
  if (!api) return
  const signature = badges.map((badge) => `${badge.id}:${Math.round(badge.x)}:${Math.round(badge.y)}:${badge.text || ""}`).join("|")
  if (signature === signatureRef.current) return
  signatureRef.current = signature
  const existing = api.getSceneElements().filter((element) => element.customData?.kind !== BADGE_KIND)
  api.updateScene({ elements: [...existing, ...badges], commitToHistory: false })
}

function stripTemplateImagePayload(elements, files) {
  const templateFileIds = new Set(
    elements
      .filter((element) => element.customData?.kind === "derma_template" && element.fileId)
      .map((element) => element.fileId)
  )
  return {
    elements: elements
      .filter((element) => element.customData?.kind !== BADGE_KIND)
      // Area outlines are derived from the body template and re-rendered on every load. Storing
      // them would freeze a drawing against the geometry it was made with, so a later template
      // edit would leave old and new outlines mixed on the next resave.
      .filter((element) => element.customData?.kind !== TEMPLATE_PART_KIND)
      .map((element) => (templateFileIds.has(element.fileId) ? { ...element, dataURL: undefined } : element)),
    files: Object.fromEntries(Object.entries(files).filter(([fileId]) => !templateFileIds.has(fileId))),
  }
}

/**
 * On the first open after a cold page load the canvas can still be unmeasured when this runs,
 * which lands the zoom on NaN and parks the view off content. Retry on the next frame until it
 * has dimensions - bounded, never a loop.
 */
function fitToTemplate(api, attempt = 0) {
  if (!api) return
  const appState = api.getAppState?.() || {}
  if (attempt < FIT_RETRY_LIMIT && (!appState.width || !Number.isFinite(appState.zoom?.value))) {
    requestAnimationFrame(() => fitToTemplate(api, attempt + 1))
    return
  }
  // An unmeasured template is not something to fit onto - fitting to it parks the view on a
  // box nobody can see, which is what a resumed drawing used to open on.
  const templateElement = getTemplateBounds(api) ? getTemplateElement(api) : null
  const visibleElements = templateElement
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

import React, { useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react"
import { createRoot } from "react-dom/client"
import { markerSizeOf, scaledStrokeWidth } from "../../shared/marker_size"
import { convertBlobToDataUrl, imageUrlToRenderableData } from "../../shared/image_data.js"

const GENERATED_BY_MARKS = "render_chart_marks"
const MIN_DRAWN_MARK_SIZE = 6
export const BADGE_KIND = "derma_badge"
export const TEMPLATE_PART_KIND = "derma_template_part"
export const PHOTO_KIND = "derma_photo"
/** Images the scene stores as a URL and repaints on load, rather than carrying their bytes. */
const REBUILDABLE_IMAGE_KINDS = new Set(["derma_template", PHOTO_KIND])
/** A captured photo lands big enough to work on: this share of the visible canvas. */
const PHOTO_VIEWPORT_RATIO = 0.4
/** Each shot of a burst steps off the last, so none of them hides another. */
const PHOTO_CASCADE_OFFSET = 32
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
	const markerSizeRef = useRef(markerSizeOf(null))
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
	const partStateRef = useRef({ hidden: false, selected: [], filled: [] })

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
        elements: exportableElements(elements, partStateRef.current),
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
          ...stripStoredImagePayload(elements, files),
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
	    setMarkerSize: (size) => {
	      markerSizeRef.current = markerSizeOf(size)
	    },
	    resizeMarkElements: (payload) => resizeMarkElements(api, payload),
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
        selected: state?.selected || [],
        filled: state?.filled || [],
      }
      styleTemplateParts(api, partStateRef.current)
    },
    setPartsHidden: (hidden) => {
      partStateRef.current = { ...partStateRef.current, hidden: Boolean(hidden) }
      styleTemplateParts(api, partStateRef.current)
    },
    setBadgeElements: (badges) => syncBadgeLayer(api, badges, badgeSignature),
    insertPhotos: (photos) => insertPhotoElements(api, photos),
    getPhotoNames: () => photoElementNames(api),
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
		  const hydrated = await hydrateSceneImageFiles(scene)
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
	          // Reported on a miss too: bare canvas is how the practitioner closes the area editor.
	          // Only a deliberate click reports it, though - a pen stroke or an eraser drag that
	          // happens to start inside an outline must not change what the saved image shows.
	          const isPlacingMark = requestedToolRef.current === "mark"
	          if (isPlacingMark || api.getAppState?.()?.activeTool?.type === "selection") {
	            onRegionSelected?.(hitRegion, { isPlacingMark })
	          }
	          if (dermaToolRef.current !== "mark" || !isStampBehavior(template)) return
	          if (pointerDownState?.scrollbars?.isOverEither) return
	          if (!getTemplateElement(api)) {
	            globalThis.frappe?.show_alert?.({ message: "Load a chart image before placing marks", indicator: "orange" })
	            return
	          }
	          if (!origin) return
	          stampSequence.current += 1
		          const markerSize = markerSizeRef.current
		          const stamp = insertProcedureStamp(api, template, origin, stampSequence.current, procedureVariablesRef.current, markerSize)
		          if (stamp?.elementIds?.length) {
		            onMarkPlaced?.(
		              buildPlacementPayload(api, template, chartTemplate, origin, stamp, procedureVariablesRef.current, hitRegion, markerSize)
		            )
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
    setMarkerSize: (size) => bridgeRef.current?.setMarkerSize?.(size),
    resizeMarkElements: (payload) => bridgeRef.current?.resizeMarkElements?.(payload),
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
      // Entering select mode drops whatever placement left selected, so the first click
      // on a mark binds the editor to that mark and not to the last stamp placed.
      ...(tool === "select" ? { selectedElementIds: {}, selectedGroupIds: {} } : {}),
    },
    commitToHistory: true,
  })
}

function insertProcedureStamp(api, template, origin, sequence, procedureVariables = {}, size = 1) {
  const behavior = String(template?.custom_derma_marker_behavior || "").toLowerCase()
  const color = template?.custom_derma_marker_color || "#0f766e"
  const groupId = makeId("derma-mark-group")
  const elements = createStampElements({ behavior, color, origin, sequence, groupId, template, procedureVariables, size })
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

function buildPlacementPayload(api, template, chartTemplate, origin, stamp, procedureVariables = {}, region = null, markerSize = 1) {
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
    marker_size: markerSize,
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

function ownsMark(element, markName) {
  const custom = element.customData || {}
  return custom.mark_name === markName || custom.derma_chart_mark === markName
}

/**
 * Redraw one placed mark at a new size. The stamp it replaces carries everything needed to
 * rebuild it - behaviour, colour, variables and the group it belongs to - so the mark keeps
 * its identity and only its geometry changes.
 */
function resizeMarkElements(api, payload = {}) {
  const markName = payload?.markName
  if (!api || !markName) return
  const elements = api.getSceneElements()
  const owned = elements.filter((element) => !element.isDeleted && ownsMark(element, markName))
  if (!owned.length) return
  const custom = owned[0].customData || {}
  const behavior = String(custom.marker_behavior || "").toLowerCase()
  const color = custom.marker_color || "#0f766e"
  const groupId = owned[0].groupIds?.[0] || makeId("derma-mark-group")
  const replacements = createStampElements({
    behavior,
    color,
    origin: stampOrigin(custom, owned),
    sequence: custom.sequence || "",
    groupId,
    template: {
      name: custom.procedure_template,
      custom_derma_category: custom.category,
      custom_derma_marker_behavior: custom.marker_behavior,
      custom_derma_marker_color: color,
    },
    procedureVariables: custom.procedure_variables || {},
    size: payload.size,
  }).map((element) => ({
    ...element,
    locked: owned[0].locked,
    opacity: owned[0].opacity,
    customData: { ...element.customData, ...markOwnership(custom) },
  }))
  if (!replacements.length) return
  api.updateScene({
    elements: [...elements.filter((element) => !ownsMark(element, markName)), ...replacements],
    commitToHistory: true,
  })
}

/** What ties a stamp back to its Derma Chart Mark, kept across a redraw. */
function markOwnership(custom = {}) {
  return {
    generated_by: custom.generated_by,
    mark_name: custom.mark_name,
    derma_chart_mark: custom.derma_chart_mark,
    sequence: custom.sequence,
    clinical_procedure: custom.clinical_procedure,
  }
}

/** Where the stamp was placed. Marks stamped before sizes existed fall back to their bounds. */
function stampOrigin(custom = {}, elements = []) {
  const x = Number(custom.origin_x)
  const y = Number(custom.origin_y)
  if (Number.isFinite(x) && Number.isFinite(y)) return { x, y }
  return elementsCentre(elements)
}

function elementsCentre(elements = []) {
  const left = Math.min(...elements.map((element) => element.x))
  const top = Math.min(...elements.map((element) => element.y))
  const right = Math.max(...elements.map((element) => element.x + (element.width || 0)))
  const bottom = Math.max(...elements.map((element) => element.y + (element.height || 0)))
  return { x: (left + right) / 2, y: (top + bottom) / 2 }
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
  // Selecting a mark the practitioner picked from a list is worth nothing if it sits
  // outside the viewport.
  const selected = api.getSceneElements().filter((element) => ids.includes(element.id))
  api.scrollToContent?.(selected, { fitToContent: false, animate: true })
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
      size: mark.marker_size,
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
  const selected = new Set(state.selected || [])
  let changed = false
  const elements = api.getSceneElements().map((element) => {
    if (element.isDeleted || element.customData?.kind !== TEMPLATE_PART_KIND) return element
    const partName = element.customData?.part_name || element.customData?.partName || ""
    const baseColor = element.customData?.base_color || "#4dabf7"
    const baseOpacity = Number(element.customData?.base_opacity || 0.14)
    const isSelected = Boolean(partName) && selected.has(partName)
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

/**
 * The scene as the exported image should show it: only the selected areas, drawn as they are
 * on screen even while "Hide Areas" fades them, so a view toggle never changes what is filed.
 * The live scene is untouched, so a failed export cannot leave the canvas half-hidden.
 */
function exportableElements(elements, state = {}) {
  const selected = new Set(state.selected || [])
  return (elements || [])
    .filter((element) => {
      if (element.customData?.kind !== TEMPLATE_PART_KIND) return true
      return selected.has(element.customData?.part_name || element.customData?.partName || "")
    })
    .map((element) =>
      element.customData?.kind === TEMPLATE_PART_KIND && element.opacity !== 100
        ? { ...element, opacity: 100 }
        : element
    )
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

function createStampElements({ behavior, color, origin, sequence, groupId, template, procedureVariables, size }) {
  const scale = markerSizeOf(size)
  const elements = stampShapeElements({ behavior, color, origin, sequence, groupId, template, procedureVariables, scale })
  // The badge layer reads the size from here. The origin travels with the stamp because a
  // cluster is not centred on it - resizing from the bounding box would walk the mark.
  return elements.map((element) => ({
    ...element,
    customData: { ...(element.customData || {}), marker_size: scale, origin_x: origin.x, origin_y: origin.y },
  }))
}

function stampShapeElements({ behavior, color, origin, sequence, groupId, template, procedureVariables, scale }) {
  const preset = createPresetElements(template, origin, color, groupId, procedureVariables, scale)
  if (preset.length) return preset
  if (behavior.includes("x")) return createXMark(origin, color, groupId, template, procedureVariables, scale)
  if (behavior.includes("target")) return createTargetMark(origin, color, groupId, template, procedureVariables, scale)
  // Dragged behaviours take their geometry from the gesture, so their shape stays unscaled.
  if (behavior.includes("hatch") || behavior.includes("five_lines")) return createHatchMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("area")) return createAreaMark(origin, color, groupId, template, procedureVariables)
  if (behavior.includes("triangle")) return createTriangleCluster(origin, color, groupId, template, procedureVariables, scale)
  if (behavior.includes("finding_dot") || behavior.includes("three_dots")) return createDotCluster(origin, color, groupId, template, procedureVariables, scale)
  return createNumberedDot(origin, color, groupId, template, sequence, procedureVariables, scale)
}

function createPresetElements(template, origin, color, groupId, procedureVariables, scale = 1) {
  if (!template?.custom_derma_marker_preset_json) return []
  try {
    const preset = JSON.parse(template.custom_derma_marker_preset_json)
    const elements = Array.isArray(preset) ? preset : preset.elements || []
    return elements.map((element) => ({
      ...element,
      ...baseElement(
        element.type || "ellipse",
        origin.x + Number(element.x || 0) * scale,
        origin.y + Number(element.y || 0) * scale,
        Number(element.width || 12) * scale,
        Number(element.height || 12) * scale,
        element.strokeColor || color,
        groupId,
        template,
        procedureVariables,
        { ...element, strokeWidth: scaledStrokeWidth(element.strokeWidth || 2, scale) }
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
function createNumberedDot(origin, color, groupId, template, sequence, procedureVariables, scale = 1) {
  const radius = 8 * scale
  return [
    ellipseElement(origin.x - radius, origin.y - radius, radius * 2, radius * 2, color, groupId, template, procedureVariables, {
      backgroundColor: color,
      strokeWidth: scaledStrokeWidth(2, scale),
    }),
  ]
}

function createDotCluster(origin, color, groupId, template, procedureVariables, scale = 1) {
  const offsets = [[0, -12], [-12, 8], [12, 8]]
  const radius = 5 * scale
  return offsets.map(([x, y]) =>
    ellipseElement(origin.x + x * scale - radius, origin.y + y * scale - radius, radius * 2, radius * 2, color, groupId, template, procedureVariables, {
      backgroundColor: color,
      strokeWidth: scaledStrokeWidth(2, scale),
    })
  )
}

function createTriangleCluster(origin, color, groupId, template, procedureVariables, scale = 1) {
  const offsets = [[0, -14], [-14, 10], [14, 10]]
  return offsets.flatMap(([x, y]) =>
    triangleElements(origin.x + x * scale, origin.y + y * scale, 16 * scale, color, groupId, template, procedureVariables, scale)
  )
}

function createHatchMark(origin, color, groupId, template, procedureVariables) {
  return [-20, -10, 0, 10, 20].map((offset) =>
    lineElement(origin.x - 36, origin.y + offset + 18, origin.x + 36, origin.y + offset - 18, color, groupId, template, procedureVariables, 3)
  )
}

function createXMark(origin, color, groupId, template, procedureVariables, scale = 1) {
  const arm = 18 * scale
  const stroke = scaledStrokeWidth(3, scale)
  return [
    lineElement(origin.x - arm, origin.y - arm, origin.x + arm, origin.y + arm, color, groupId, template, procedureVariables, stroke),
    lineElement(origin.x + arm, origin.y - arm, origin.x - arm, origin.y + arm, color, groupId, template, procedureVariables, stroke),
  ]
}

function createTargetMark(origin, color, groupId, template, procedureVariables, scale = 1) {
  const ring = 18 * scale
  const core = 7 * scale
  const cross = 26 * scale
  const stroke = scaledStrokeWidth(2, scale)
  return [
    ellipseElement(origin.x - ring, origin.y - ring, ring * 2, ring * 2, color, groupId, template, procedureVariables, { strokeWidth: stroke }),
    ellipseElement(origin.x - core, origin.y - core, core * 2, core * 2, color, groupId, template, procedureVariables, {
      backgroundColor: color,
      strokeWidth: stroke,
    }),
    lineElement(origin.x - cross, origin.y, origin.x + cross, origin.y, color, groupId, template, procedureVariables, stroke),
    lineElement(origin.x, origin.y - cross, origin.x, origin.y + cross, color, groupId, template, procedureVariables, stroke),
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

function triangleElements(x, y, size, color, groupId, template, procedureVariables, scale = 1) {
  const half = size / 2
  const height = size * 0.9
  const stroke = scaledStrokeWidth(3, scale)
  return [
    lineElement(x, y - height / 2, x - half, y + height / 2, color, groupId, template, procedureVariables, stroke),
    lineElement(x - half, y + height / 2, x + half, y + height / 2, color, groupId, template, procedureVariables, stroke),
    lineElement(x + half, y + height / 2, x, y - height / 2, color, groupId, template, procedureVariables, stroke),
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
    // Stored variable rows first, so a value that also maps to a mark field reads the field.
    ...(mark.procedure_variables || {}),
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

/**
 * Drop captured photos onto the canvas at the centre of what the practitioner is looking at,
 * cascaded so a burst reads as several photos. They are ordinary, unlocked elements: movable,
 * resizable, and drawable over.
 */
function insertPhotoElements(api, photos = []) {
  if (!api || !photos.length) return []
  const viewport = viewportBounds(api.getAppState())
  const elements = photos.map((photo, index) => photoElement(photo, viewport, index))
  api.addFiles(
    elements.map((element) => ({
      id: element.fileId,
      mimeType: "image/jpeg",
      dataURL: element.dataURL,
      created: Date.now(),
      lastRetrieved: Date.now(),
    }))
  )
  api.updateScene({ elements: [...api.getSceneElements(), ...elements], commitToHistory: true })
  return elements.map((element) => element.id)
}

function viewportBounds(appState = {}) {
  const zoom = appState.zoom?.value || 1
  const width = (appState.width || 900) / zoom
  const height = (appState.height || 620) / zoom
  return {
    width,
    height,
    centreX: width / 2 - (appState.scrollX || 0),
    centreY: height / 2 - (appState.scrollY || 0),
  }
}

function photoElement(photo, viewport, index) {
  const fileId = `derma-photo-${String(photo.photo).replace(/[^a-zA-Z0-9_-]+/g, "-")}`
  const { width, height } = photoGeometry(photo, viewport)
  const offset = index * PHOTO_CASCADE_OFFSET
  return {
    ...photoElementDefaults(),
    id: `${fileId}-element`,
    x: viewport.centreX - width / 2 + offset,
    y: viewport.centreY - height / 2 + offset,
    width,
    height,
    dataURL: photo.dataUrl,
    fileId,
    customData: {
      kind: PHOTO_KIND,
      photo: photo.photo,
      photo_set: photo.photoSet,
      image: photo.fileUrl,
    },
  }
}

function photoGeometry(photo, viewport) {
  const naturalWidth = Number(photo.width) || 1600
  const naturalHeight = Number(photo.height) || 1200
  const scale = Math.min(
    (viewport.width * PHOTO_VIEWPORT_RATIO) / naturalWidth,
    (viewport.height * PHOTO_VIEWPORT_RATIO) / naturalHeight
  )
  return { width: naturalWidth * scale, height: naturalHeight * scale }
}

function photoElementDefaults() {
  return {
    type: "image",
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
    seed: Math.floor(Math.random() * 1000000000),
    version: 1,
    versionNonce: Math.floor(Math.random() * 1000000000),
    isDeleted: false,
    boundElements: null,
    updated: Date.now(),
    link: null,
    locked: false,
    status: "saved",
    scale: [1, 1],
  }
}

/** The photos the drawing currently carries. What is missing from it has been deleted. */
function photoElementNames(api) {
  return (api?.getSceneElements?.() || [])
    .filter((element) => !element.isDeleted && element.customData?.kind === PHOTO_KIND)
    .map((element) => element.customData.photo)
    .filter(Boolean)
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

/**
 * The URL a stored image element is repainted from. Only the body template may fall back to the
 * scene-level template: a captured photo that lost its own URL must render as Excalidraw's
 * placeholder, never as another image.
 */
function elementImageSource(element, scene) {
  const custom = element.customData || {}
  if (custom.kind === PHOTO_KIND) return custom.image || ""
  const template = custom.template || (custom.kind === "derma_template" ? scene.derma_template : null)
  return template?.image || ""
}

async function hydrateSceneImageFiles(scene) {
  const elements = scene.elements || []
  const files = normalizeBinaryFiles(scene.files)
  const hydratedFiles = { ...files }
  const elementDataUrls = {}
  let unreadablePhotoCount = 0

  for (const element of elements) {
    if (element.type !== "image" || !element.fileId) continue
    if (hydratedFiles[element.fileId]?.dataURL) {
      elementDataUrls[element.fileId] = hydratedFiles[element.fileId].dataURL
      continue
    }
    const source = elementImageSource(element, scene)
    if (!source) continue
    try {
      const { dataURL, mimeType } = await imageUrlToRenderableData(source)
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
      if (element.customData?.kind === PHOTO_KIND) unreadablePhotoCount += 1
    }
  }
  if (unreadablePhotoCount) {
    globalThis.frappe?.show_alert?.({
      message: `${unreadablePhotoCount} photo(s) on this drawing could not be loaded. Their frames are left in place.`,
      indicator: "red",
    })
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

/**
 * Swap the badge layer for a freshly numbered one. Badges are ordinary scene elements so they
 * export with the drawing and are visible while working, but they are derived state: never
 * committed to undo history, and stripped from what gets persisted.
 */
function syncBadgeLayer(api, badges = [], signatureRef) {
  if (!api) return
  const signature = badges.map((badge) => `${badge.id}:${Math.round(badge.x)}:${Math.round(badge.y)}:${badge.text || ""}`).join("|")
  if (signature === signatureRef.current) return
  signatureRef.current = signature
  const existing = api.getSceneElements().filter((element) => element.customData?.kind !== BADGE_KIND)
  api.updateScene({ elements: [...existing, ...badges], commitToHistory: false })
}

/**
 * Drop the base64 payload of every image the scene can repaint from a URL - the body template
 * and the captured photos. hydrateSceneImageFiles() rebuilds them on load, so the megabytes they
 * would otherwise cost per annotation buy nothing.
 *
 * Keyed strictly on those two kinds, never on "is an image": an image the practitioner inserted
 * with Excalidraw's own tool has no URL to rebuild from, so stripping it would destroy it. And
 * the template *element* must survive - _sync_chart_marks_for_annotation returns early without
 * it, which would silently stop every mark in the session being linked back to the annotation.
 */
function stripStoredImagePayload(elements, files) {
  const rebuildableFileIds = new Set(
    elements
      .filter((element) => REBUILDABLE_IMAGE_KINDS.has(element.customData?.kind) && element.fileId)
      .map((element) => element.fileId)
  )
  return {
    elements: elements
      .filter((element) => element.customData?.kind !== BADGE_KIND)
      // Area outlines are derived from the body template and re-rendered on every load. Storing
      // them would freeze a drawing against the geometry it was made with, so a later template
      // edit would leave old and new outlines mixed on the next resave.
      .filter((element) => element.customData?.kind !== TEMPLATE_PART_KIND)
      .map((element) => (rebuildableFileIds.has(element.fileId) ? { ...element, dataURL: undefined } : element)),
    files: Object.fromEntries(Object.entries(files).filter(([fileId]) => !rebuildableFileIds.has(fileId))),
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

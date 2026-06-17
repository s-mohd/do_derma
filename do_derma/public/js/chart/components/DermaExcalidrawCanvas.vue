<template>
  <div class="derma-excalidraw-canvas">
    <div v-if="showEmptyOverlay" class="derma-canvas-empty">
      <strong>{{ __("Derma Chart") }}</strong>
      <span>{{ __("Choose a chart image or select a procedure to begin.") }}</span>
    </div>

    <div ref="hostRef" class="derma-excalidraw-host"></div>
    <div v-if="viewTemplates.length > 1" class="excalidraw-view-rotate" :aria-label="__('Rotate chart view')">
      <button type="button" :title="__('Previous view')" @click="rotateTemplate(-1)">
        <span aria-hidden="true">↶</span>
      </button>
      <button type="button" :title="__('Next view')" @click="rotateTemplate(1)">
        <span aria-hidden="true">↷</span>
      </button>
    </div>
    <div v-if="chartNavigationTargets.length" class="excalidraw-region-nav" :aria-label="__('Body part navigation')">
      <button
        v-for="target in chartNavigationTargets"
        :key="target.key"
        type="button"
        :style="target.style"
        :title="target.label"
        @click="loadNavigationTarget(target)"
      >
        <span aria-hidden="true">+</span>
        <small>{{ target.label }}</small>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { mountEmbeddedExcalidraw } from "../excalidraw/EmbeddedExcalidraw.jsx"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  latestAnnotation: { type: Object, default: null },
  annotationHistory: { type: Array, default: () => [] },
  selectedTemplate: { type: Object, default: null },
  bodyTemplate: { type: Object, default: null },
  bodyTemplates: { type: Array, default: () => [] },
  procedureVariables: { type: Object, default: () => ({}) },
  marks: { type: Array, default: () => [] },
  overlayMode: { type: String, default: "today" },
})

const emit = defineEmits(["load-template", "import-annotation", "place-mark", "select-mark", "select-region", "update:overlay-mode", "carry-forward-history"])

const hostRef = ref(null)
let bridge = null

const showEmptyOverlay = computed(() => !props.bodyTemplate?.image)
const viewTemplates = computed(() => {
  if (!props.bodyTemplate?.name) return []
  const type = props.bodyTemplate.template_type
  const gender = props.bodyTemplate.gender
  return props.bodyTemplates
    .filter((row) => row.image && row.template_type === type && row.gender === gender)
    .sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0) || String(a.title || a.name).localeCompare(String(b.title || b.name)))
})
const chartNavigationTargets = computed(() => navigationTargets(props.bodyTemplate)
  .map((target) => {
    const template = findTargetTemplate(target)
    if (!template || template.name === props.bodyTemplate?.name) return null
    return { ...target, template }
  })
  .filter(Boolean))

onMounted(() => {
  bridge = mountEmbeddedExcalidraw(hostRef.value, {
    initialAnnotation: null,
    selectedTemplate: props.selectedTemplate,
    bodyTemplate: props.bodyTemplate,
    procedureVariables: props.procedureVariables,
    marks: props.marks,
	    onMarkPlaced: (payload) => emit("place-mark", payload),
	    onMarkSelected: (payload) => emit("select-mark", payload),
	    onRegionSelected: (payload) => emit("select-region", payload),
	  })
})

onBeforeUnmount(() => {
  if (bridge?.unmount) bridge.unmount()
  bridge = null
})

watch(
  () => props.selectedTemplate,
  (template) => {
    bridge?.setSelectedTemplate?.(template || null)
  },
  { deep: true }
)

watch(
  () => props.bodyTemplate,
  (template) => {
    if (template?.image) {
      bridge?.loadTemplateImage?.(template)
    } else {
      bridge?.setBodyTemplate?.(template || null)
    }
  },
  { deep: true }
)

watch(
  () => props.procedureVariables,
  (variables) => {
    bridge?.setProcedureVariables?.(variables || {})
  },
  { deep: true }
)

watch(
  () => props.marks,
  (marks) => {
    bridge?.setMarks?.(marks || [])
  },
  { deep: true }
)

function loadAnnotation(annotation) {
  bridge?.loadAnnotation?.(annotation)
}

function exportScene() {
  return bridge?.exportScene?.()
}

function loadTemplateImage(template = props.bodyTemplate) {
  return bridge?.loadTemplateImage?.(template)
}

function linkMarkElements(payload) {
  return bridge?.linkMarkElements?.(payload)
}

function selectMark(markName) {
  return bridge?.selectMark?.(markName)
}

function setTool(tool) {
  bridge?.setDermaTool?.(tool)
}

function resetView() {
  bridge?.resetView?.()
}

function loadNavigationTarget(target) {
  if (!target?.template) return
  emit("load-template", target.template)
}

function rotateTemplate(direction) {
  const templates = viewTemplates.value
  if (!templates.length) return
  const index = templates.findIndex((row) => row.name === props.bodyTemplate?.name)
  const currentIndex = index >= 0 ? index : 0
  const nextIndex = (currentIndex + direction + templates.length) % templates.length
  emit("load-template", templates[nextIndex])
}

function findTargetTemplate(target) {
  const gender = props.bodyTemplate?.gender
  return props.bodyTemplates.find((row) => row.image && row.gender === gender && target.matches(row)) ||
    props.bodyTemplates.find((row) => row.image && target.matches(row))
}

function navigationTargets(template) {
  const configured = configuredNavigationTargets(template)
  return configured.length ? configured : defaultNavigationTargets(template)
}

function configuredNavigationTargets(template) {
  if (!Array.isArray(template?.regions)) return []
  return template.regions
    .map((region, index) => configuredNavTarget(region, index))
    .filter(Boolean)
}

function configuredNavTarget(region, index) {
  const targetTemplate = region?.target_template || region?.body_template || region?.template
  const targetViewKey = region?.target_view_key || region?.view_key
  const targetType = region?.target_template_type || region?.template_type
  if (!targetTemplate && !targetViewKey && !targetType) return null
  const x = percentValue(region.x_percent ?? region.x ?? region.left)
  const y = percentValue(region.y_percent ?? region.y ?? region.top)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  const label = region.label || region.part_name || region.region || targetTemplate || targetType || targetViewKey || __("Open")
  return {
    key: `configured-${index}-${label}`,
    label,
    style: { left: `${x}%`, top: `${y}%` },
    matches: (row) => {
      if (targetTemplate && [row.name, row.title].includes(targetTemplate)) return true
      if (targetViewKey && normalizedViewKey(row.view_key) === normalizedViewKey(targetViewKey)) return true
      if (targetType && String(row.template_type || "") === String(targetType)) return true
      return false
    },
  }
}

function percentValue(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return Number.NaN
  return number <= 1 ? number * 100 : number
}

function defaultNavigationTargets(template) {
  if (!template?.image) return []
  const type = String(template?.template_type || "").toLowerCase()
  if (type === "face") {
    return [
      navTarget("Scalp", { left: "53%", top: "15%" }, (row) => row.template_type === "Scalp"),
      navTarget("Ear", { left: "22%", top: "44%" }, viewKeyMatches("left_ear")),
      navTarget("Ear", { left: "78%", top: "44%" }, viewKeyMatches("right_ear")),
      navTarget("Nose", { left: "74%", top: "56%" }, viewKeyMatches("nose_mouth")),
      navTarget("Full Body", { left: "18%", top: "86%" }, (row) => row.template_type === "Body"),
    ]
  }
  if (type === "hands") {
    return [navTarget("Full Body", { left: "16%", top: "86%" }, (row) => row.template_type === "Body")]
  }
  if (type === "scalp") {
    return [navTarget("Face", { left: "78%", top: "82%" }, (row) => row.template_type === "Face")]
  }
  return [
    navTarget("Face", { left: "58%", top: "12%" }, (row) => row.template_type === "Face"),
    navTarget("Scalp", { left: "48%", top: "7%" }, (row) => row.template_type === "Scalp"),
    navTarget("Chest", { left: "79%", top: "27%" }, viewKeyMatches("chest")),
    navTarget("Arm", { left: "22%", top: "42%" }, viewKeyMatches("left_arm")),
    navTarget("Arm", { left: "80%", top: "42%" }, viewKeyMatches("right_arm")),
    navTarget("Hand", { left: "20%", top: "61%" }, (row) => row.template_type === "Hands" || viewKeyMatches("left_hand")(row)),
    navTarget("Hand", { left: "81%", top: "61%" }, (row) => row.template_type === "Hands" || viewKeyMatches("right_hand")(row)),
    navTarget("Legs", { left: "77%", top: "77%" }, viewKeyMatches("right_leg")),
    navTarget("Foot", { left: "31%", top: "91%" }, viewKeyMatches("left_foot")),
    navTarget("Foot", { left: "72%", top: "91%" }, viewKeyMatches("right_foot")),
  ]
}

function navTarget(label, style, matches) {
  return { key: `${label}-${style.left}-${style.top}`, label, style, matches }
}

function viewKeyMatches(key) {
  return (row) => normalizedViewKey(row.view_key) === normalizedViewKey(key)
}

function normalizedViewKey(value) {
  return String(value || "").replace(/^(male|female)_/, "")
}

defineExpose({ exportScene, loadAnnotation, loadTemplateImage, linkMarkElements, selectMark, setTool, resetView })
</script>

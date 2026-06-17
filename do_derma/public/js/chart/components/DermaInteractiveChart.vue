<template>
  <div class="derma-interactive-chart">
    <div ref="frameRef" class="native-chart-frame" @click="handleFrameClick">
      <button type="button" class="native-view-arrow previous" :disabled="!previousTemplate" :title="__('Previous view')" @click.stop="emitTemplate(previousTemplate)">
        &lsaquo;
      </button>
      <button type="button" class="native-view-arrow next" :disabled="!nextTemplate" :title="__('Next view')" @click.stop="emitTemplate(nextTemplate)">
        &rsaquo;
      </button>
      <div v-if="detailTargets.length" class="native-region-nav" :aria-label="__('Body part navigation')">
        <button
          v-for="target in detailTargets"
          :key="target.key"
          type="button"
          :title="target.label"
          @click.stop="openDetailTarget(target)"
        >
          <span aria-hidden="true">+</span>
          <small>{{ target.label }}</small>
        </button>
      </div>

      <div v-if="!bodyTemplate?.image" class="native-chart-empty">
        <strong>{{ __("Load a Chart Image") }}</strong>
        <span>{{ __("Select a female or male face/body template from the right panel.") }}</span>
      </div>

      <img
        v-else
        ref="imageRef"
        class="native-chart-image"
        :src="bodyTemplate.image"
        :alt="bodyTemplate.title || bodyTemplate.name"
        draggable="false"
        @load="measureImage"
      />

      <svg
        v-if="bodyTemplate?.image && imageBounds.width"
        class="native-region-layer"
        :style="boundsStyle"
        :viewBox="`0 0 ${imageBounds.width} ${imageBounds.height}`"
        preserveAspectRatio="none"
      >
        <polygon
          v-for="region in regionPolygons"
          :key="region.key"
          :points="region.points"
          :fill="region.fill"
          :stroke="region.color"
          :class="{ active: selectedRegionKey === region.key }"
          @click.stop="selectRegion(region, $event)"
        />
      </svg>

      <button
        v-for="mark in positionedMarks"
        :key="mark.name"
        type="button"
        class="native-chart-mark"
        :class="[mark.tone, { selected: isSelectedMark(mark), history: mark._history }]"
        :style="mark.style"
        :title="mark.title"
        @click.stop="$emit('select-mark', mark)"
      >
        <span v-if="mark.shape === 'x'" class="mark-x"></span>
        <span v-else-if="mark.shape === 'triangle'" class="mark-triangle"></span>
        <span v-else-if="mark.shape === 'target'" class="mark-target"></span>
        <span v-else-if="mark.shape === 'hatch'" class="mark-hatch"></span>
        <span v-else class="mark-dot">{{ mark.label }}</span>
      </button>
    </div>

    <footer class="native-view-strip" v-if="viewTemplates.length > 1">
      <button
        v-for="template in viewTemplates"
        :key="template.name"
        type="button"
        :class="{ active: template.name === bodyTemplate?.name }"
        @click="emitTemplate(template)"
      >
        <img v-if="template.image" :src="template.image" :alt="template.title || template.name" />
        <span v-else>{{ initials(template) }}</span>
        <small>{{ shortViewLabel(template) }}</small>
      </button>
    </footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  selectedTemplate: { type: Object, default: null },
  bodyTemplate: { type: Object, default: null },
  bodyTemplates: { type: Array, default: () => [] },
  procedureVariables: { type: Object, default: () => ({}) },
  marks: { type: Array, default: () => [] },
  selectedMarkName: { type: String, default: "" },
  selectedMarkNames: { type: Array, default: () => [] },
  overlayMode: { type: String, default: "today" },
})

const emit = defineEmits(["load-template", "place-mark", "select-mark", "select-region", "update:overlay-mode", "carry-forward-history"])

const frameRef = ref(null)
const imageRef = ref(null)
const imageBounds = ref({ x: 0, y: 0, width: 0, height: 0 })
const selectedRegionKey = ref("")
let resizeObserver = null

const viewTemplates = computed(() => {
  if (!props.bodyTemplate?.name) return props.bodyTemplates.filter((row) => row.image).slice(0, 8)
  const gender = props.bodyTemplate.gender
  const type = props.bodyTemplate.template_type
  const rows = props.bodyTemplates
    .filter((row) => row.image && (!gender || row.gender === gender) && (!type || row.template_type === type))
    .sort(sortTemplates)
  return rows.length ? rows : props.bodyTemplates.filter((row) => row.image).sort(sortTemplates)
})

const currentIndex = computed(() => viewTemplates.value.findIndex((row) => row.name === props.bodyTemplate?.name))
const previousTemplate = computed(() => {
  if (currentIndex.value < 0 || viewTemplates.value.length < 2) return null
  return viewTemplates.value[(currentIndex.value - 1 + viewTemplates.value.length) % viewTemplates.value.length]
})
const nextTemplate = computed(() => {
  if (currentIndex.value < 0 || viewTemplates.value.length < 2) return null
  return viewTemplates.value[(currentIndex.value + 1) % viewTemplates.value.length]
})

const viewLabel = computed(() => {
  if (!props.bodyTemplate?.name) return __("No image loaded")
  return [props.bodyTemplate.gender, props.bodyTemplate.template_type, props.bodyTemplate.view_key].filter(Boolean).join(" / ")
})

const boundsStyle = computed(() => ({
  left: `${imageBounds.value.x}px`,
  top: `${imageBounds.value.y}px`,
  width: `${imageBounds.value.width}px`,
  height: `${imageBounds.value.height}px`,
}))

const regionPolygons = computed(() => {
  const bounds = imageBounds.value
  if (!bounds.width || !bounds.height) return []
  return (props.bodyTemplate?.parts || [])
    .map((part, index) => {
      const coords = parseShape(part.shape_json)
      if (coords.length < 3) return null
      const points = coords.map(([x, y]) => `${Number(x || 0) * bounds.width},${Number(y || 0) * bounds.height}`).join(" ")
      const color = part.color || "#14b8a6"
      return {
        ...part,
        key: part.name || `${part.part_name}-${index}`,
        points,
        color,
        fill: hexToRgba(color, Number(part.opacity ?? 0.14)),
        center: centerOf(coords),
      }
    })
    .filter(Boolean)
})

const detailTargets = computed(() => {
  if (!props.bodyTemplate?.image || !imageBounds.value.width) return []
  const candidates = defaultDetailTargets(props.bodyTemplate)
  return candidates
    .map((target) => {
      const template = findTargetTemplate(target)
      if (!template || template.name === props.bodyTemplate?.name) return null
      return {
        ...target,
        template,
        style: {
          left: `${imageBounds.value.x + target.x * imageBounds.value.width}px`,
          top: `${imageBounds.value.y + target.y * imageBounds.value.height}px`,
        },
      }
    })
    .filter(Boolean)
})

const positionedMarks = computed(() => {
  const bounds = imageBounds.value
  if (!bounds.width || !bounds.height) return []
  return props.marks
    .filter((mark) => !props.bodyTemplate?.name || !mark.body_template || mark.body_template === props.bodyTemplate.name)
    .map((mark) => {
      const x = clamp(Number(mark.x_percent || 0), 0, 100) / 100
      const y = clamp(Number(mark.y_percent || 0), 0, 100) / 100
      const shape = markShape(mark)
      const category = String(mark.category || mark.derma_category || "").toLowerCase()
      return {
        ...mark,
        shape,
        tone: mark._history ? "previous" : category || shape,
        label: mark.sequence || "",
        title: [mark.category, mark.region_label || mark.body_region, mark.status].filter(Boolean).join(" / "),
        style: {
          left: `${bounds.x + x * bounds.width}px`,
          top: `${bounds.y + y * bounds.height}px`,
          "--mark-color": mark.marker_color || categoryColor(category),
        },
      }
    })
})

onMounted(() => {
  nextTick(measureImage)
  resizeObserver = new ResizeObserver(measureImage)
  if (frameRef.value) resizeObserver.observe(frameRef.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

watch(() => props.bodyTemplate?.image, () => nextTick(measureImage))

function measureImage() {
  const frame = frameRef.value
  const image = imageRef.value
  if (!frame || !image || !image.naturalWidth || !image.naturalHeight) {
    imageBounds.value = { x: 0, y: 0, width: 0, height: 0 }
    return
  }
  const frameRect = frame.getBoundingClientRect()
  const frameWidth = frame.clientWidth
  const frameHeight = frame.clientHeight
  const imageRatio = image.naturalWidth / image.naturalHeight
  const frameRatio = frameWidth / frameHeight
  let width = frameWidth
  let height = frameHeight
  if (frameRatio > imageRatio) {
    height = frameHeight
    width = height * imageRatio
  } else {
    width = frameWidth
    height = width / imageRatio
  }
  imageBounds.value = {
    x: (frameRect.width - width) / 2,
    y: (frameRect.height - height) / 2,
    width,
    height,
  }
}

function handleFrameClick() {
  // The native body map is for review/navigation only. Drawing and marks live in annotation mode.
}

function selectRegion(region) {
  selectedRegionKey.value = region.key
  emit("select-region", region)
}

function openDetailTarget(target) {
  if (target?.template) emitTemplate(target.template)
}

function emitTemplate(template) {
  if (template?.name) emit("load-template", template)
}

function findTargetTemplate(target) {
  const gender = props.bodyTemplate?.gender
  return props.bodyTemplates.find((row) => row.image && row.gender === gender && target.matches(row)) ||
    props.bodyTemplates.find((row) => row.image && target.matches(row))
}

function defaultDetailTargets(template) {
  const type = String(template?.template_type || "").toLowerCase()
  if (type === "face") {
    return [
      target("Scalp", "Scalp", 0.5, 0.08, (row) => row.template_type === "Scalp"),
      target("Eyes", "Eyes", 0.5, 0.36, viewKeyMatches("eyes")),
      target("Nose and Mouth", "Nose and Mouth", 0.5, 0.58, viewKeyMatches("nose_mouth")),
      target("Ear", "Ear", 0.16, 0.48, viewKeyMatches("left_ear")),
      target("Ear", "Ear", 0.84, 0.48, viewKeyMatches("right_ear")),
      target("Full Body", "Body", 0.12, 0.9, (row) => row.template_type === "Body"),
    ]
  }
  if (type === "hands") {
    return [target("Full Body", "Body", 0.1, 0.9, (row) => row.template_type === "Body")]
  }
  if (type === "scalp") {
    return [target("Face", "Face", 0.82, 0.86, (row) => row.template_type === "Face")]
  }
  if (type === "custom") {
    return [target("Full Body", "Body", 0.1, 0.9, (row) => row.template_type === "Body")]
  }
  return [
    target("Face", "Face", 0.5, 0.1, (row) => row.template_type === "Face"),
    target("Scalp", "Scalp", 0.5, 0.04, (row) => row.template_type === "Scalp"),
    target("Chest", "Chest", 0.5, 0.28, viewKeyMatches("chest")),
    target("Abdomen", "Abdomen", 0.5, 0.43, viewKeyMatches("abdomen")),
    target("Arm", "Arm", 0.24, 0.4, viewKeyMatches("left_arm")),
    target("Arm", "Arm", 0.76, 0.4, viewKeyMatches("right_arm")),
    target("Hand", "Hands", 0.18, 0.58, (row) => row.template_type === "Hands" || viewKeyMatches("left_hand")(row)),
    target("Hand", "Hands", 0.82, 0.58, (row) => row.template_type === "Hands" || viewKeyMatches("right_hand")(row)),
    target("Leg", "Leg", 0.42, 0.74, viewKeyMatches("left_leg")),
    target("Leg", "Leg", 0.58, 0.74, viewKeyMatches("right_leg")),
    target("Foot", "Foot", 0.38, 0.94, viewKeyMatches("left_foot")),
    target("Foot", "Foot", 0.62, 0.94, viewKeyMatches("right_foot")),
  ]
}

function target(label, type, x, y, matches) {
  return { key: `${label}-${x}-${y}`, label, type, x, y, matches }
}

function viewKeyMatches(key) {
  return (row) => String(row.view_key || "").replace(/^male_/, "") === key
}

function markShape(mark) {
  const behavior = String(mark.marker_behavior || mark.custom_derma_marker_behavior || mark.category || "").toLowerCase()
  if (behavior.includes("triangle") || behavior.includes("filler")) return "triangle"
  if (behavior.includes("hatch") || behavior.includes("laser") || behavior.includes("area")) return "hatch"
  if (behavior.includes("biopsy") || behavior.includes("excision") || behavior.includes(" x") || behavior === "x") return "x"
  if (behavior.includes("target") || behavior.includes("lesion")) return "target"
  return "dot"
}

function categoryColor(category) {
  if (category.includes("botox")) return "#2563eb"
  if (category.includes("filler")) return "#16a34a"
  if (category.includes("laser")) return "#dc2626"
  if (category.includes("biopsy")) return "#d4a000"
  if (category.includes("lesion")) return "#f97316"
  if (category.includes("scar")) return "#7c3aed"
  return "#0ea5e9"
}

function isSelectedMark(mark) {
  return props.selectedMarkName === mark.name || props.selectedMarkNames.includes(mark.name)
}

function sortTemplates(a, b) {
  const sequence = Number(a.sequence || 0) - Number(b.sequence || 0)
  if (sequence) return sequence
  return String(a.title || a.name).localeCompare(String(b.title || b.name))
}

function shortViewLabel(template) {
  return template.view_key || template.title || template.name
}

function initials(template) {
  return String(template?.title || template?.name || "T")
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
}

function parseShape(value) {
  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function centerOf(points) {
  const sum = points.reduce((acc, [x, y]) => ({ x: acc.x + Number(x || 0), y: acc.y + Number(y || 0) }), { x: 0, y: 0 })
  const count = points.length || 1
  return { x: sum.x / count, y: sum.y / count }
}

function hexToRgba(hex = "#14b8a6", opacity = 0.14) {
  const clean = String(hex || "#14b8a6").replace("#", "")
  if (clean.length !== 6) return hex
  const red = parseInt(clean.slice(0, 2), 16)
  const green = parseInt(clean.slice(2, 4), 16)
  const blue = parseInt(clean.slice(4, 6), 16)
  return `rgba(${red}, ${green}, ${blue}, ${clamp(Number(opacity || 0), 0, 1)})`
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, Number(value) || 0))
}
</script>

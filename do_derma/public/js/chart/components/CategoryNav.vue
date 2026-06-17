<template>
  <div class="category-nav" :class="navClasses">
    <div
      v-for="group in groups"
      :key="group.id"
      class="category-tab"
      :class="{ open: open === group.id, disabled: isGroupDisabled(group.id) }"
      @mouseenter="handleOpen(group.id)"
      @mouseleave="handleOpen(null)"
      :ref="(el) => {
        if (!tabRefs.value) tabRefs.value = {}
        tabRefs.value[group.id] = el
      }"
    >
      <button type="button" :disabled="isGroupDisabled(group.id)">
        <img
          v-if="hasCategoryImage(group)"
          :src="group.image"
          :alt="group.label"
          class="cat-image"
          @error="markCategoryImageBroken(group.id)"
        />
        <span class="cat-label" :title="group.label">{{ truncated(group.label) }}</span>
        <span class="cat-underline" :style="{ background: group.color }"></span>
      </button>
      <div v-if="open === group.id" class="category-menu" :class="{ 'align-right': openAlignRight }">
        <button
          v-for="template in getTemplates(group.id)"
          :key="template.name"
          type="button"
          :disabled="template.is_disabled"
          :class="{ disabled: template.is_disabled }"
          @click="select(template)"
        >
          {{ formatTemplateEntry(template) }}
        </button>
        <p v-if="!getTemplates(group.id).length" class="field-hint">No templates</p>
      </div>
    </div>
    <!-- <div class="active-service" v-if="activeTemplate">
      <span class="badge">{{ activeTemplate.template }}</span>
      <button type="button" class="link" @click="$emit('clear')">×</button>
    </div> -->
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onBeforeUnmount } from "vue"

const props = defineProps({
  groups: { type: Array, default: () => [] },
  templates: { type: Array, default: () => [] },
  activeTemplate: { type: Object, default: null },
})

const emit = defineEmits(["select", "clear", "hover-group"])

const open = ref(null)
const openAlignRight = ref(false)
const tabRefs = ref({})
const brokenCategoryImages = ref(new Set())
let closeTimer = null

function mapTemplateToGroup(template) {
  const derma = (template?.custom_derma_category || "").toLowerCase()
  if (derma) return derma.replace(/[^a-z0-9]+/g, "-")

  const explicit = (template?.dental_procedure_category || template?.dental_condition_category || "").toLowerCase()
  if (explicit) return explicit

  const group = (template?.item_group || template?.template || "").toLowerCase()
  if (group.includes("crown")) return "crown"
  if (group.includes("restoration") || group.includes("filling")) return "restoration"
  if (group.includes("prosthesis") || group.includes("denture")) return "prosthesis"
  if (group.includes("implant")) return "implantation"
  if (group.includes("endo") || group.includes("root canal")) return "endo"
  if (group.includes("perio")) return "perio"
  if (group.includes("cosmetic")) return "cosmetics"
  if (group.includes("surgery") || group.includes("extraction")) return "surgery"
  if (group.includes("ortho")) return "orthodontics"
  if (group.includes("diagnosis") || group.includes("exam")) return "diagnosis"
  if (group.includes("pedo") || group.includes("child")) return "pedo"
  return "other"
}

const templateMap = computed(() => {
  const map = {}
  props.templates.forEach((tpl) => {
    const gid = mapTemplateToGroup(tpl)
    if (!map[gid]) map[gid] = []
    map[gid].push(tpl)
  })
  return map
})

function getTemplates(groupId) {
  return templateMap.value[groupId] || []
}

function isGroupDisabled(groupId) {
  const templates = getTemplates(groupId)
  if (!templates.length) return true
  return templates.every((tpl) => tpl?.is_disabled)
}

function select(template) {
  if (template?.is_disabled) return
  emit("select", template)
  open.value = null
}

function handleOpen(id) {
  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }
  if (id && isGroupDisabled(id)) return
  if (!id) {
    closeTimer = setTimeout(() => {
      open.value = null
      emit("hover-group", null)
    }, 180)
    return
  }
  open.value = id
  emit("hover-group", id)
}

function updateMenuAlignment() {
  const id = open.value
  if (!id || !tabRefs.value.value[id]) {
    openAlignRight.value = false
    return
  }
  const tabEl = tabRefs.value.value[id]
  if (!tabEl) return
  const rect = tabEl.getBoundingClientRect()
  const menuEl = tabEl.querySelector(".category-menu")
  const menuWidth = menuEl?.getBoundingClientRect().width || 260
  const gutter = 16
  const spaceRight = window.innerWidth - rect.right - gutter
  const spaceLeft = rect.left - gutter
  if (spaceRight < menuWidth && spaceLeft >= menuWidth) {
    openAlignRight.value = true
  } else if (spaceRight >= menuWidth) {
    openAlignRight.value = false
  } else {
    openAlignRight.value = true
  }
}

watch(
  () => open.value,
  (id) => {
    if (!id) {
      openAlignRight.value = false
      return
    }
    nextTick(() => {
      requestAnimationFrame(() => {
        updateMenuAlignment()
      })
    })
  }
)

const handleResize = () => {
  if (!open.value) return
  updateMenuAlignment()
}
window.addEventListener("resize", handleResize)
onBeforeUnmount(() => {
  if (closeTimer) clearTimeout(closeTimer)
  window.removeEventListener("resize", handleResize)
})

const navClasses = computed(() => {
  const many = props.groups.length > 10
  const dense = props.groups.length > 7
  return {
    dense,
    wrap: many,
  }
})

function truncated(label = "") {
  const limit = props.groups.length > 10 ? 6 : 12
  if (label.length <= limit) return label
  return `${label.slice(0, limit - 1)}…`
}

function hasCategoryImage(group) {
  const image = String(group?.image || "").trim()
  if (!image || !group?.id) return false
  return !brokenCategoryImages.value.has(group.id)
}

function markCategoryImageBroken(groupId) {
  if (!groupId || brokenCategoryImages.value.has(groupId)) return
  brokenCategoryImages.value = new Set(brokenCategoryImages.value).add(groupId)
}

function formatTemplateEntry(template) {
  const code = String(template?.custom_procedure_code || template?.procedure_code || "").trim()
  const label = String(template?.procedure_template || template?.template || template?.name || "").trim()
  if (code && label) return `${code} - ${label}`
  return code || label || ""
}
</script>

<style scoped>
.dental-chart-page .category-nav {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  padding: 10px 12px 6px;
  margin: 12px 0 14px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
  position: relative;
  justify-content: center;
  flex-wrap: nowrap;
  overflow: visible;
}

.dental-chart-page .category-nav.dense {
  gap: 8px;
  padding: 8px 10px 4px;
}

.dental-chart-page .category-nav.wrap {
  flex-wrap: wrap;
  /* justify-content: flex-start; */
  row-gap: 6px;
}

.dental-chart-page .category-tab {
  position: relative;
  flex: 0 0 auto;
  padding-bottom: 12px;
  margin-bottom: -12px;
}

.dental-chart-page .category-tab.disabled button {
  opacity: 0.45;
  cursor: not-allowed;
}

.dental-chart-page .category-tab.disabled .cat-underline {
  visibility: hidden;
  transform: scaleX(0);
}

.dental-chart-page .category-tab button {
  border: none;
  background: transparent;
  padding: 6px 6px 0;
  font-weight: 700;
  color: #1f2937;
  cursor: pointer;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 72px;
}

.dental-chart-page .cat-image {
  width: 24px;
  height: 24px;
  object-fit: contain;
  display: block;
}

.dental-chart-page .cat-label {
  position: relative;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
  white-space: nowrap;
  line-height: 1.2;
}

.dental-chart-page .cat-underline {
  display: block;
  height: 3px;
  margin-top: 4px;
  width: 100%;
  border-radius: 999px;
}

.dental-chart-page .category-menu {
  position: absolute;
  top: calc(100% - 25px);
  left: 0;
  min-width: 220px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
  z-index: 20;
  padding: 8px;
  max-height: 275px;
  overflow: auto;
}

.dental-chart-page .category-menu button {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 8px 10px;
  border-radius: 8px;
  font-weight: 500;
  font-size: 12px;
  line-height: 1.3;
  color: #0f172a;
  cursor: pointer;
  display: block;
}

.dental-chart-page .category-menu button.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.dental-chart-page .category-menu button:hover {
  background: #f3f4f6;
}

.dental-chart-page .category-tab .category-menu.align-right {
  left: auto;
  right: 0;
}

.dental-chart-page .active-service {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: #1f2937;
}

.dental-chart-page .active-service .badge {
  background: #dc2626;
  color: #fff;
  padding: 6px 10px;
  border-radius: 999px;
}

.dental-chart-page .active-service .link {
  border: none;
  background: transparent;
  color: #6b7280;
  font-size: 16px;
  cursor: pointer;
}
</style>

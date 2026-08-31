<template>
  <span class="config-marker" data-test="config-marker-preview" :data-behavior="behavior || ''" v-html="svg"></span>
</template>

<script setup>
import { computed } from "vue"
import { markerPreviewSvg } from "../../../shared/marker_preview.js"

const props = defineProps({
  behavior: { type: String, default: "" },
  color: { type: String, default: "" },
  size: { type: Number, default: 44 },
  scale: { type: Number, default: 1 },
  frame: { type: Number, default: 1 },
})

const svg = computed(() => markerPreviewSvg(props.behavior, props.color || "#94a3b8", props.size, props.scale, props.frame))
</script>

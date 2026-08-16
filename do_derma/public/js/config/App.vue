<template>
  <div class="derma-config-page" data-test="derma-config-root">
    <aside class="config-rail">
      <div class="config-rail-title">{{ __("Configure") }}</div>
      <button
        v-for="tool in TOOLS"
        :key="tool.key"
        type="button"
        class="config-rail-item"
        :class="{ active: activeTool === tool.key }"
        :data-test="`config-rail-item-${tool.key}`"
        @click="activeTool = tool.key"
      >
        {{ __(tool.label) }}
      </button>
      <div class="config-rail-separator"></div>
      <a class="config-rail-item outbound" :href="ANNOTATION_TEMPLATE_LIST" data-test="config-rail-item-annotation-templates">
        {{ __("Annotation Templates") }} ↗
      </a>
    </aside>

    <section class="config-panel">
      <div v-if="loading" class="config-status" data-test="config-loading">{{ __("Loading configuration…") }}</div>
      <div v-else-if="loadError" class="config-status error" data-test="config-error">{{ loadError }}</div>
      <template v-else>
        <div v-if="failedSections.length" class="config-status warning" data-test="config-partial">
          {{ __("Some configuration could not be read: {0}", [failedSections.join(", ")]) }}
        </div>
        <BodyTemplatesPanel v-if="activeTool === 'body-templates'" :templates="bodyTemplates" />
        <div v-else class="config-status" data-test="config-placeholder">
          {{ __("This tool arrives in a later pass.") }}
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import BodyTemplatesPanel from "./panels/BodyTemplatesPanel.vue"

const __ = window.__ || ((txt) => txt)

const TOOLS = [
  { key: "body-templates", label: "Body Templates" },
  { key: "procedure-templates", label: "Procedure Templates" },
  { key: "categories", label: "Categories" },
  { key: "readiness", label: "Readiness" },
]
const ANNOTATION_TEMPLATE_LIST = "/app/annotation-template"

const activeTool = ref(TOOLS[0].key)
const bodyTemplates = ref([])
const failedSections = ref([])
const loading = ref(true)
const loadError = ref("")

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    const response = await frappe.call({ method: "do_derma.api.get_derma_config_overview" })
    const payload = response.message || {}
    bodyTemplates.value = payload.body_templates || []
    failedSections.value = payload.errors || []
  } catch (error) {
    console.warn("[do_derma] Failed to load configuration", error)
    loadError.value = __("Unable to load the derma configuration.")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

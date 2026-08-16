<template>
  <div class="config-section" data-test="config-readiness">
    <header class="config-section-head">
      <h3>{{ __("Readiness") }}</h3>
      <button
        type="button"
        class="btn btn-default btn-xs"
        data-test="config-edit-derma-settings"
        @click="editSettings"
      >
        {{ __("Derma Settings") }} →
      </button>
    </header>

    <dl class="config-facts">
      <div>
        <dt>{{ __("Blocked session completion") }}</dt>
        <dd data-test="config-readiness-enforcement" :data-mode="readiness.enforcement">
          {{ enforcementLabel }}
        </dd>
      </div>
      <div>
        <dt>{{ __("An open ToDo on a follow-up blocker") }}</dt>
        <dd data-test="config-readiness-todo-downgrade" :data-enabled="todoDowngrade">
          {{ todoDowngradeLabel }}
        </dd>
      </div>
    </dl>

    <div v-if="warnings.length" class="config-warnings">
      <span
        v-for="warning in warnings"
        :key="warning"
        class="config-badge warn"
        data-test="config-readiness-warning"
        :data-warning="warning"
      >
        {{ warningLabel(warning) }}
      </span>
    </div>

    <p class="config-status">
      {{ __("Read-only for now — change these on the Derma Settings form.") }}
    </p>

    <h4 class="config-subhead">{{ __("Incomplete features") }}</h4>
    <p v-if="!featureToggles.length" class="config-status" data-test="config-feature-toggles-empty">
      {{ __("No feature toggle could be read.") }}
    </p>
    <ul v-else class="config-toggles">
      <li
        v-for="toggle in featureToggles"
        :key="toggle.fieldname"
        data-test="config-feature-toggle"
        :data-toggle="toggle.fieldname"
        :data-enabled="toggle.enabled ? '1' : '0'"
      >
        <span class="config-badge" :class="{ warn: toggle.enabled }">
          {{ toggle.enabled ? __("On") : __("Off") }}
        </span>
        {{ toggleLabel(toggle.fieldname) }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { labelFor } from "../labels"

const __ = window.__ || ((txt) => txt)

const UNKNOWN = "—"

const ENFORCEMENT_LABELS = {
  Warn: "Warns, and completes anyway",
  Block: "Refused until the blockers are resolved",
}

const WARNING_LABELS = {
  completion_gate_is_client_side:
    "Only the chart enforces this — a direct API call completes a blocked session",
}

const TOGGLE_LABELS = {
  enable_whatsapp_consent: "WhatsApp consent actions",
  enable_lab_cases: "Lab case actions",
  enable_billing_sync: "Sync Billables action",
}

const props = defineProps({
  readiness: { type: Object, default: () => ({}) },
})

const warnings = computed(() => props.readiness.warnings || [])
const featureToggles = computed(() => props.readiness.feature_toggles || [])
const enforcementLabel = computed(() =>
  props.readiness.enforcement ? labelFor(ENFORCEMENT_LABELS, props.readiness.enforcement) : UNKNOWN
)

// A section that failed to load knows nothing, and "Still blocks" would be a stricter
// claim than the server makes.
const todoDowngrade = computed(() => {
  const rule = props.readiness.todo_downgrades_blockers
  if (rule === undefined || rule === null) return ""
  return rule ? "1" : "0"
})

const todoDowngradeLabel = computed(() => {
  if (!todoDowngrade.value) return UNKNOWN
  return todoDowngrade.value === "1" ? __("Downgrades it to a warning") : __("Still blocks")
})

function warningLabel(warning) {
  return labelFor(WARNING_LABELS, warning)
}

function toggleLabel(fieldname) {
  return labelFor(TOGGLE_LABELS, fieldname)
}

function editSettings() {
  frappe.set_route("Form", "Derma Settings")
}
</script>

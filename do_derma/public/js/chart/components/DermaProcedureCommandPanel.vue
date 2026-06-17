<template>
  <aside class="derma-procedure-command">
    <header>
      <div>
        <strong>{{ activeProcedure ? __("Active Procedure") : selectedTemplate ? __("Procedure Details") : __("Clinical Workflow") }}</strong>
        <small>{{ activeProcedure ? activeProcedureMeta : selectedTemplate ? selectedTemplateHint : __("Select a procedure to begin.") }}</small>
      </div>
      <button v-if="selectedTemplate || activeProcedure" type="button" class="ghost small" @click="$emit('clear')">
        {{ __("Clear") }}
      </button>
    </header>

    <div v-if="!selectedTemplate && !activeProcedure" class="command-empty">
      <strong>{{ __("Start with a derma procedure") }}</strong>
      <p>{{ __("Choose Botox, filler, laser, acne, lesion, biopsy, or another procedure from the palette.") }}</p>
    </div>

    <section v-else-if="selectedTemplate && !activeProcedure" class="command-section">
      <slot name="fields"></slot>
      <div class="readiness-list">
        <button
          v-for="item in readinessItems"
          :key="item.key"
          type="button"
          class="readiness-item"
          :class="item.state"
          @click="$emit('readiness', item)"
        >
          <b>{{ item.label }}</b>
          <small>{{ item.detail }}</small>
          <em v-if="item.action">{{ item.action }}</em>
        </button>
      </div>
    </section>

    <section v-else class="command-section active-procedure-summary">
      <dl>
        <div>
          <dt>{{ __("Procedure") }}</dt>
          <dd>{{ activeProcedureLabel }}</dd>
        </div>
        <div>
          <dt>{{ __("Status") }}</dt>
          <dd>{{ activeProcedure.status || __("Draft") }}</dd>
        </div>
        <div>
          <dt>{{ __("Evidence") }}</dt>
          <dd>{{ artifactText }}</dd>
        </div>
      </dl>
      <button type="button" class="ghost" @click="$emit('open-procedure')">{{ __("Open Clinical Procedure") }}</button>
    </section>

    <footer>
      <button
        v-if="selectedTemplate && !activeProcedure"
        type="button"
        class="primary"
        :disabled="!canCreateProcedure || procedureSaving"
        @click="$emit('create')"
      >
        {{ procedureSaving ? __("Creating...") : __("Create Draft Procedure") }}
      </button>
      <button v-if="activeProcedure" type="button" class="primary" @click="$emit('new-procedure')">
        {{ __("New Procedure") }}
      </button>
    </footer>
  </aside>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  selectedTemplate: { type: Object, default: null },
  selectedTemplateHint: { type: String, default: "" },
  activeProcedure: { type: Object, default: null },
  activeProcedureLabel: { type: String, default: "" },
  activeProcedureMeta: { type: String, default: "" },
  artifactText: { type: String, default: "" },
  readinessItems: { type: Array, default: () => [] },
  canCreateProcedure: { type: Boolean, default: false },
  procedureSaving: { type: Boolean, default: false },
})

defineEmits(["clear", "create", "new-procedure", "open-procedure", "readiness"])
</script>

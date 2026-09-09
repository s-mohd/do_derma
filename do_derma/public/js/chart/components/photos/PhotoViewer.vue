<template>
  <div class="photo-viewer" data-test="photo-viewer" @click.self="$emit('close')">
    <article class="photo-viewer-shell">
      <header>
        <div>
          <strong>{{ photo.stage }}</strong>
          <small>{{ [photo.dateLabel, photo.region, photo.procedure].filter(Boolean).join(" · ") }}</small>
        </div>
        <button type="button" class="ghost small" data-test="photo-viewer-close" @click="$emit('close')">{{ __("Close") }}</button>
      </header>

      <div class="photo-viewer-stage" :class="{ comparing: Boolean(partner) }">
        <figure>
          <div class="photo-zoom-frame" :class="{ zoomed: isZoomed }">
            <img :src="photo.image" :alt="photo.stage" @click="isZoomed = !isZoomed" />
          </div>
          <figcaption>{{ photo.dateLabel }} · {{ photo.stage }}</figcaption>
        </figure>
        <figure v-if="partner">
          <div class="photo-zoom-frame" :class="{ zoomed: isZoomed }">
            <img :src="partner.image" :alt="partner.stage" @click="isZoomed = !isZoomed" />
          </div>
          <figcaption>{{ partner.dateLabel }} · {{ partner.stage }}</figcaption>
        </figure>
      </div>

      <p v-if="isCrossRegion" class="photo-viewer-warning" data-test="photo-compare-warning">
        {{ __("These photos are of different regions.") }}
      </p>

      <footer>
        <div class="photo-stage-chips" v-if="canEdit">
          <span>{{ __("Stage") }}</span>
          <button
            v-for="stage in stages"
            :key="stage"
            type="button"
            :class="{ active: stage === photo.stage }"
            :data-test="`photo-stage-${stage.toLowerCase()}`"
            :disabled="Boolean(busy)"
            @click="$emit('retag', stage)"
          >
            {{ stage }}
          </button>
          <span v-if="busy === 'retag'" class="chart-spinner" role="status" :aria-label="__('Saving the stage')"></span>
        </div>
        <span v-else class="photo-stage-badge">{{ photo.stage }}</span>

        <div class="photo-viewer-actions">
          <button type="button" class="ghost small" data-test="photo-compare" @click="$emit('compare')">
            {{ partner ? __("Change Comparison") : __("Compare with…") }}
          </button>
          <button v-if="partner" type="button" class="ghost small" @click="$emit('swap')">{{ __("Swap") }}</button>
          <button
            v-if="canEdit"
            type="button"
            class="danger small"
            data-test="photo-delete"
            :disabled="Boolean(busy)"
            @click="$emit('delete')"
          >
            <span v-if="busy === 'delete'" class="chart-spinner" aria-hidden="true"></span>
            {{ busy === "delete" ? __("Deleting...") : __("Delete") }}
          </button>
        </div>
      </footer>
    </article>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  photo: { type: Object, required: true },
  partner: { type: Object, default: null },
  stages: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
  // Which photo write is in flight: "upload", "retag", "delete", or empty.
  busy: { type: String, default: "" },
})

defineEmits(["close", "retag", "delete", "compare", "swap"])

const isZoomed = ref(false)

const isCrossRegion = computed(() => {
  if (!props.partner) return false
  return Boolean(props.photo.region && props.partner.region && props.photo.region !== props.partner.region)
})
</script>

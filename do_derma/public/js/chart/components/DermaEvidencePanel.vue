<template>
  <aside class="derma-evidence-panel">
    <section>
      <header>
        <div>
          <strong>{{ activeProcedure ? __("Procedure Evidence") : __("Encounter Evidence") }}</strong>
          <small>{{ summary }}</small>
        </div>
        <button type="button" class="ghost small" :disabled="!allowUpload" @click="$emit('upload')">{{ __("Upload") }}</button>
      </header>

      <div class="evidence-stats">
        <span>
          <b>{{ annotationCount }}</b>
          <small>{{ __("drawings") }}</small>
        </span>
        <span>
          <b>{{ photoSetCount }}</b>
          <small>{{ __("photo sets") }}</small>
        </span>
      </div>
    </section>

    <section>
      <header>
        <strong>{{ __("Photo Compare") }}</strong>
        <small>{{ photoSummary }}</small>
      </header>
      <div v-if="photoCompare.before || photoCompare.after" class="photo-compare compact">
        <figure>
          <img v-if="photoCompare.before" :src="photoCompare.before.image" :alt="photoCompare.before.label" />
          <span v-else>{{ __("No previous") }}</span>
          <figcaption>{{ photoCompare.before?.label || __("Previous") }}</figcaption>
        </figure>
        <figure>
          <img v-if="photoCompare.after" :src="photoCompare.after.image" :alt="photoCompare.after.label" />
          <span v-else>{{ __("No current") }}</span>
          <figcaption>{{ photoCompare.after?.label || __("Today") }}</figcaption>
        </figure>
      </div>
      <p v-else class="panel-muted">{{ activeProcedure ? __("Upload procedure photos to compare before and after images.") : __("Upload encounter photos to build visual history.") }}</p>
    </section>

    <section v-if="photoSets.length">
      <header>
        <strong>{{ __("Saved Artifacts") }}</strong>
        <small>{{ photoSets.length }} {{ __("set(s)") }}</small>
      </header>
      <div class="artifact-strip">
        <button
          v-for="set in photoSets.slice(0, 6)"
          :key="set.name"
          type="button"
          :class="{ active: selectedPhotoSetName === set.name }"
          @click="$emit('select-photo-set', set.name)"
        >
          <img v-if="set.preview_image" :src="set.preview_image" :alt="set.name" loading="lazy" />
          <span v-else class="photo-empty-thumb"></span>
          <b>{{ set.set_type || set.name }}</b>
          <small>{{ set.body_view || set.body_region || set.creation }}</small>
        </button>
      </div>
    </section>
  </aside>
</template>

<script setup>
const __ = window.__ || ((txt) => txt)

defineProps({
  activeProcedure: { type: Object, default: null },
  annotationCount: { type: Number, default: 0 },
  photoSetCount: { type: Number, default: 0 },
  summary: { type: String, default: "" },
  photoSummary: { type: String, default: "" },
  photoCompare: { type: Object, default: () => ({ before: null, after: null }) },
  photoSets: { type: Array, default: () => [] },
  selectedPhotoSetName: { type: String, default: "" },
  allowUpload: { type: Boolean, default: false },
})

defineEmits(["upload", "select-photo-set"])
</script>

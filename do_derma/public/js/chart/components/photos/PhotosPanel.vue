<template>
  <section class="section-panel photos-panel" data-test="photos-panel">
    <header>
      <div class="photo-scope-row">
        <button
          v-for="scope in availableScopes"
          :key="scope.key"
          type="button"
          class="photo-scope-chip"
          :class="{ active: scope.key === activeScope }"
          :data-test="`photo-scope-${scope.key}`"
          @click="activeScope = scope.key"
        >
          {{ scope.label }}
        </button>
        <small data-test="photo-count">{{ photoCountText }}</small>
      </div>
      <button type="button" class="primary small" data-test="photos-upload" @click="$emit('upload')">
        {{ __("Upload Photo") }}
      </button>
    </header>

    <div v-if="requiresBeforeAfter" class="photo-required-row" data-test="photo-required-slots">
      <button
        v-for="slot in requiredSlots"
        :key="slot.stage"
        type="button"
        class="photo-required-slot"
        :class="{ filled: slot.filled }"
        :disabled="slot.filled"
        @click="$emit('upload')"
      >
        <b>{{ slot.stage }}</b>
        <small>{{ slot.filled ? __("captured") : __("required") }}</small>
      </button>
    </div>

    <p v-if="isPicking" class="photo-picking-hint" data-test="photo-picking-hint">
      {{ __("Pick the photo to compare with.") }}
      <button type="button" class="ghost small" @click="cancelPicking">{{ __("Cancel") }}</button>
    </p>

    <div v-if="visibleGroups.length" class="photo-roll" :class="{ picking: isPicking }">
      <section v-for="group in visibleGroups" :key="group.key" class="photo-roll-group">
        <h4>{{ group.label }}</h4>
        <div class="photo-roll-grid">
          <button
            v-for="photo in group.photos"
            :key="photo.id"
            type="button"
            class="photo-thumb"
            :data-test="`photo-thumb-${photo.name}`"
            @click="openPhoto(photo)"
          >
            <img
              v-if="!isBroken(photo.image)"
              :src="photo.image"
              :alt="photo.stage"
              loading="lazy"
              @error="markBroken(photo.image)"
            />
            <span v-else class="photo-thumb-missing">{{ __("Image unavailable") }}</span>
            <span class="photo-stage-badge">{{ photo.stage }}</span>
          </button>
        </div>
      </section>

    </div>

    <p v-if="!visibleGroups.length" class="panel-muted" data-test="photo-empty-state">
      {{ __("No photos in this scope yet. Upload to start the visual record.") }}
    </p>

    <button
      v-if="hasOlderGroups"
      type="button"
      class="ghost small"
      data-test="photo-load-older"
      @click="revealedOlderGroups += VISIBLE_GROUP_STEP"
    >
      {{ __("Load older visits") }}
    </button>

    <PhotoViewer
      v-if="openPhotoRow && !isPicking"
      :photo="openPhotoRow"
      :partner="partnerRow"
      :stages="RETAG_STAGES"
      :can-edit="openPhotoRow.isEditable && !readOnly"
      @close="closeViewer"
      @retag="(stage) => $emit('retag', { photo: openPhotoRow.name, stage })"
      @delete="requestDelete"
      @compare="startCompare"
      @swap="swapCompare"
    />
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue"

import PhotoViewer from "./PhotoViewer.vue"
import { useBrokenImages } from "../../../shared/broken_images.js"

const __ = window.__ || ((txt) => txt)

const { isBroken, markBroken } = useBrokenImages()

const RETAG_STAGES = ["Before", "After", "Visit"]
const OPPOSITE_STAGE = { Before: "After", After: "Before" }
const VISIBLE_GROUP_STEP = 3
const SCOPES = [
  { key: "procedure", label: __("This procedure") },
  { key: "visit", label: __("This visit") },
  { key: "all", label: __("All photos") },
]

const props = defineProps({
  photoSets: { type: Array, default: () => [] },
  previousPhotoSets: { type: Array, default: () => [] },
  activeProcedure: { type: Object, default: null },
  activeProcedureTreatments: { type: Array, default: () => [] },
  requiresBeforeAfter: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["upload", "retag", "delete"])

const activeScope = ref("visit")
const revealedOlderGroups = ref(0)
const openPhotoId = ref("")
const partnerId = ref("")
const isPicking = ref(false)

const availableScopes = computed(() =>
  SCOPES.filter((scope) => scope.key !== "procedure" || Boolean(props.activeProcedure?.name))
)

const todayPhotos = computed(() => flattenSets(props.photoSets, "today"))
const previousPhotos = computed(() => flattenSets(props.previousPhotoSets, "previous"))
const allPhotos = computed(() =>
  [...todayPhotos.value, ...previousPhotos.value].sort((left, right) =>
    String(right.capturedOn).localeCompare(String(left.capturedOn))
  )
)

const procedurePhotos = computed(() => {
  const procedure = props.activeProcedure?.name
  if (!procedure) return todayPhotos.value
  const treatments = new Set(props.activeProcedureTreatments.map((row) => row.name).filter(Boolean))
  return todayPhotos.value.filter(
    (photo) => photo.procedure === procedure || (photo.treatmentEntry && treatments.has(photo.treatmentEntry))
  )
})

const scopedPhotos = computed(() => {
  if (activeScope.value === "all") return allPhotos.value
  if (activeScope.value === "procedure") return procedurePhotos.value
  return todayPhotos.value
})

const photoGroups = computed(() => groupByDate(scopedPhotos.value))

const currentGroups = computed(() => photoGroups.value.filter((group) => !group.isPrevious))
const olderGroups = computed(() => photoGroups.value.filter((group) => group.isPrevious))

// This visit reads in full and earlier ones wait to be asked for, unless there is no
// current visit to read - then the first batch of older ones stands in for it.
const revealedOlder = computed(() =>
  currentGroups.value.length ? revealedOlderGroups.value : Math.max(revealedOlderGroups.value, VISIBLE_GROUP_STEP)
)

const visibleGroups = computed(() => [...currentGroups.value, ...olderGroups.value.slice(0, revealedOlder.value)])

const hasOlderGroups = computed(() => olderGroups.value.length > revealedOlder.value)

const photoCountText = computed(() => `${scopedPhotos.value.length} ${__("photo(s)")}`)

const requiredSlots = computed(() =>
  ["Before", "After"].map((stage) => ({
    stage,
    filled: procedurePhotos.value.some((photo) => photo.stage === stage),
  }))
)

const openPhotoRow = computed(() => allPhotos.value.find((photo) => photo.id === openPhotoId.value) || null)
const partnerRow = computed(() => allPhotos.value.find((photo) => photo.id === partnerId.value) || null)

// A deleted or refreshed photo must not leave the viewer showing a row that is gone.
watch(allPhotos, () => {
  if (openPhotoId.value && !openPhotoRow.value) closeViewer()
  if (partnerId.value && !partnerRow.value) partnerId.value = ""
})

watch(activeScope, () => (revealedOlderGroups.value = 0))

function groupByDate(photos) {
  const groups = []
  const byKey = new Map()
  for (const photo of photos) {
    if (!byKey.has(photo.dateLabel)) {
      const group = { key: photo.dateLabel, label: photo.dateLabel, isPrevious: photo.isPrevious, photos: [] }
      byKey.set(photo.dateLabel, group)
      groups.push(group)
    }
    byKey.get(photo.dateLabel).photos.push(photo)
  }
  return groups
}

function flattenSets(sets, period) {
  const rows = []
  for (const set of sets || []) {
    for (const photo of set.photos || []) {
      if (!photo?.image) continue
      rows.push({
        id: `${set.name}::${photo.name}`,
        name: photo.name,
        image: photo.image,
        stage: photo.photo_type || "Visit",
        region: photo.body_region || set.body_region || set.body_view || "",
        procedure: set.clinical_procedure || "",
        treatmentEntry: photo.treatment_entry || set.treatment_entry || "",
        capturedOn: set.creation || set.modified || "",
        dateLabel: formatDate(set.creation || set.modified) || __("Undated"),
        isEditable: period === "today",
        isPrevious: period === "previous",
      })
    }
  }
  return rows
}

function openPhoto(photo) {
  if (isPicking.value) {
    partnerId.value = photo.id
    isPicking.value = false
    return
  }
  openPhotoId.value = photo.id
  partnerId.value = ""
}

function closeViewer() {
  openPhotoId.value = ""
  partnerId.value = ""
}

function startCompare() {
  if (partnerRow.value) {
    partnerId.value = ""
    isPicking.value = true
    return
  }
  const partner = findPartner(openPhotoRow.value)
  if (partner) {
    partnerId.value = partner.id
    return
  }
  isPicking.value = true
}

function cancelPicking() {
  isPicking.value = false
}

function swapCompare() {
  const current = openPhotoId.value
  openPhotoId.value = partnerId.value
  partnerId.value = current
}

function findPartner(photo) {
  const opposite = OPPOSITE_STAGE[photo?.stage]
  if (!opposite) return null
  return (
    allPhotos.value.find(
      (row) => row.id !== photo.id && row.stage === opposite && row.region === photo.region
    ) || null
  )
}

function requestDelete() {
  const photo = openPhotoRow.value
  if (!photo) return
  emit("delete", { photo: photo.name })
}

function formatDate(value) {
  if (!value) return ""
  // Sets carry a timestamp; the roll groups by the day it was taken.
  const day = String(value).slice(0, 10)
  return window.frappe?.datetime?.str_to_user?.(day) || day
}
</script>

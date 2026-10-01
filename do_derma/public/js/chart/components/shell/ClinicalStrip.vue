<template>
  <DegradedSectionNotice
    v-if="isDegraded"
    section="clinical-profile"
    :label="__('clinical profile')"
    @retry="$emit('retry')"
  />
  <section v-else-if="profile" class="clinical-strip" data-test="clinical-strip">
    <div class="clinical-strip-columns">
      <div class="clinical-strip-column" data-test="clinical-strip-allergies">
        <h3>⚠ {{ __("Allergies") }}</h3>
        <div class="clinical-strip-chips">
          <span v-for="allergy in profile.allergies" :key="allergy.allergen" class="clinical-strip-chip" data-tone="danger">
            {{ allergy.allergen }}
          </span>
          <span v-if="!profile.allergies.length" class="clinical-strip-chip">{{ allergyEmptyText }}</span>
        </div>
      </div>
      <div class="clinical-strip-column" data-test="clinical-strip-history">
        <h3>{{ __("Medical History") }}</h3>
        <div class="clinical-strip-chips">
          <span
            v-for="condition in profile.conditions"
            :key="condition.name"
            class="clinical-strip-chip"
            :data-tone="condition.is_critical ? 'caution' : ''"
            :title="condition.note || ''"
          >{{ condition.name }}</span>
          <span v-if="!profile.conditions.length" class="clinical-strip-chip">{{ __("Not recorded") }}</span>
        </div>
      </div>
      <div class="clinical-strip-column" data-test="clinical-strip-medications">
        <h3>{{ __("Medications") }}</h3>
        <div class="clinical-strip-chips">
          <span
            v-for="medication in profile.medications"
            :key="medication.name"
            class="clinical-strip-chip"
            :data-tone="medication.risk_class ? 'caution' : ''"
            :title="medication.risk_class || ''"
          >{{ medication.name }}</span>
          <span v-if="!profile.medications.length" class="clinical-strip-chip">{{ __("Not recorded") }}</span>
        </div>
      </div>
    </div>
    <footer class="clinical-strip-footer">
      <span v-if="surgeriesText"><b>{{ __("Surgical") }}</b> {{ surgeriesText }}</span>
      <span v-if="habitsText"><b>{{ __("Habits") }}</b> {{ habitsText }}</span>
      <span class="clinical-strip-reviewed">{{ reviewedText }}</span>
      <button
        v-if="hasHistoryDrawer"
        type="button"
        class="clinical-strip-link"
        data-test="clinical-strip-update-history"
        @click="openHistory"
      >{{ __("Update history") }} →</button>
    </footer>
  </section>
</template>

<script setup>
import { computed } from "vue"
import DegradedSectionNotice from "../DegradedSectionNotice.vue"

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  profile: { type: Object, default: null },
  isDegraded: { type: Boolean, default: false },
  patient: { type: String, default: "" },
})

defineEmits(["retry"])

const allergyEmptyText = computed(() =>
  props.profile?.allergy_status === "none_known" ? __("None known") : __("Not recorded")
)
const surgeriesText = computed(() => (props.profile?.surgeries || []).map((row) => row.name).join(", "))
const habitsText = computed(() =>
  (props.profile?.habits || []).map((row) => (row.note ? `${row.habit}: ${row.note}` : row.habit)).join("; ")
)
const reviewedText = computed(() => {
  const date = props.profile?.reviewed_on?.date
  if (!date) return __("History not yet reviewed")
  return __("Reviewed {0}").replace("{0}", window.frappe?.datetime?.str_to_user?.(date) || date)
})
const hasHistoryDrawer = computed(() => typeof window.do_health?.openMedicalHistoryPanel === "function")

function openHistory() {
  window.do_health.openMedicalHistoryPanel(props.patient)
}
</script>

<style scoped>
.clinical-strip {
  background: var(--chart-surface);
  border: 1px solid var(--chart-border);
  border-radius: var(--chart-radius);
  box-shadow: var(--chart-shadow);
  overflow: hidden;
}

.clinical-strip-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.clinical-strip-column {
  padding: 14px 16px;
  min-width: 0;
}

.clinical-strip-column + .clinical-strip-column {
  border-left: 1px solid var(--chart-border);
}

.clinical-strip-column h3 {
  margin: 0 0 8px;
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.clinical-strip-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.clinical-strip-chip {
  padding: 3px 10px;
  border: 1px solid var(--chart-border-strong);
  border-radius: 999px;
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.clinical-strip-chip[data-tone="danger"] {
  background: var(--chart-danger-soft);
  border-color: var(--chart-danger-border);
  color: var(--chart-danger-text);
}

.clinical-strip-chip[data-tone="caution"] {
  background: var(--chart-caution-soft);
  border-color: var(--chart-caution-border);
  color: var(--chart-caution-text);
}

.clinical-strip-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 20px;
  padding: 10px 16px;
  border-top: 1px solid var(--chart-border);
  background: var(--chart-surface-muted);
  color: var(--chart-text-soft);
  font-size: 12px;
}

.clinical-strip-footer b {
  color: var(--chart-muted);
  font-weight: 500;
  margin-right: 4px;
}

.clinical-strip-reviewed {
  margin-left: auto;
  color: var(--chart-muted);
}

.clinical-strip-link {
  border: 0;
  background: transparent;
  color: var(--chart-blue);
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .clinical-strip-columns {
    grid-template-columns: minmax(0, 1fr);
  }

  .clinical-strip-column + .clinical-strip-column {
    border-left: 0;
    border-top: 1px solid var(--chart-border);
  }
}
</style>

<template>
  <section class="voice-scribe" :data-state="state" data-test="voice-scribe">
    <div class="voice-scribe-row">
      <button
        v-if="state === 'idle' || state === 'ready' || state === 'failed'"
        type="button"
        class="primary small"
        data-test="voice-start"
        @click="startRecording"
      >
        <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8" />
        </svg>
        {{ state === "idle" ? __("Dictate") : __("Record again") }}
      </button>
      <button v-else-if="state === 'recording'" type="button" class="voice-stop small" data-test="voice-stop" @click="stopRecording">
        <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
        {{ __("Stop") }} · {{ clock }}
      </button>
      <button v-else type="button" class="ghost small" disabled>
        <span class="voice-spinner" aria-hidden="true"></span>
        {{ state === "transcribing" ? __("Transcribing...") : __("Writing note...") }}
      </button>
      <div v-if="state === 'recording'" class="voice-meter" :data-zone="meterZone" data-test="voice-meter" :title="meterHint">
        <span v-for="n in METER_BARS" :key="n" class="voice-bar" :class="{ on: n <= litBars }"></span>
        <em>{{ meterHint }}</em>
      </div>

      <select v-if="microphones.length > 1 && state !== 'recording'" v-model="deviceId" class="voice-mic" :title="__('Microphone')" data-test="voice-mic">
        <option v-for="mic in microphones" :key="mic.deviceId" :value="mic.deviceId">{{ mic.label || __("Microphone") }}</option>
      </select>

      <small class="voice-hint">
        <template v-if="state === 'idle'">{{ __("Record the visit (English / Arabic); the AI drafts the note in the current format for you to review.") }}</template>
        <template v-else-if="state === 'recording' && silenceWarning">
          <span class="voice-warning" data-test="voice-silence">{{ silenceWarning }}</span>
        </template>
        <template v-else-if="state === 'recording'">{{ __("Recording. Speak naturally; press Stop when the visit ends.") }}</template>
        <template v-else-if="state === 'ready'">{{ __("Draft filled below. Edit anything, then Save.") }}</template>
        <template v-else-if="state === 'failed'">{{ error }}</template>
      </small>
    </div>

    <form v-if="hasNote && state !== 'recording'" class="voice-refine" data-test="voice-refine" @submit.prevent="refine">
      <input v-model="instruction" type="text" :placeholder="__('Ask the AI to adjust the note, e.g. add a 2-week follow-up and mention sun protection')" :disabled="refining" />
      <button type="submit" class="ghost small" :disabled="refining || instruction.trim().length < 3">
        <span v-if="refining" class="voice-spinner" aria-hidden="true"></span>{{ refining ? __("Adjusting...") : __("Adjust") }}
      </button>
    </form>

    <div v-if="result" class="voice-result" data-test="voice-result">
      <div class="voice-result-head">
        <b>{{ result.diagnosis || __("No diagnosis suggested") }}</b>
        <code v-if="result.icd10">{{ result.icd10 }}</code>
      </div>
      <details v-if="result.followup_en || result.followup_ar">
        <summary>{{ __("WhatsApp follow-up for the patient") }}</summary>
        <div class="voice-followups">
          <div v-if="result.followup_en">
            <pre>{{ result.followup_en }}</pre>
            <button type="button" class="ghost small" @click="copy(result.followup_en)">{{ __("Copy English") }}</button>
          </div>
          <div v-if="result.followup_ar" dir="rtl">
            <pre>{{ result.followup_ar }}</pre>
            <button type="button" class="ghost small" @click="copy(result.followup_ar)">{{ __("نسخ العربية") }}</button>
          </div>
        </div>
      </details>
      <details v-if="result.soap_ar">
        <summary>{{ __("Arabic note") }}</summary>
        <pre dir="rtl">{{ result.soap_ar }}</pre>
      </details>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import {
  GOOD_RMS,
  HEARD_RMS,
  LOUD_PEAK,
  createVoiceRecorder,
  listMicrophones,
  rememberDeviceId,
  rememberedDeviceId,
} from "../../voice/voice_recorder.js"

const METER_BARS = 12
// Seconds of silence before the doctor is told the mic is not picking anything up.
const SILENCE_WARN_SEC = 6

const __ = window.__ || ((txt) => txt)

const props = defineProps({
  // {encounter, appointment, patient} - same shape the chart sends to every endpoint
  context: { type: Object, required: true },
  maxMinutes: { type: Number, default: 20 },
  hasNote: { type: Boolean, default: false },
})
const emit = defineEmits(["fill", "refined"])

const instruction = ref("")
const refining = ref(false)

async function refine() {
  refining.value = true
  error.value = ""
  try {
    const response = await frappe.call({ method: "do_derma.voice.refine_note", args: { ...props.context, instruction: instruction.value } })
    emit("refined", response.message)
    instruction.value = ""
    window.frappe?.show_alert?.({ message: __("Note adjusted and saved as a draft."), indicator: "green" })
  } catch (err) {
    window.frappe?.show_alert?.({ message: String(err?.message || __("The AI could not adjust the note.")).replace(/<[^>]+>/g, ""), indicator: "red" }, 8)
  } finally {
    refining.value = false
  }
}

const state = ref("idle") // idle | recording | transcribing | generating | ready | failed
const error = ref("")
const result = ref(null)
const clock = ref("0:00")
const microphones = ref([])
const deviceId = ref(rememberedDeviceId())

const meter = ref({ level: 0, peak: 0, silentSec: 0 })
const silenceWarned = ref(false)

const recorder = createVoiceRecorder()
let ticker = null
let meterTicker = null

const litBars = computed(() => Math.min(METER_BARS, Math.round((meter.value.level / (GOOD_RMS * 2)) * METER_BARS)))
const meterZone = computed(() => {
  const { level, peak } = meter.value
  if (peak >= LOUD_PEAK) return "loud"
  if (level < HEARD_RMS) return "quiet"
  if (level < GOOD_RMS) return "low"
  return "good"
})
const meterHint = computed(
  () =>
    ({
      quiet: __("No sound"),
      low: __("Low - bring the mic closer"),
      good: __("Good level"),
      loud: __("Too loud - move the mic away"),
    })[meterZone.value]
)
const silenceWarning = computed(() =>
  meter.value.silentSec >= SILENCE_WARN_SEC
    ? __("Nothing has been heard for {0} s. Bring the mic closer or check the selected microphone.").replace("{0}", Math.floor(meter.value.silentSec))
    : ""
)

onMounted(async () => {
  try {
    microphones.value = await listMicrophones()
  } catch {
    microphones.value = []
  }
})

onBeforeUnmount(() => {
  clearInterval(ticker)
  clearInterval(meterTicker)
  recorder.cancel()
})

async function startRecording() {
  error.value = ""
  result.value = null
  try {
    await recorder.start(deviceId.value)
    rememberDeviceId(deviceId.value)
    state.value = "recording"
    ticker = setInterval(() => {
      const s = recorder.elapsedSec()
      clock.value = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
      if (s >= props.maxMinutes * 60) {
        window.frappe?.show_alert?.({ message: __("Maximum recording length reached; transcribing now."), indicator: "orange" }, 6)
        stopRecording()
      }
    }, 500)
    silenceWarned.value = false
    meterTicker = setInterval(() => {
      meter.value = recorder.meter()
      if (meter.value.silentSec >= SILENCE_WARN_SEC && !silenceWarned.value) {
        silenceWarned.value = true
        window.frappe?.show_alert?.({ message: __("The microphone is not picking up any voice."), indicator: "orange" }, 6)
      }
    }, 120)
  } catch (err) {
    fail(err?.message || __("Microphone permission was refused."))
  }
}

async function stopRecording() {
  clearInterval(ticker)
  clearInterval(meterTicker)
  state.value = "transcribing"
  let blob
  try {
    ;({ blob } = await recorder.stop())
    const text = await transcribe(blob)
    if (!text) throw new Error(__("Nothing was heard. Check the microphone and try again."))
    state.value = "generating"
    const queued = await frappe.call({ method: "do_derma.voice.queue_note", args: { ...props.context, transcript: text } })
    result.value = await waitForJob(queued.message?.job)
    emit("fill", result.value)
    state.value = "ready"
    attachAudio(blob, result.value?.encounter || props.context.encounter)
  } catch (err) {
    fail(err?.message || err?._server_messages || __("Voice note failed."))
  }
}

// The note is written by a background job; poll every 3 s (up to 5 min).
async function waitForJob(job) {
  if (!job) throw new Error(__("The note job was not started."))
  for (let i = 0; i < 100; i++) {
    const status = await frappe.call({ method: "do_derma.voice.job_status", args: { job } })
    const m = status.message || {}
    if (m.status === "done") return m.result
    if (m.status === "failed") throw new Error(m.error || __("The AI note failed."))
    if (m.status === "unknown") throw new Error(__("The note job expired."))
    await new Promise((r) => setTimeout(r, 3000))
  }
  throw new Error(__("The AI is taking too long. Try again in a minute."))
}

async function transcribe(blob) {
  const form = new FormData()
  form.append("audio", blob, `consultation-${Date.now()}.wav`)
  if (props.context.encounter) form.append("encounter", props.context.encounter)
  const response = await fetch("/api/method/do_derma.voice.transcribe", {
    method: "POST",
    headers: { "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "", Accept: "application/json" },
    body: form,
    signal: AbortSignal.timeout ? AbortSignal.timeout(240000) : undefined,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(serverMessage(data) || `${__("Transcription failed")} (${response.status})`)
  return (data.message?.text || "").trim()
}

// Keep the recording on the encounter for audit - private File, best effort.
function attachAudio(blob, encounter) {
  if (!encounter) return
  const form = new FormData()
  form.append("file", blob, `consultation-${Date.now()}.wav`)
  form.append("is_private", "1")
  form.append("doctype", "Patient Encounter")
  form.append("docname", encounter)
  fetch("/api/method/upload_file", {
    method: "POST",
    headers: { "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "", Accept: "application/json" },
    body: form,
  }).catch(() => {})
}

function serverMessage(data) {
  try {
    const raw = data?._server_messages ? JSON.parse(data._server_messages) : []
    const first = raw[0] ? JSON.parse(raw[0]) : null
    return first?.message || data?.exception || ""
  } catch {
    return data?.exception || ""
  }
}

function fail(message) {
  clearInterval(ticker)
  clearInterval(meterTicker)
  recorder.cancel()
  error.value = String(message).replace(/<[^>]+>/g, "")
  state.value = "failed"
}

function copy(text) {
  navigator.clipboard?.writeText(text).then(
    () => window.frappe?.show_alert?.({ message: __("Copied"), indicator: "green" }),
    () => {}
  )
}
</script>

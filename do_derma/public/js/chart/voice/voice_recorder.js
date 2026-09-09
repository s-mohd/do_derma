export const SAMPLE_RATE = 16000
const DEVICE_KEY = "derma_voice_mic"
// Below this RMS the buffer counts as silence (room noise on a laptop mic is ~0.003).
export const HEARD_RMS = 0.012
// A good speaking level; above LOUD the signal is near clipping - mic too close.
export const GOOD_RMS = 0.03
export const LOUD_PEAK = 0.9

export function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeString = (offset, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }
  writeString(0, "RIFF")
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(8, "WAVE")
  writeString(12, "fmt ")
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, "data")
  view.setUint32(40, samples.length * 2, true)
  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: "audio/wav" })
}

export function downsample(input, inputRate, outputRate) {
  if (inputRate === outputRate) return input
  const ratio = inputRate / outputRate
  const length = Math.ceil(input.length / ratio)
  const output = new Float32Array(length)
  for (let i = 0; i < length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), input.length)
    let sum = 0
    let count = 0
    for (let j = start; j < end; j++) {
      sum += input[j]
      count++
    }
    output[i] = count ? sum / count : 0
  }
  return output
}

export function rememberedDeviceId() {
  try {
    return localStorage.getItem(DEVICE_KEY) || ""
  } catch {
    return ""
  }
}

export function rememberDeviceId(id) {
  try {
    if (id) localStorage.setItem(DEVICE_KEY, id)
  } catch {
    /* private mode */
  }
}

export async function listMicrophones() {
  if (!navigator.mediaDevices?.enumerateDevices) return []
  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices.filter((d) => d.kind === "audioinput")
}

export function createVoiceRecorder() {
  let stream = null
  let context = null
  let processor = null
  let source = null
  let chunks = []
  let inputRate = SAMPLE_RATE
  let startedAt = 0
  let level = 0 // RMS of the latest buffer, 0..1
  let peak = 0
  let lastHeardAt = 0

  async function start(deviceId = rememberedDeviceId()) {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access is not available in this browser.")
    const audio = deviceId ? { deviceId: { exact: deviceId } } : true
    stream = await navigator.mediaDevices.getUserMedia({ audio })
    const track = stream.getAudioTracks()[0]
    if (track?.getSettings?.().deviceId) rememberDeviceId(track.getSettings().deviceId)
    context = new (window.AudioContext || window.webkitAudioContext)()
    inputRate = context.sampleRate
    source = context.createMediaStreamSource(stream)
    // ScriptProcessorNode is deprecated but still universal; an AudioWorklet needs a
    // separately served module file, which Frappe's bundler does not give us for free.
    processor = context.createScriptProcessor(4096, 1, 1)
    chunks = []
    processor.onaudioprocess = (event) => {
      const samples = event.inputBuffer.getChannelData(0)
      chunks.push(new Float32Array(samples))
      measure(samples)
    }
    source.connect(processor)
    processor.connect(context.destination)
    startedAt = lastHeardAt = Date.now()
    level = peak = 0
  }

  function measure(samples) {
    let sum = 0
    let max = 0
    for (let i = 0; i < samples.length; i++) {
      const v = samples[i]
      sum += v * v
      if (v > max) max = v
      else if (-v > max) max = -v
    }
    level = Math.sqrt(sum / samples.length)
    peak = max
    if (level > HEARD_RMS) lastHeardAt = Date.now()
  }

  async function stop() {
    const total = chunks.reduce((n, c) => n + c.length, 0)
    const merged = new Float32Array(total)
    let offset = 0
    for (const chunk of chunks) {
      merged.set(chunk, offset)
      offset += chunk.length
    }
    cleanup()
    const durationSec = total / inputRate
    return { blob: encodeWAV(downsample(merged, inputRate, SAMPLE_RATE), SAMPLE_RATE), durationSec }
  }

  function cleanup() {
    try {
      processor?.disconnect()
      source?.disconnect()
    } catch {
      /* already torn down */
    }
    stream?.getTracks().forEach((t) => t.stop())
    context?.close().catch(() => {})
    processor = source = stream = context = null
    chunks = []
  }

  function elapsedSec() {
    return startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0
  }

  // Snapshot for the meter: level/peak now, and how long since speech was last heard.
  function meter() {
    return { level, peak, silentSec: lastHeardAt ? (Date.now() - lastHeardAt) / 1000 : 0 }
  }

  return { start, stop, cancel: cleanup, elapsedSec, meter }
}

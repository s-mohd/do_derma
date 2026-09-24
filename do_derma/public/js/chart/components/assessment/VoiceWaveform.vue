<template>
  <div class="voice-waveform" :data-paused="paused" data-test="voice-waveform">
    <canvas ref="canvas"></canvas>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue"

// Speech peaks sit around 0.05-0.5; the square root lifts quiet speech so it stays visible.
const FULL_SCALE_PEAK = 0.6
const BAR_STEP = 4
const BAR_WIDTH = 1.5

const props = defineProps({
  peaks: { type: Function, required: true },
  paused: { type: Boolean, default: false },
})

const canvas = ref(null)
let frame = 0

onMounted(() => {
  frame = requestAnimationFrame(draw)
})

onBeforeUnmount(() => cancelAnimationFrame(frame))

function draw() {
  const element = canvas.value
  if (!element) return
  const ratio = window.devicePixelRatio || 1
  const width = element.clientWidth
  const height = element.clientHeight
  if (element.width !== width * ratio || element.height !== height * ratio) {
    element.width = width * ratio
    element.height = height * ratio
  }
  const context = element.getContext("2d")
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  context.clearRect(0, 0, width, height)

  const style = getComputedStyle(element)
  const barColor = style.getPropertyValue("--wave-bar").trim() || "#ef4444"
  const headColor = style.getPropertyValue("--wave-head").trim() || "#ef4444"
  const middle = height / 2
  const peaks = props.peaks()
  // The playhead follows the newest bar until 80% of the width, then the bars scroll left.
  const playhead = Math.min(peaks.length * BAR_STEP, Math.floor(width * 0.8)) + 3
  const visible = Math.min(peaks.length, Math.floor(playhead / BAR_STEP))
  const start = peaks.length - visible
  const offset = playhead - visible * BAR_STEP

  context.fillStyle = barColor
  for (let i = 0; i < visible; i++) {
    const amplitude = Math.min(1, Math.sqrt(peaks[start + i] / FULL_SCALE_PEAK))
    const bar = Math.max(1, amplitude * (height - 6))
    context.fillRect(offset + i * BAR_STEP, middle - bar / 2, BAR_WIDTH, bar)
  }

  context.fillStyle = headColor
  context.fillRect(playhead, 0, 1.5, height)
  context.beginPath()
  context.arc(playhead + 0.75, 2.5, 2.5, 0, Math.PI * 2)
  context.arc(playhead + 0.75, height - 2.5, 2.5, 0, Math.PI * 2)
  context.fill()

  frame = requestAnimationFrame(draw)
}
</script>

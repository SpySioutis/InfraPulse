<template>
  <svg :viewBox="`0 0 ${width} ${height}`" class="chart" role="img" :aria-label="label">
    <line
      v-for="tick in yTicks"
      :key="tick"
      :x1="padL"
      :x2="width - padR"
      :y1="y(tick)"
      :y2="y(tick)"
      class="grid-line"
    />
    <text
      v-for="tick in yTicks"
      :key="`y-${tick}`"
      :x="padL - 4"
      :y="y(tick) + 3"
      text-anchor="end"
      class="y-label"
    >{{ tick }}</text>
    <polyline :points="linePoints" class="line" />
    <g v-if="showSecond">
      <polyline :points="secondLinePoints" class="line-second" />
    </g>
    <text
      v-for="(lbl, i) in xLabels"
      :key="`x-${i}`"
      :x="lbl.x"
      :y="height - 4"
      class="x-label"
    >{{ lbl.text }}</text>
  </svg>
  <div v-if="showSecond" class="legend">
    <span class="swatch total"></span> {{ primaryLabel }}
    <span class="swatch second"></span> {{ secondLabel }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Point {
  key: string
  total: number
  second?: number
  xLabel?: string
}

const props = withDefaults(
  defineProps<{ points: Point[]; label: string; showSecond?: boolean; primaryLabel?: string; secondLabel?: string; unit?: string }>(),
  { showSecond: false, primaryLabel: 'value', secondLabel: '', unit: '' },
)

const width = 640
const height = 180
const padL = 34
const padR = 8
const padTop = 8
const padBottom = 20

const maxValue = computed(() => Math.max(1, ...props.points.flatMap((p) => [p.total, p.second ?? 0])) * 1.1)

const y = (value: number) =>
  padTop + (height - padTop - padBottom) * (1 - value / maxValue.value)

const yTicks = computed(() => {
  const max = maxValue.value
  const step = Math.max(max / 4, 0.1)
  const ticks: number[] = []
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 10) / 10)
  return ticks.slice(0, 6)
})

function toPoints(get: (p: Point) => number): string {
  const n = props.points.length
  if (!n) return ''
  const slot = (width - padL - padR) / Math.max(1, n - 1 || 1)
  return props.points
    .map((p, i) => `${(padL + slot * i).toFixed(1)},${y(get(p)).toFixed(1)}`)
    .join(' ')
}

const linePoints = computed(() => toPoints((p) => p.total))
const secondLinePoints = computed(() => toPoints((p) => p.second ?? 0))

const xLabels = computed(() => {
  const n = props.points.length
  if (!n) return []
  const slot = (width - padL - padR) / Math.max(1, n - 1 || 1)
  const idx = new Set<number>()
  for (let i = 0; i < n; i += Math.max(1, Math.ceil(n / 5))) idx.add(i)
  if (n > 1) idx.add(n - 1)
  return [...idx].map((i) => ({
    x: padL + slot * i - 10,
    text: props.points[i].xLabel ?? props.points[i].key,
  }))
})
</script>

<style scoped>
.chart { width: 100%; height: auto; display: block; }
.grid-line { stroke: var(--border-soft); stroke-width: 1; }
.line { fill: none; stroke: var(--accent); stroke-width: 1.8; }
.line-second { fill: none; stroke: var(--info); stroke-width: 1.4; stroke-dasharray: 4 3; }
.x-label { fill: var(--text-faint); font-size: 10px; }
.y-label { fill: var(--text-faint); font-size: 10px; }
.legend { display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--text-dim); margin-top: 6px; }
.swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.swatch.total { background: var(--accent); }
.swatch.second { background: var(--info); margin-left: 10px; }
</style>

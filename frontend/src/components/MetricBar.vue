<template>
  <div class="mbar">
    <span class="lbl">{{ label }}</span>
    <span class="track"><span :class="barClass(value, warn, crit)" :style="{ width: `${Math.min(100, Math.max(0, value))}%` }"></span></span>
    <span class="val">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { barClass } from '../utils/health'

const props = withDefaults(
  defineProps<{ label: string; value: number; text?: string; warn?: number; crit?: number }>(),
  { text: '', warn: 75, crit: 90 },
)
const text = computed(() => props.text || `${props.value.toFixed(1)}%`)
</script>

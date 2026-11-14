<template>
  <div class="stat">
    <div class="label">{{ label }}</div>
    <div class="value" :class="tone">{{ formatted }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '../utils/format'

const props = withDefaults(
  defineProps<{ label: string; value: number | string; tone?: string }>(),
  { tone: '' },
)
const formatted = computed(() =>
  typeof props.value === 'number' ? formatNumber(props.value) : props.value,
)
</script>

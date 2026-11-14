<template>
  <div class="page-head">
    <h1>Overview</h1>
    <span class="sub">infrastructure health at a glance</span>
    <span class="spacer" style="flex: 1"></span>
    <RouterLink to="/metrics"><button>Historical metrics</button></RouterLink>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div v-if="!loading && summary && summary.servers === 0">
    <EmptyState title="No servers registered">
      Register a server and install the InfraPulse agent to start monitoring.
      <br />
      <RouterLink to="/servers">Go to Servers</RouterLink>
    </EmptyState>
  </div>

  <template v-else>
    <div class="stats" v-if="summary">
      <StatCard label="Servers" :value="summary.servers" />
      <StatCard label="Online" :value="summary.online" tone="ok" />
      <StatCard label="Offline" :value="summary.offline" tone="danger" />
      <StatCard label="Warning" :value="summary.warning" tone="warn" />
      <StatCard label="Critical" :value="summary.critical" tone="danger" />
      <StatCard label="Active alerts" :value="summary.active_alerts" tone="warn" />
      <StatCard label="Avg CPU" :value="summary.avg_cpu_pct === null ? '—' : `${summary.avg_cpu_pct}%`" />
      <StatCard label="Avg memory" :value="summary.avg_mem_pct === null ? '—' : `${summary.avg_mem_pct}%`" />
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px">
      <div class="panel">
        <h2>Recent alerts</h2>
        <table class="grid" v-if="summary && summary.recent_alerts.length">
          <tbody>
            <tr v-for="a in summary.recent_alerts" :key="a.id" class="rowlink" @click="$router.push('/alerts')">
              <td><span :class="severityClass(a.severity)">{{ a.severity }}</span></td>
              <td class="ellipsis" :title="a.message">{{ truncate(a.message, 80) }}</td>
              <td class="mono dim nowrap">{{ formatDateTime(a.triggered_at) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="No alerts" hint="Threshold breaches and offline servers will appear here." />
      </div>

      <div class="panel">
        <h2>Recent activity</h2>
        <table class="grid" v-if="summary && summary.recent_activity.length">
          <tbody>
            <tr v-for="a in summary.recent_activity" :key="a.id">
              <td class="mono dim nowrap">{{ formatDateTime(a.created_at) }}</td>
              <td>{{ a.username ?? 'system' }}</td>
              <td class="mono">{{ a.action }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="No activity yet" />
      </div>
    </div>
  </template>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type DashboardSummary } from '../api/client'
import { formatDateTime } from '../utils/format'
import { severityClass } from '../utils/health'
import EmptyState from '../components/EmptyState.vue'
import StatCard from '../components/StatCard.vue'

const loading = ref(true)
const error = ref('')
const summary = ref<DashboardSummary | null>(null)

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

onMounted(async () => {
  try {
    summary.value = (await api.get('/dashboard/summary')).data
  } catch {
    error.value = 'Could not load overview data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
})
</script>

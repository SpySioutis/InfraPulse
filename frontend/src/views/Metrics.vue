<template>
  <div class="page-head">
    <h1>Metrics</h1>
    <span class="sub">historical series and server comparison</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div class="panel">
    <div class="filterbar">
      <label class="field" style="min-width: 200px">
        Server *
        <select v-model="serverId" @change="reload">
          <option value="" disabled>Select…</option>
          <option v-for="s in servers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>
      <label class="field">
        Metric
        <select v-model="metric" @change="reload">
          <option value="cpu">CPU total %</option>
          <option value="memory">Memory used %</option>
          <option value="disk">Disk used % (worst mount)</option>
          <option value="network">Network throughput</option>
        </select>
      </label>
      <label class="field">
        Range
        <select v-model="hours" @change="reload">
          <option :value="1">last hour</option>
          <option :value="6">last 6 hours</option>
          <option :value="24">last 24 hours</option>
          <option :value="168">last 7 days</option>
        </select>
      </label>
      <button :class="{ primary: compare }" @click="compare = !compare; reload()">
        {{ compare ? 'Comparing: on' : 'Compare servers' }}
      </button>
    </div>

    <div v-if="!serverId">
      <EmptyState title="Pick a server" hint="Select a server above to chart its metrics." />
    </div>
    <template v-else>
      <h2>{{ metricTitle }}</h2>
      <TimeChart
        v-if="series.length && series[0].points.length"
        :points="chartPoints(series[0])"
        :label="metricTitle"
        :show-second="series.length > 1"
        primary-label="series A"
        second-label="series B"
      />
      <EmptyState v-else title="No samples in range" hint="The agent reports every minute; widen the range or wait for samples." />

      <div v-if="compare" style="margin-top: 12px">
        <label class="field" style="min-width: 220px">
          Compare with
          <select v-model="compareId" @change="reload">
            <option value="">Select…</option>
            <option v-for="s in servers.filter((x) => x.id !== serverId)" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, type SamplePoint, type Server, type Series } from '../api/client'
import { formatShortTime } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'
import TimeChart from '../components/TimeChart.vue'

const route = useRoute()
const servers = ref<Server[]>([])
const serverId = ref('')
const compareId = ref('')
const metric = ref('cpu')
const hours = ref(6)
const compare = ref(false)
const error = ref('')
const series = ref<{ points: SamplePoint[]; second?: SamplePoint[] }[]>([])

const metricTitle = computed(() => {
  switch (metric.value) {
    case 'cpu': return 'CPU total utilization (%)'
    case 'memory': return 'Memory used (%)'
    case 'disk': return 'Disk used, worst mount (%)'
    default: return 'Network throughput (bytes/s)'
  }
})

function chartPoints(s: { points: SamplePoint[]; second?: SamplePoint[] }) {
  const byTs = new Map(s.points.map((p) => [p.ts, p.value]))
  const secondMap = new Map((s.second ?? []).map((p) => [p.ts, p.value]))
  const keys = [...new Set([...byTs.keys(), ...secondMap.keys()])].sort()
  return keys.map((k) => ({
    key: k,
    total: byTs.get(k) ?? 0,
    second: secondMap.get(k),
    xLabel: formatShortTime(k),
  }))
}

function range() {
  const to = new Date()
  const from = new Date(to.getTime() - hours.value * 3600 * 1000)
  return { date_from: from.toISOString(), date_to: to.toISOString() }
}

async function loadSeries(server: string, kind: string, name: string): Promise<SamplePoint[]> {
  const res = await api.get('/metrics/series', {
    params: { server_id: server, kind, name, limit: 1000, ...range() },
  })
  return (res.data as Series).points
}

async function diskWorst(server: string): Promise<SamplePoint[]> {
  const latest: { name: string; value: number }[] = (
    await api.get('/metrics/latest', { params: { server_id: server, kind: 'disk' } })
  ).data
  const pcts = latest.filter((r) => r.name.endsWith('/used_pct'))
  if (!pcts.length) return []
  const worst = pcts.reduce((a, b) => (a.value >= b.value ? a : b))
  const mount = '/' + worst.name.split('/').slice(1, -1).join('/')
  return loadSeries(server, 'disk', `${mount === '/' ? '/' : mount}/used_pct`)
}

async function netTotal(server: string): Promise<{ rx: SamplePoint[]; tx: SamplePoint[] }> {
  const latest: { name: string }[] = (
    await api.get('/metrics/latest', { params: { server_id: server, kind: 'net' } })
  ).data
  const ifaces = [...new Set(latest.map((r) => r.name.split('/')[0]).filter((n) => n && n !== 'lo' && n !== 'lo0'))]
  const iface = ifaces[0] ?? [...new Set(latest.map((r) => r.name.split('/')[0]).filter(Boolean))][0]
  if (!iface) return { rx: [], tx: [] }
  const [rx, tx] = await Promise.all([
    loadSeries(server, 'net', `${iface}/rx_bps`).catch(() => [] as SamplePoint[]),
    loadSeries(server, 'net', `${iface}/tx_bps`).catch(() => [] as SamplePoint[]),
  ])
  return { rx, tx }
}

async function reload() {
  error.value = ''
  series.value = []
  if (!serverId.value) return
  try {
    if (metric.value === 'cpu') {
      const a = await loadSeries(serverId.value, 'cpu', 'total')
      let second: SamplePoint[] | undefined
      if (compare.value && compareId.value) second = await loadSeries(compareId.value, 'cpu', 'total')
      series.value = [{ points: a, second }]
    } else if (metric.value === 'memory') {
      const a = await loadSeries(serverId.value, 'memory', 'used_pct')
      let second: SamplePoint[] | undefined
      if (compare.value && compareId.value) second = await loadSeries(compareId.value, 'memory', 'used_pct')
      series.value = [{ points: a, second }]
    } else if (metric.value === 'disk') {
      series.value = [{ points: await diskWorst(serverId.value) }]
    } else {
      const net = await netTotal(serverId.value)
      series.value = [{ points: net.rx, second: net.tx.map((p) => ({ ...p })) }]
    }
  } catch {
    error.value = 'Could not load metric series.'
  }
}

onMounted(async () => {
  servers.value = (await api.get('/servers', { params: { page_size: 100 } })).data.items
  const q = route.query
  if (typeof q.server === 'string') serverId.value = q.server
  else if (servers.value.length === 1) serverId.value = servers.value[0].id
  if (typeof q.metric === 'string' && ['cpu', 'memory', 'disk', 'network'].includes(q.metric)) {
    metric.value = q.metric
  }
  await reload()
})
</script>

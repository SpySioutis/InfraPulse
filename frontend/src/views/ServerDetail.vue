<template>
  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="server">
    <div class="page-head">
      <h1>{{ server.name }}</h1>
      <span :class="healthDot(server.health)"></span>
      <span :class="healthClass(server.health)">{{ server.health }}</span>
      <span class="sub mono">{{ server.hostname }}</span>
      <span class="spacer" style="flex: 1"></span>
      <RouterLink to="/servers"><button>← All servers</button></RouterLink>
    </div>
    <div v-if="notice" class="notice">{{ notice }}</div>

    <div class="panel">
      <h2>System information</h2>
      <dl class="kv">
        <dt>Hostname</dt>
        <dd class="mono">{{ server.hostname }}</dd>
        <dt>IP address</dt>
        <dd class="mono">{{ server.ip_address ?? '—' }}</dd>
        <dt>Operating system</dt>
        <dd>{{ server.os_name ?? '—' }} {{ server.os_version ?? '' }}</dd>
        <dt>Architecture</dt>
        <dd class="mono">{{ server.architecture ?? '—' }}</dd>
        <dt>Environment</dt>
        <dd>{{ server.environment ?? '—' }}</dd>
        <dt>Group</dt>
        <dd>{{ server.group_name ?? '—' }}</dd>
        <dt>Agent</dt>
        <dd class="mono">{{ server.agent_status ?? 'none' }}{{ server.agent_version ? ` · v${server.agent_version}` : '' }}</dd>
        <dt>Last heartbeat</dt>
        <dd class="mono">{{ formatDateTime(server.last_heartbeat_at) }}</dd>
      </dl>
      <div v-if="server.health_reasons.length" class="dim" style="font-size: 12.5px">
        Health reasons: {{ server.health_reasons.join('; ') }}
      </div>
    </div>

    <div class="panel">
      <h2>Current utilization</h2>
      <MetricBar label="CPU total" :value="server.cpu_pct ?? 0" :text="server.cpu_pct === null ? 'no data' : undefined" />
      <MetricBar label="Memory used" :value="server.mem_pct ?? 0" :text="server.mem_pct === null ? 'no data' : undefined" />
      <MetricBar label="Disk (worst)" :value="server.disk_max_pct ?? 0" :text="server.disk_max_pct === null ? 'no data' : undefined" />
      <div v-if="disks.length" style="margin-top: 10px">
        <h2>Filesystems</h2>
        <table class="grid">
          <thead>
            <tr>
              <th>Mount point</th>
              <th style="text-align: right">Used</th>
              <th style="text-align: right">Total</th>
              <th style="text-align: right">Use%</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in disks" :key="d.mount">
              <td class="mono">{{ d.mount }}</td>
              <td class="mono" style="text-align: right">{{ formatBytes(d.used) }}</td>
              <td class="mono" style="text-align: right">{{ formatBytes(d.total) }}</td>
              <td class="mono" style="text-align: right">{{ d.pct.toFixed(1) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>CPU history (total %)</h2>
      <TimeChart v-if="cpuSeries.length" :points="chartPoints(cpuSeries)" label="CPU utilization" />
      <EmptyState v-else title="No CPU samples yet" hint="Samples appear once the agent reports." />
    </div>

    <div class="panel">
      <h2>Memory history (used %)</h2>
      <TimeChart v-if="memSeries.length" :points="chartPoints(memSeries)" label="Memory utilization" />
      <EmptyState v-else title="No memory samples yet" />
    </div>

    <div class="panel">
      <h2>Network throughput</h2>
      <TimeChart v-if="netPoints.length" :points="netPoints" label="Network throughput" show-second primary-label="rx" second-label="tx" />
      <EmptyState v-else title="No network samples yet" />
    </div>

    <div class="panel">
      <h2>Agent & registration</h2>
      <div class="toolbar" style="margin-bottom: 8px">
        <button class="primary" @click="issueToken">Generate registration token</button>
        <span class="spacer"></span>
        <button class="danger" @click="revokeAgent" :disabled="!hasAgent">Revoke agent</button>
      </div>
      <div v-if="regToken" class="notice" style="overflow-wrap: anywhere">
        Single-use token (shown once — store it on the monitored host now):
        <br />
        <span class="mono"><strong>{{ regToken }}</strong></span>
      </div>
      <p class="dim" style="font-size: 12.5px; margin-bottom: 0">
        Agent status: <span class="mono">{{ server.agent_status ?? 'none registered' }}</span>.
        Revoking blocks metric submission immediately; register again with a fresh token to resume.
      </p>
    </div>

    <div class="panel">
      <h2>Recent alerts</h2>
      <table class="grid" v-if="alerts.length">
        <tbody>
          <tr v-for="a in alerts" :key="a.id">
            <td><span :class="severityClass(a.severity)">{{ a.severity }}</span></td>
            <td class="ellipsis" :title="a.message">{{ a.message }}</td>
            <td class="mono dim nowrap">{{ formatDateTime(a.triggered_at) }}</td>
            <td class="mono">{{ a.status }}</td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-else title="No alerts for this server" />
    </div>
  </div>
  <div v-else-if="loading" class="dim">Loading…</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, type Alert, type SamplePoint, type Server, type Series } from '../api/client'
import { formatBytes, formatDateTime, formatShortTime } from '../utils/format'
import { healthClass, healthDot, severityClass } from '../utils/health'
import EmptyState from '../components/EmptyState.vue'
import MetricBar from '../components/MetricBar.vue'
import TimeChart from '../components/TimeChart.vue'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const notice = ref('')
const server = ref<Server | null>(null)
const cpuSeries = ref<SamplePoint[]>([])
const memSeries = ref<SamplePoint[]>([])
const netSeries = ref<{ rx: SamplePoint[]; tx: SamplePoint[] }>({ rx: [], tx: [] })
const disks = ref<{ mount: string; used: number; total: number; pct: number }[]>([])
const alerts = ref<Alert[]>([])
const regToken = ref('')
const hasAgent = ref(false)

const netPoints = computed(() => {
  const rxMap = new Map(netSeries.value.rx.map((p) => [p.ts, p.value]))
  const txMap = new Map(netSeries.value.tx.map((p) => [p.ts, p.value]))
  const keys = [...new Set([...rxMap.keys(), ...txMap.keys()])].sort()
  return keys.map((k) => ({
    key: k,
    total: rxMap.get(k) ?? 0,
    second: txMap.get(k),
    xLabel: formatShortTime(k),
  }))
})

function chartPoints(points: SamplePoint[]) {
  return points.map((p) => ({
    key: p.ts,
    total: p.value,
    xLabel: formatShortTime(p.ts),
  }))
}

async function series(kind: string, name: string): Promise<SamplePoint[]> {
  const id = String(route.params.id)
  const res = await api.get('/metrics/series', { params: { server_id: id, kind, name, limit: 300 } })
  return (res.data as Series).points
}

async function primaryInterface(id: string): Promise<string> {
  const latest: { name: string; value: number }[] = (
    await api.get('/metrics/latest', { params: { server_id: id, kind: 'net' } })
  ).data
  const ifaces = [...new Set(latest.map((r) => r.name.split('/')[0]).filter((n) => n && n !== 'lo0' && n !== 'lo'))]
  if (ifaces.length) return ifaces[0]
  const any = latest.map((r) => r.name.split('/')[0]).filter(Boolean)
  return any[0] ?? 'eth0'
}

async function load() {
  const id = String(route.params.id)
  loading.value = true
  try {
    const iface = await primaryInterface(id).catch(() => 'eth0')
    const [s, cpu, mem, rx, tx] = await Promise.all([
      api.get(`/servers/${id}`),
      series('cpu', 'total'),
      series('memory', 'used_pct'),
      series('net', `${iface}/rx_bps`).catch(() => [] as SamplePoint[]),
      series('net', `${iface}/tx_bps`).catch(() => [] as SamplePoint[]),
    ])
    const srv = s.data as Server
    server.value = srv
    cpuSeries.value = cpu as SamplePoint[]
    memSeries.value = mem as SamplePoint[]
    netSeries.value = { rx: rx as SamplePoint[], tx: tx as SamplePoint[] }
    hasAgent.value = !!srv.agent_status && srv.agent_status !== 'revoked'
    alerts.value = (
      await api.get('/alerts', { params: { server_id: id, page_size: 10 } })
    ).data.items
    // Disk table from the newest value of every disk/* metric.
    const latest: { name: string; value: number }[] = (
      await api.get('/metrics/latest', { params: { server_id: id, kind: 'disk' } })
    ).data
    const byMount = new Map<string, { total?: number; used?: number; pct?: number }>()
    for (const row of latest) {
      const parts = row.name.split('/')
      if (parts.length < 3) continue
      const field = parts.pop() as string
      const mount = parts.join('/')
      const entry = byMount.get(mount) ?? {}
      if (field === 'total_bytes') entry.total = row.value
      else if (field === 'used_bytes') entry.used = row.value
      else if (field === 'used_pct') entry.pct = row.value
      byMount.set(mount, entry)
    }
    disks.value = [...byMount.entries()].map(([mount, e]) => ({
      mount,
      used: e.used ?? 0,
      total: e.total ?? 0,
      pct: e.pct ?? 0,
    }))
  } catch {
    error.value = 'Could not load server details.'
  } finally {
    loading.value = false
  }
}

async function issueToken() {
  error.value = ''
  regToken.value = ''
  try {
    const res = await api.post(`/servers/${String(route.params.id)}/registration-token`)
    regToken.value = res.data.registration_token
    notice.value = 'Token issued. It is shown once and expires in 24 hours.'
    setTimeout(() => (notice.value = ''), 15000)
  } catch (e: unknown) {
    error.value = 'Could not issue a registration token.'
  }
}

async function revokeAgent() {
  if (!window.confirm('Revoke this agent? Metric submission stops immediately.')) return
  const agents = (await api.get('/agents')).data as { id: string; server_id: string }[]
  const agent = agents.find((a) => a.server_id === String(route.params.id))
  if (!agent) {
    notice.value = 'No agent registered for this server.'
    return
  }
  await api.delete(`/agents/${agent.id}`)
  notice.value = 'Agent revoked.'
  await load()
}

onMounted(load)
</script>

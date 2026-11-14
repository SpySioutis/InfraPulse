<template>
  <div class="page-head">
    <h1>Alerts</h1>
    <span class="sub" v-if="page">{{ formatNumber(page.total) }} total</span>
    <span class="spacer" style="flex: 1"></span>
    <button @click="evaluate">Evaluate now</button>
    <button :class="{ primary: showForm }" @click="showForm = !showForm">{{ showForm ? 'Close' : 'New rule' }}</button>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div v-if="showForm" class="panel">
    <h2>{{ editing ? 'Edit alert rule' : 'New alert rule' }}</h2>
    <div class="filterbar">
      <label class="field" style="min-width: 200px">
        Name *
        <input v-model="form.name" type="text" placeholder="High CPU" />
      </label>
      <label class="field">
        Server (empty = all)
        <select v-model="form.server_id">
          <option value="">All servers</option>
          <option v-for="s in servers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>
      <label class="field" style="min-width: 200px">
        Metric *
        <select v-model="form.metric">
          <option value="cpu_total">cpu_total (%)</option>
          <option value="memory_used_pct">memory_used_pct (%)</option>
          <option value="disk_max_pct">disk_max_pct (%)</option>
          <option value="custom">custom kind/name…</option>
        </select>
      </label>
      <label v-if="form.metric === 'custom'" class="field">
        kind/name
        <input v-model="customMetric" type="text" placeholder="cpu/load_1" />
      </label>
      <label class="field">
        Operator
        <select v-model="form.operator">
          <option value=">">&gt;</option>
          <option value=">=">&gt;=</option>
          <option value="<">&lt;</option>
          <option value="<=">&lt;=</option>
        </select>
      </label>
      <label class="field">
        Threshold *
        <input v-model.number="form.threshold" type="number" step="any" />
      </label>
      <label class="field">
        Severity
        <select v-model="form.severity">
          <option value="informational">informational</option>
          <option value="warning">warning</option>
          <option value="critical">critical</option>
        </select>
      </label>
      <label class="field">
        Cooldown (min)
        <input v-model.number="form.cooldown_minutes" type="number" min="1" max="1440" />
      </label>
      <label class="field" style="flex-direction: row; align-items: center; gap: 6px">
        <input v-model="form.enabled" type="checkbox" /> enabled
      </label>
      <button class="primary" :disabled="!form.name.trim()" @click="saveRule">{{ editing ? 'Update' : 'Create' }}</button>
      <button v-if="editing" @click="cancelEdit">Cancel</button>
    </div>
  </div>

  <div class="panel">
    <h2>Alert rules</h2>
    <table class="grid" v-if="rules.length">
      <thead>
        <tr>
          <th>Name</th>
          <th>Scope</th>
          <th>Condition</th>
          <th>Severity</th>
          <th>Enabled</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rules" :key="r.id">
          <td><strong>{{ r.name }}</strong></td>
          <td>{{ r.server_id ? serverName(r.server_id) : 'all servers' }}</td>
          <td class="mono">{{ r.metric }} {{ r.operator }} {{ r.threshold }}</td>
          <td><span :class="severityClass(r.severity)">{{ r.severity }}</span></td>
          <td class="mono">{{ r.enabled ? 'yes' : 'no' }}</td>
          <td class="nowrap" style="text-align: right">
            <button style="margin-right: 6px" @click="startEdit(r)">Edit</button>
            <button class="danger" @click="removeRule(r)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-else title="No alert rules" hint="Create one above — e.g. cpu_total > 90 (critical)." />
  </div>

  <div class="panel">
    <div class="filterbar">
      <label class="field">
        Status
        <select v-model="query.status" @change="reload">
          <option value="">All</option>
          <option value="active">active</option>
          <option value="acknowledged">acknowledged</option>
          <option value="resolved">resolved</option>
        </select>
      </label>
      <label class="field">
        Severity
        <select v-model="query.severity" @change="reload">
          <option value="">All</option>
          <option value="informational">informational</option>
          <option value="warning">warning</option>
          <option value="critical">critical</option>
        </select>
      </label>
      <label class="field">
        Server
        <select v-model="query.server_id" @change="reload">
          <option value="">All</option>
          <option v-for="s in servers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>
      <button @click="resetQuery">Reset</button>
    </div>
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="page && page.items.length">
      <table class="grid">
        <thead>
          <tr>
            <th>Triggered</th>
            <th>Severity</th>
            <th>Server</th>
            <th>Message</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in page.items" :key="a.id">
            <td class="mono dim nowrap">{{ formatDateTime(a.triggered_at) }}</td>
            <td><span :class="severityClass(a.severity)">{{ a.severity }}</span></td>
            <td>{{ a.server_name ?? '—' }}</td>
            <td class="ellipsis" :title="a.message">{{ a.message }}</td>
            <td class="mono">{{ a.status }}</td>
            <td class="nowrap" style="text-align: right">
              <button v-if="a.status === 'active'" style="margin-right: 6px" @click="ack(a)">Acknowledge</button>
              <button v-if="a.status !== 'resolved'" @click="resolve(a)">Resolve</button>
            </td>
          </tr>
        </tbody>
      </table>
      <Pagination :page="page.page" :pages="page.pages" :total="page.total" @change="goToPage" />
    </template>
    <EmptyState v-else title="No alerts" hint="Alerts fire automatically when rules breach or servers go offline." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, toParams, type Alert, type AlertRule, type Server } from '../api/client'
import { formatDateTime, formatNumber } from '../utils/format'
import { severityClass } from '../utils/health'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'

const servers = ref<Server[]>([])
const rules = ref<AlertRule[]>([])
const page = ref<{ items: Alert[]; total: number; page: number; pages: number } | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const showForm = ref(false)
const editing = ref<AlertRule | null>(null)
const query = reactive<{ status?: string; severity?: string; server_id?: string; page: number; page_size: number }>({
  page: 1,
  page_size: 25,
})
const form = reactive({
  name: '',
  server_id: '',
  metric: 'cpu_total',
  operator: '>',
  threshold: 90,
  severity: 'warning',
  cooldown_minutes: 60,
  enabled: true,
})
const customMetric = ref('')

function serverName(id: string | null): string {
  if (!id) return 'all servers'
  return servers.value.find((s) => s.id === id)?.name ?? id.slice(0, 8)
}

function effectiveMetric(): string {
  return form.metric === 'custom' ? customMetric.value.trim() : form.metric
}

async function loadServers() {
  servers.value = (await api.get('/servers', { params: { page_size: 100 } })).data.items
}

async function refreshRules() {
  rules.value = (await api.get('/alert-rules')).data
}

async function reload() {
  loading.value = true
  try {
    page.value = (await api.get('/alerts', { params: toParams(query as Record<string, unknown>) })).data
  } catch {
    error.value = 'Could not load alerts.'
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.status = undefined
  query.severity = undefined
  query.server_id = undefined
  query.page = 1
  reload()
}

function goToPage(p: number) {
  query.page = p
  reload()
}

async function saveRule() {
  const metric = effectiveMetric()
  if (!metric) {
    error.value = 'Metric is required.'
    return
  }
  const payload = {
    name: form.name.trim(),
    server_id: form.server_id || null,
    metric,
    operator: form.operator,
    threshold: form.threshold,
    severity: form.severity,
    cooldown_minutes: form.cooldown_minutes,
    enabled: form.enabled,
  }
  try {
    if (editing.value) {
      await api.put(`/alert-rules/${editing.value.id}`, payload)
    } else {
      await api.post('/alert-rules', payload)
    }
    cancelEdit()
    await refreshRules()
  } catch {
    error.value = 'Could not save rule. Check the metric name.'
  }
}

function startEdit(r: AlertRule) {
  editing.value = r
  form.name = r.name
  form.server_id = r.server_id ?? ''
  form.metric = ['cpu_total', 'memory_used_pct', 'disk_max_pct'].includes(r.metric) ? r.metric : 'custom'
  customMetric.value = form.metric === 'custom' ? r.metric : ''
  form.operator = r.operator
  form.threshold = r.threshold
  form.severity = r.severity
  form.cooldown_minutes = r.cooldown_minutes
  form.enabled = r.enabled
  showForm.value = true
}

function cancelEdit() {
  editing.value = null
  form.name = ''
  form.server_id = ''
  form.metric = 'cpu_total'
  form.operator = '>'
  form.threshold = 90
  form.severity = 'warning'
  form.cooldown_minutes = 60
  form.enabled = true
  customMetric.value = ''
  showForm.value = false
}

async function removeRule(r: AlertRule) {
  if (!window.confirm(`Delete rule "${r.name}"? (Admin only)`)) return
  try {
    await api.delete(`/alert-rules/${r.id}`)
    await refreshRules()
  } catch {
    error.value = 'Delete failed. Only admins can delete rules.'
  }
}

async function ack(a: Alert) {
  await api.post(`/alerts/${a.id}/acknowledge`)
  await reload()
}

async function resolve(a: Alert) {
  await api.post(`/alerts/${a.id}/resolve`)
  await reload()
}

async function evaluate() {
  const res = await api.post('/alerts/evaluate')
  notice.value = `Evaluated ${res.data.servers_checked} server(s): ${res.data.alerts_fired} fired, ${res.data.alerts_resolved} resolved.`
  await reload()
  setTimeout(() => (notice.value = ''), 5000)
}

onMounted(async () => {
  await loadServers()
  await refreshRules()
  await reload()
})
</script>

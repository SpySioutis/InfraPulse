<template>
  <div class="page-head">
    <h1>Agents</h1>
    <span class="sub">registration, status, revocation</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="panel">
    <h2>Registered agents</h2>
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="agents.length">
      <table class="grid">
        <thead>
          <tr>
            <th>Server</th>
            <th>Status</th>
            <th>Version</th>
            <th>Token prefix</th>
            <th>Last heartbeat</th>
            <th>Last metric</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in agents" :key="a.id">
            <td><RouterLink :to="'/servers/' + a.server_id">{{ a.server_name ?? a.server_id }}</RouterLink></td>
            <td class="mono">{{ a.status }}</td>
            <td class="mono">{{ a.version ?? '—' }}</td>
            <td class="mono dim">{{ a.token_prefix }}…</td>
            <td class="mono dim nowrap">{{ formatDateTime(a.last_heartbeat_at) }}</td>
            <td class="mono dim nowrap">{{ formatDateTime(a.last_metric_at) }}</td>
            <td class="nowrap" style="text-align: right">
              <button class="danger" @click="revoke(a)" :disabled="a.status === 'revoked'">Revoke</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <EmptyState v-else title="No agents registered" hint="Open a server and generate a registration token to enroll its agent." />
  </div>

  <div class="panel">
    <h2>How to enroll an agent</h2>
    <ol class="dim" style="font-size: 13px; padding-left: 20px; margin: 0">
      <li>Register the server under Servers (or open its details page).</li>
      <li>Click “Generate registration token” and copy the single-use token.</li>
      <li>On the monitored Linux host, install the agent (see MANUAL.md) and store the token in its config.</li>
      <li>Start the agent: it registers itself and begins reporting every minute.</li>
      <li>Tokens are shown once and stored hashed; revoke here any time to cut off an agent.</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type Agent } from '../api/client'
import { formatDateTime } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'

const agents = ref<Agent[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')

async function refresh() {
  loading.value = true
  try {
    agents.value = (await api.get('/agents')).data
  } catch {
    error.value = 'Could not load agents.'
  } finally {
    loading.value = false
  }
}

async function revoke(a: Agent) {
  if (!window.confirm(`Revoke the agent on "${a.server_name}"? It stops reporting immediately. (Admin only)`)) return
  try {
    await api.delete(`/agents/${a.id}`)
    notice.value = `Agent on "${a.server_name}" revoked.`
    await refresh()
    setTimeout(() => (notice.value = ''), 5000)
  } catch {
    error.value = 'Revoke failed. Only admins can revoke agents.'
  }
}

onMounted(refresh)
</script>

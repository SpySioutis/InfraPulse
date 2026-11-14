<template>
  <div class="page-head">
    <h1>Settings</h1>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="panel">
    <h2>Account</h2>
    <dl class="kv">
      <dt>Username</dt>
      <dd class="mono">{{ auth.user?.username }}</dd>
      <dt>Role</dt>
      <dd>{{ auth.isAdmin ? 'admin' : 'user' }}</dd>
    </dl>
    <div class="toolbar" style="margin-bottom: 0">
      <button @click="logout">Log out</button>
    </div>
  </div>

  <div v-if="auth.isAdmin" class="panel">
    <h2>Users (admin)</h2>
    <div class="filterbar">
      <label class="field">
        Username
        <input v-model="newUsername" type="text" />
      </label>
      <label class="field">
        Password (min 8)
        <input v-model="newPassword" type="password" />
      </label>
      <label class="field" style="flex-direction: row; align-items: center; gap: 6px">
        <input v-model="newAdmin" type="checkbox" /> admin
      </label>
      <button class="primary" :disabled="!newUsername || newPassword.length < 8" @click="createUser">Add user</button>
    </div>
    <table class="grid" v-if="users.length">
      <thead>
        <tr>
          <th>Username</th>
          <th>Role</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td class="mono">{{ u.username }}</td>
          <td>{{ u.is_admin ? 'admin' : 'user' }}</td>
          <td style="text-align: right">
            <button v-if="u.id !== auth.user?.id" class="danger" @click="removeUser(u.id, u.username)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Monitoring configuration</h2>
    <p class="dim" style="font-size: 13px; margin-top: 0">
      Thresholds and retention are centralized on the server (<span class="mono">.env</span>).
      Current effective values:
    </p>
    <dl class="kv">
      <dt>CPU warn / critical</dt>
      <dd class="mono">{{ config.cpu_warn_pct }}% / {{ config.cpu_crit_pct }}%</dd>
      <dt>Memory warn / critical</dt>
      <dd class="mono">{{ config.mem_warn_pct }}% / {{ config.mem_crit_pct }}%</dd>
      <dt>Disk warn / critical</dt>
      <dd class="mono">{{ config.disk_warn_pct }}% / {{ config.disk_crit_pct }}%</dd>
      <dt>Heartbeat grace</dt>
      <dd class="mono">{{ config.heartbeat_grace_seconds }}s</dd>
      <dt>Retention</dt>
      <dd class="mono">{{ config.metric_retention_days }} days</dd>
    </dl>
    <h2>Notifications</h2>
    <div class="toolbar">
      <span class="dim">{{ unreadCount }} unread</span>
      <span class="spacer"></span>
      <button @click="markAllRead">Mark all read</button>
    </div>
    <table class="grid" v-if="notifications.length">
      <tbody>
        <tr v-for="n in notifications" :key="n.id" :style="n.read_at ? '' : 'font-weight: 600'">
          <td class="mono dim nowrap">{{ formatDateTime(n.created_at) }}</td>
          <td>{{ n.title }}</td>
          <td class="dim ellipsis" :title="n.body ?? ''">{{ n.body ?? '' }}</td>
          <td style="text-align: right">
            <button v-if="!n.read_at" @click="markRead(n.id)">Mark read</button>
          </td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-else title="No notifications" hint="Alert notifications will appear here." />
  </div>

  <div class="panel">
    <h2>Appearance</h2>
    <div class="toolbar">
      <label class="field" style="flex-direction: row; align-items: center">
        Theme
        <select :value="settings.theme" @change="onTheme">
          <option value="dark">Dark (default)</option>
          <option value="light">Light</option>
        </select>
      </label>
    </div>
  </div>

  <div class="panel">
    <h2>Backend</h2>
    <dl class="kv">
      <dt>API base URL</dt>
      <dd class="mono">{{ apiBase }}</dd>
      <dt>Health</dt>
      <dd v-if="health" style="color: var(--ok)">reachable · {{ health.service }}</dd>
      <dd v-else-if="healthChecked" style="color: var(--danger)">unreachable</dd>
      <dd v-else class="dim">checking…</dd>
      <dt>API docs</dt>
      <dd><a :href="docsUrl" target="_blank" rel="noopener">OpenAPI (Swagger UI)</a></dd>
    </dl>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useSettingsStore } from '../stores/settings'
import { formatDateTime } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'

const auth = useAuthStore()
const settings = useSettingsStore()
const router = useRouter()
const error = ref('')
const notice = ref('')
const users = ref<{ id: string; username: string; is_admin: boolean }[]>([])
const notifications = ref<{ id: string; title: string; body: string | null; read_at: string | null; created_at: string | null }[]>([])
const unreadCount = ref(0)
const newUsername = ref('')
const newPassword = ref('')
const newAdmin = ref(false)
const apiBase = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`
const docsUrl = import.meta.env.VITE_API_BASE_URL ? `${import.meta.env.VITE_API_BASE_URL}/api/docs` : '/api/docs'
const health = ref<{ status: string; service: string } | null>(null)
const healthChecked = ref(false)
const config = ref({
  cpu_warn_pct: 75,
  cpu_crit_pct: 90,
  mem_warn_pct: 80,
  mem_crit_pct: 95,
  disk_warn_pct: 80,
  disk_crit_pct: 95,
  heartbeat_grace_seconds: 180,
  metric_retention_days: 30,
})

function onTheme(event: Event) {
  settings.setTheme((event.target as HTMLSelectElement).value as 'dark' | 'light')
}

function logout() {
  auth.logout()
  router.push('/login')
}

async function createUser() {
  try {
    await api.post('/auth/users', { username: newUsername.value.trim(), password: newPassword.value, is_admin: newAdmin.value })
    newUsername.value = ''
    newPassword.value = ''
    newAdmin.value = false
    users.value = (await api.get('/auth/users')).data
  } catch {
    error.value = 'Could not create user (name taken?).'
  }
}

async function removeUser(id: string, username: string) {
  if (!window.confirm(`Delete user "${username}"?`)) return
  await api.delete(`/auth/users/${id}`)
  users.value = (await api.get('/auth/users')).data
}

async function loadNotifications() {
  notifications.value = (await api.get('/notifications', { params: { limit: 50 } })).data
  unreadCount.value = notifications.value.filter((n) => !n.read_at).length
}

async function markRead(id: string) {
  await api.post(`/notifications/${id}/read`)
  await loadNotifications()
}

async function markAllRead() {
  await api.post('/notifications/read-all')
  await loadNotifications()
}

onMounted(async () => {
  settings.applyTheme()
  try {
    health.value = (await api.get('/health')).data
  } catch {
    health.value = null
  } finally {
    healthChecked.value = true
  }
  try {
    config.value = (await api.get('/config')).data
  } catch {
    // Fall back to documented defaults.
  }
  await loadNotifications()
  if (auth.isAdmin) {
    try {
      users.value = (await api.get('/auth/users')).data
    } catch {
      error.value = 'Could not load users.'
    }
  }
})
</script>

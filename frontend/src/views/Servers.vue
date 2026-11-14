<template>
  <div class="page-head">
    <h1>Servers</h1>
    <span class="sub" v-if="page">{{ formatNumber(page.total) }} registered</span>
    <span class="spacer" style="flex: 1"></span>
    <button class="primary" @click="showForm = !showForm">{{ showForm ? 'Close' : 'Register server' }}</button>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div v-if="showForm" class="panel">
    <h2>{{ editing ? 'Edit server' : 'Register server' }}</h2>
    <div class="filterbar">
      <label class="field" style="min-width: 200px">
        Name *
        <input v-model="form.name" type="text" placeholder="web-prod-1" />
      </label>
      <label class="field" style="min-width: 200px">
        Hostname *
        <input v-model="form.hostname" type="text" placeholder="web1.example.com" />
      </label>
      <label class="field">
        IP address
        <input v-model="form.ip_address" type="text" placeholder="10.0.0.11" />
      </label>
      <label class="field">
        Environment
        <select v-model="form.environment">
          <option value="">—</option>
          <option>production</option>
          <option>staging</option>
          <option>development</option>
          <option>testing</option>
        </select>
      </label>
      <label class="field">
        Group
        <select v-model="form.group_id">
          <option value="">— none —</option>
          <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </label>
    </div>
    <div class="toolbar">
      <button class="primary" :disabled="!form.name.trim() || !form.hostname.trim()" @click="save">
        {{ editing ? 'Update' : 'Register' }}
      </button>
      <button v-if="editing" @click="cancel">Cancel</button>
    </div>
  </div>

  <div class="panel">
    <div class="filterbar">
      <label class="field" style="min-width: 220px; flex: 1">
        Search
        <input v-model="query.q" type="search" placeholder="name, host, IP…" @input="scheduleReload" />
      </label>
      <label class="field">
        Group
        <select v-model="query.group_id" @change="reload">
          <option value="">All</option>
          <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </label>
      <label class="field">
        Environment
        <select v-model="query.environment" @change="reload">
          <option value="">All</option>
          <option>production</option>
          <option>staging</option>
          <option>development</option>
          <option>testing</option>
        </select>
      </label>
      <label class="field">
        Health
        <select v-model="query.health" @change="reload">
          <option value="">All</option>
          <option value="healthy">healthy</option>
          <option value="warning">warning</option>
          <option value="critical">critical</option>
          <option value="offline">offline</option>
          <option value="unknown">unknown</option>
        </select>
      </label>
      <button :class="{ primary: query.favorite }" @click="query.favorite = query.favorite ? undefined : true; reload()">Favorites</button>
      <button @click="resetQuery">Reset</button>
    </div>

    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="page && page.items.length">
      <table class="grid">
        <thead>
          <tr>
            <th style="width: 26px"></th>
            <th>Name</th>
            <th>Target</th>
            <th>OS</th>
            <th style="text-align: right">CPU</th>
            <th style="text-align: right">Mem</th>
            <th style="text-align: right">Disk</th>
            <th>Health</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="srv in page.items" :key="srv.id" class="rowlink" @click="$router.push(`/servers/${srv.id}`)">
            <td><span :class="healthDot(srv.health)" :title="srv.health"></span></td>
            <td>
              <strong>{{ srv.name }}</strong>
              <span v-if="srv.is_favorite" class="pill fav" style="margin-left: 6px">fav</span>
              <div v-if="srv.environment" class="dim">{{ srv.environment }}</div>
            </td>
            <td class="mono dim">{{ srv.ip_address ?? srv.hostname }}</td>
            <td class="dim">{{ srv.os_name ?? '—' }}</td>
            <td class="mono nowrap" style="text-align: right">{{ srv.cpu_pct === null ? '—' : `${srv.cpu_pct.toFixed(1)}%` }}</td>
            <td class="mono nowrap" style="text-align: right">{{ srv.mem_pct === null ? '—' : `${srv.mem_pct.toFixed(1)}%` }}</td>
            <td class="mono nowrap" style="text-align: right">{{ srv.disk_max_pct === null ? '—' : `${srv.disk_max_pct.toFixed(1)}%` }}</td>
            <td><span :class="healthClass(srv.health)">{{ srv.health }}</span></td>
            <td class="nowrap" @click.stop>
              <button style="margin-right: 6px" @click="startEdit(srv)">Edit</button>
              <button style="margin-right: 6px" @click="toggleFav(srv)">Fav</button>
              <button class="danger" @click="remove(srv)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <Pagination :page="page.page" :pages="page.pages" :total="page.total" @change="goToPage" />
    </template>
    <EmptyState v-else title="No servers match" hint="Register your first server above to start monitoring." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, toParams, type Server, type ServerGroup, type ServerPage } from '../api/client'
import { formatNumber } from '../utils/format'
import { healthClass, healthDot } from '../utils/health'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'

const groups = ref<ServerGroup[]>([])
const page = ref<ServerPage | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const showForm = ref(false)
const editing = ref<Server | null>(null)
const query = reactive<{ q?: string; group_id?: string; environment?: string; health?: string; favorite?: boolean; page: number }>({
  page: 1,
})
const form = reactive({ name: '', hostname: '', ip_address: '', environment: '', group_id: '', is_favorite: false })

let timer: number | undefined

async function loadGroups() {
  groups.value = (await api.get('/groups')).data
}

async function reload() {
  loading.value = true
  try {
    page.value = (await api.get('/servers', { params: toParams(query as Record<string, unknown>) })).data
  } catch {
    error.value = 'Could not load servers.'
  } finally {
    loading.value = false
  }
}

function scheduleReload() {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    query.page = 1
    reload()
  }, 350)
}

function resetQuery() {
  query.q = undefined
  query.group_id = undefined
  query.environment = undefined
  query.health = undefined
  query.favorite = undefined
  query.page = 1
  reload()
}

function goToPage(p: number) {
  query.page = p
  reload()
}

async function save() {
  error.value = ''
  const payload = {
    name: form.name.trim(),
    hostname: form.hostname.trim(),
    ip_address: form.ip_address || null,
    environment: form.environment || null,
    group_id: form.group_id || null,
  }
  try {
    if (editing.value) {
      await api.put(`/servers/${editing.value.id}`, payload)
      notice.value = `Server "${payload.name}" updated.`
    } else {
      await api.post('/servers', payload)
      notice.value = `Server "${payload.name}" registered. Now generate its agent token from its details page.`
    }
    editing.value = null
    form.name = ''
    form.hostname = ''
    form.ip_address = ''
    form.environment = ''
    form.group_id = ''
    showForm.value = false
    await reload()
    setTimeout(() => (notice.value = ''), 6000)
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } }
    error.value = err.response?.status === 409 ? 'A server with this name already exists.' : 'Save failed.'
  }
}

function startEdit(srv: Server) {
  editing.value = srv
  form.name = srv.name
  form.hostname = srv.hostname
  form.ip_address = srv.ip_address ?? ''
  form.environment = srv.environment ?? ''
  form.group_id = srv.group_id ?? ''
  showForm.value = true
}

function cancel() {
  editing.value = null
  showForm.value = false
}

async function toggleFav(srv: Server) {
  await api.patch(`/servers/${srv.id}/favorite`)
  await reload()
}

async function remove(srv: Server) {
  if (!window.confirm(`Delete server "${srv.name}" and ALL its metrics, alerts and agent credentials? (Admin only)`)) return
  try {
    await api.delete(`/servers/${srv.id}`)
    await reload()
  } catch {
    error.value = 'Delete failed. Only admins can delete servers.'
  }
}

onMounted(async () => {
  await loadGroups()
  const groupId = useRoute().query.group_id
  if (typeof groupId === 'string' && groupId) query.group_id = groupId
  await reload()
})
</script>

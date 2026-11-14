<template>
  <div class="page-head">
    <h1>Server Groups</h1>
    <span class="spacer" style="flex: 1"></span>
    <button class="primary" @click="showForm = !showForm">{{ showForm ? 'Close' : 'New group' }}</button>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div v-if="showForm" class="panel">
    <h2>{{ editing ? 'Rename group' : 'New group' }}</h2>
    <div class="filterbar">
      <label class="field" style="min-width: 220px">
        Name *
        <input v-model="name" type="text" placeholder="Production" />
      </label>
      <label class="field" style="flex: 1; min-width: 220px">
        Description
        <input v-model="description" type="text" />
      </label>
      <button class="primary" :disabled="!name.trim()" @click="save">{{ editing ? 'Update' : 'Create' }}</button>
      <button v-if="editing" @click="cancel">Cancel</button>
    </div>
  </div>

  <div class="panel">
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="groups.length">
      <table class="grid">
        <thead>
          <tr>
            <th>Name</th>
            <th style="text-align: right">Servers</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in groups" :key="g.id">
            <td>
              <strong>{{ g.name }}</strong>
              <div v-if="g.description" class="dim">{{ g.description }}</div>
            </td>
            <td class="mono" style="text-align: right">{{ g.server_count }}</td>
            <td class="nowrap" style="text-align: right">
              <RouterLink :to="{ path: '/servers', query: { group_id: g.id } }">
                <button style="margin-right: 6px">View servers</button>
              </RouterLink>
              <button style="margin-right: 6px" @click="startEdit(g)">Rename</button>
              <button class="danger" @click="remove(g)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <EmptyState v-else title="No groups" hint="Create groups like Production or Database Servers to organize servers." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type ServerGroup } from '../api/client'
import EmptyState from '../components/EmptyState.vue'

const groups = ref<ServerGroup[]>([])
const loading = ref(true)
const error = ref('')
const showForm = ref(false)
const editing = ref<ServerGroup | null>(null)
const name = ref('')
const description = ref('')

async function refresh() {
  loading.value = true
  try {
    groups.value = (await api.get('/groups')).data
  } catch {
    error.value = 'Could not load groups.'
  } finally {
    loading.value = false
  }
}

async function save() {
  error.value = ''
  try {
    if (editing.value) {
      await api.put(`/groups/${editing.value.id}`, { name: name.value.trim(), description: description.value || null })
    } else {
      await api.post('/groups', { name: name.value.trim(), description: description.value || null })
    }
    cancel()
    await refresh()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } }
    error.value = err.response?.status === 409 ? 'A group with this name already exists.' : 'Save failed.'
  }
}

function startEdit(g: ServerGroup) {
  editing.value = g
  name.value = g.name
  description.value = g.description ?? ''
  showForm.value = true
}

function cancel() {
  editing.value = null
  name.value = ''
  description.value = ''
  showForm.value = false
}

async function remove(g: ServerGroup) {
  if (!window.confirm(`Delete group "${g.name}"? (Admin only; must be empty first)`)) return
  try {
    await api.delete(`/groups/${g.id}`)
    await refresh()
  } catch {
    error.value = 'Delete failed. Only empty groups can be deleted, and only by admins.'
  }
}

onMounted(refresh)
</script>

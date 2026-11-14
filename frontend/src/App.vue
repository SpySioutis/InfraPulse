<template>
  <div v-if="auth.isAuthenticated" class="app-shell">
    <aside class="sidebar">
      <div class="brand">Infra<span>Pulse</span></div>
      <nav class="nav">
        <RouterLink to="/">Overview</RouterLink>
        <RouterLink to="/servers">Servers</RouterLink>
        <RouterLink to="/groups">Server Groups</RouterLink>
        <RouterLink to="/agents">Agents</RouterLink>
        <RouterLink to="/alerts">Alerts</RouterLink>
        <RouterLink to="/metrics">Metrics</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
      </nav>
      <div class="side-foot">
        {{ auth.user?.username }} · <a href="#" @click.prevent="logout">log out</a>
      </div>
    </aside>
    <main class="main">
      <RouterView />
    </main>
  </div>
  <RouterView v-else />
</template>

<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>Infra<span>Pulse</span></h1>
      <p class="dim">Sign in to monitor your infrastructure.</p>
      <div v-if="error" class="alert">{{ error }}</div>
      <label class="field" style="margin-bottom: 10px">
        Username
        <input v-model="username" type="text" autocomplete="username" autofocus />
      </label>
      <label class="field" style="margin-bottom: 14px">
        Password
        <input v-model="password" type="password" autocomplete="current-password" />
      </label>
      <button class="primary" type="submit" :disabled="busy || !username || !password" style="width: 100%">
        {{ busy ? 'Signing in…' : 'Sign in' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : '/'
    router.push(next)
  } catch {
    error.value = 'Invalid username or password.'
  } finally {
    password.value = ''
    busy.value = false
  }
}
</script>

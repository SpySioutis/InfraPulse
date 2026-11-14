import { defineStore } from 'pinia'
import { api } from '../api/client'

interface AuthUser {
  id: string
  username: string
  is_admin: boolean
}

// The token lives in memory + localStorage. Passwords are never stored
// anywhere on the client: the login form keeps the password only in the
// transient input and clears it after the request completes.
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: '' as string,
    user: null as AuthUser | null,
  }),
  getters: {
    isAuthenticated: (s) => !!s.token,
    isAdmin: (s) => !!s.user?.is_admin,
  },
  actions: {
    restore() {
      const token = localStorage.getItem('infrapulse-token') ?? ''
      const userRaw = localStorage.getItem('infrapulse-user')
      if (token) {
        this.token = token
        try {
          this.user = userRaw ? (JSON.parse(userRaw) as AuthUser) : null
        } catch {
          this.user = null
        }
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      }
    },
    async login(username: string, password: string) {
      const res = await api.post('/auth/login', { username, password })
      this.token = res.data.access_token
      this.user = res.data.user
      localStorage.setItem('infrapulse-token', this.token)
      localStorage.setItem('infrapulse-user', JSON.stringify(this.user))
      api.defaults.headers.common['Authorization'] = `Bearer ${this.token}`
    },
    async fetchMe() {
      try {
        const res = await api.get('/auth/me')
        this.user = res.data
        localStorage.setItem('infrapulse-user', JSON.stringify(this.user))
      } catch {
        this.logout()
        throw new Error('session expired')
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('infrapulse-token')
      localStorage.removeItem('infrapulse-user')
      delete api.defaults.headers.common['Authorization']
    },
  },
})

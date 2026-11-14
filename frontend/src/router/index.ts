import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Login from '../views/Login.vue'
import Overview from '../views/Overview.vue'
import Servers from '../views/Servers.vue'
import ServerDetail from '../views/ServerDetail.vue'
import ServerGroups from '../views/ServerGroups.vue'
import Agents from '../views/Agents.vue'
import Alerts from '../views/Alerts.vue'
import Metrics from '../views/Metrics.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    { path: '/', name: 'overview', component: Overview, meta: { requiresAuth: true } },
    { path: '/servers', name: 'servers', component: Servers, meta: { requiresAuth: true } },
    { path: '/servers/:id', name: 'server-detail', component: ServerDetail, meta: { requiresAuth: true } },
    { path: '/groups', name: 'groups', component: ServerGroups, meta: { requiresAuth: true } },
    { path: '/agents', name: 'agents', component: Agents, meta: { requiresAuth: true } },
    { path: '/alerts', name: 'alerts', component: Alerts, meta: { requiresAuth: true } },
    { path: '/metrics', name: 'metrics', component: Metrics, meta: { requiresAuth: true } },
    { path: '/settings', name: 'settings', component: Settings, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { next: to.fullPath } }
  }
  if (to.path === '/login' && auth.isAuthenticated) {
    return { path: '/' }
  }
  return true
})

export default router

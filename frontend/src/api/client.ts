import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api'

export const api = axios.create({ baseURL, timeout: 60000 })

export interface ServerPage {
  items: Server[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Server {
  id: string
  name: string
  hostname: string
  ip_address: string | null
  os_name: string | null
  os_version: string | null
  architecture: string | null
  environment: string | null
  group_id: string | null
  group_name: string | null
  is_favorite: boolean
  health: string
  health_reasons: string[]
  agent_status: string | null
  agent_version: string | null
  last_heartbeat_at: string | null
  cpu_pct: number | null
  mem_pct: number | null
  disk_max_pct: number | null
  created_at: string | null
}

export interface ServerGroup {
  id: string
  name: string
  description: string | null
  server_count: number
}

export interface Agent {
  id: string
  server_id: string
  server_name: string | null
  status: string
  version: string | null
  token_prefix: string
  last_heartbeat_at: string | null
  last_metric_at: string | null
}

export interface AlertRule {
  id: string
  name: string
  server_id: string | null
  metric: string
  operator: string
  threshold: number
  severity: string
  cooldown_minutes: number
  enabled: boolean
}

export interface Alert {
  id: string
  rule_id: string | null
  server_id: string
  server_name: string | null
  alert_type: string
  severity: string
  message: string
  metric_value: number | null
  status: string
  triggered_at: string | null
}

export interface SamplePoint {
  ts: string
  value: number
}

export interface Series {
  server_id: string
  kind: string
  name: string
  points: SamplePoint[]
}

export interface DashboardSummary {
  servers: number
  online: number
  offline: number
  warning: number
  critical: number
  groups: number
  active_alerts: number
  avg_cpu_pct: number | null
  avg_mem_pct: number | null
  total_disk_bytes: number
  total_disk_used_bytes: number
  recent_alerts: Alert[]
  recent_activity: { id: string; username: string | null; action: string; detail: string | null; created_at: string | null }[]
}

export function toParams(query: Record<string, unknown>): Record<string, string | string[]> {
  const params: Record<string, string | string[]> = {}
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      if (value.length) params[key] = value.map(String)
    } else if (typeof value === 'boolean') {
      params[key] = String(value)
    } else {
      params[key] = String(value)
    }
  }
  return params
}

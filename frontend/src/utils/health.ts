export const HEALTH_LABELS: Record<string, string> = {
  healthy: 'healthy',
  warning: 'warning',
  critical: 'critical',
  offline: 'offline',
  unknown: 'unknown',
}

export function healthDot(health: string | null): string {
  switch (health) {
    case 'healthy':
      return 'dot dot-on'
    case 'warning':
      return 'dot dot-warn'
    case 'critical':
      return 'dot dot-bad'
    default:
      return 'dot dot-off'
  }
}

export function healthClass(health: string | null): string {
  if (!health) return 'st-unknown'
  return `st-${health}`
}

export function severityClass(severity: string): string {
  if (severity === 'critical') return 'pill critical'
  if (severity === 'warning') return 'pill warning'
  return 'pill'
}

/** CSS class for a utilization bar given warn/crit thresholds. */
export function barClass(value: number, warn = 75, crit = 90): string {
  if (value >= crit) return 'fill crit'
  if (value >= warn) return 'fill warn'
  return 'fill'
}

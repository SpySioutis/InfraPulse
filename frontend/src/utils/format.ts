export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-US').format(n)
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes < 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  const value = bytes / Math.pow(1024, i)
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[i]}`
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatShortTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

export function formatBps(bps: number): string {
  if (bps < 1000) return `${Math.round(bps)} B/s`
  if (bps < 1000000) return `${(bps / 1000).toFixed(1)} KB/s`
  return `${(bps / 1000000).toFixed(1)} MB/s`
}

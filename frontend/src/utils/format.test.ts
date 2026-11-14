import { describe, expect, it } from 'vitest'
import { formatBytes, formatBps, formatDateTime } from './format'

describe('format utils', () => {
  it('formats byte sizes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(5 * 1024 ** 3)).toBe('5.0 GB')
  })

  it('formats throughput', () => {
    expect(formatBps(500)).toBe('500 B/s')
    expect(formatBps(2500)).toBe('2.5 KB/s')
    expect(formatBps(3000000)).toBe('3.0 MB/s')
  })

  it('handles null and invalid dates', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
    expect(formatDateTime('2026-01-01T00:00:00Z')).toContain('2026')
  })
})

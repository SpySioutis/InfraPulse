import { describe, expect, it } from 'vitest'
import { barClass, healthClass, healthDot, severityClass } from './health'

describe('health display helpers', () => {
  it('maps statuses to dots and classes', () => {
    expect(healthDot('healthy')).toContain('dot-on')
    expect(healthDot('critical')).toContain('dot-bad')
    expect(healthDot('warning')).toContain('dot-warn')
    expect(healthDot(null)).toContain('dot-off')
    expect(healthClass('healthy')).toBe('st-healthy')
    expect(healthClass('mystery')).toBe('st-mystery')
  })

  it('maps severities to pills', () => {
    expect(severityClass('critical')).toContain('critical')
    expect(severityClass('warning')).toContain('warning')
    expect(severityClass('informational')).toBe('pill')
  })

  it('colors utilization bars by thresholds', () => {
    expect(barClass(10, 75, 90)).toBe('fill')
    expect(barClass(80, 75, 90)).toBe('fill warn')
    expect(barClass(95, 75, 90)).toBe('fill crit')
  })
})

// Location-aware suggestion tests (plan-27.5 Phase 6). Pure + server-free:
// proximity filtering/sorting and the quiet-hours window (incl. wrap-around).
import { describe, expect, it } from 'vitest'
import { buildSuggestions, isQuietHours, SUGGEST_RADIUS_M } from '../src/lib/location.js'

const HERE = { lat: 10.6, lon: -66.9 }
// ~110 m north (0.001° lat) and far away (~110 km).
const NEAR = { lat: 10.601, lon: -66.9 }
const FAR = { lat: 11.6, lon: -66.9 }

describe('buildSuggestions', () => {
  it('returns [] without a position', () => {
    expect(buildSuggestions({ pos: null, operations: [{ id: 'o', zone_lat: 10.6, zone_lon: -66.9 }] })).toEqual([])
  })

  it('keeps nearby active operations and drops far ones', () => {
    const out = buildSuggestions({
      pos: HERE,
      operations: [
        { id: 'near', name: 'Near op', status: 'active', zone_lat: NEAR.lat, zone_lon: NEAR.lon },
        { id: 'far', name: 'Far op', status: 'active', zone_lat: FAR.lat, zone_lon: FAR.lon },
        { id: 'closed', name: 'Closed', status: 'closed', zone_lat: NEAR.lat, zone_lon: NEAR.lon },
      ],
    })
    expect(out.map((s) => s.id)).toEqual(['near'])
    expect(out[0].kind).toBe('operation')
    expect(out[0].distanceM).toBeLessThan(SUGGEST_RADIUS_M)
  })

  it('includes nearby facilities and sorts by distance', () => {
    const out = buildSuggestions({
      pos: HERE,
      operations: [{ id: 'op', name: 'Op', status: 'active', zone_lat: 10.605, zone_lon: -66.9 }],
      facilities: [{ id: 'fac', name: 'Hospital', lat: NEAR.lat, lon: NEAR.lon }],
    })
    expect(out.length).toBe(2)
    // facility (~110 m) is closer than the op (~550 m), so it sorts first
    expect(out[0].id).toBe('fac')
    expect(out[0].kind).toBe('facility')
  })
})

describe('isQuietHours', () => {
  it('is false when unset', () => {
    expect(isQuietHours({ quietStart: null, quietEnd: null }, new Date(2026, 0, 1, 3))).toBe(false)
  })
  it('handles a same-day window', () => {
    const s = { quietStart: 1, quietEnd: 5 }
    expect(isQuietHours(s, new Date(2026, 0, 1, 3))).toBe(true)
    expect(isQuietHours(s, new Date(2026, 0, 1, 6))).toBe(false)
  })
  it('handles a wrap-around window (22→7)', () => {
    const s = { quietStart: 22, quietEnd: 7 }
    expect(isQuietHours(s, new Date(2026, 0, 1, 23))).toBe(true)
    expect(isQuietHours(s, new Date(2026, 0, 1, 5))).toBe(true)
    expect(isQuietHours(s, new Date(2026, 0, 1, 12))).toBe(false)
  })
})

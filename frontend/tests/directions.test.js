// Tests for the offline routing math (plan-21, Phase 1): Haversine distance,
// walking/travel time, great-circle bearing, compass key, and distance format.
import { describe, expect, it } from 'vitest'
import {
  distanceMeters, walkingMinutes, travelMinutes, bearing, cardinalKey, formatDistance,
} from '../src/lib/directions.js'

// Two reference points ~near each other in Caracas (TEST DATA — not real people).
const A = { lat: 10.5000, lon: -66.9000 }
const B = { lat: 10.5100, lon: -66.9000 } // ~1.11 km due north of A

describe('distanceMeters (Haversine)', () => {
  it('measures ~1.11 km for 0.01° of latitude', () => {
    const m = distanceMeters(A, B)
    expect(m).toBeGreaterThan(1090)
    expect(m).toBeLessThan(1130)
  })
  it('is zero for the same point', () => {
    expect(distanceMeters(A, A)).toBeCloseTo(0, 5)
  })
  it('returns null for missing/invalid input', () => {
    expect(distanceMeters(null, B)).toBeNull()
    expect(distanceMeters(A, { lat: null, lon: 1 })).toBeNull()
  })
})

describe('walkingMinutes / travelMinutes', () => {
  it('estimates ~13 min on foot for ~1.11 km (5 km/h)', () => {
    const min = walkingMinutes(distanceMeters(A, B))
    expect(min).toBeGreaterThanOrEqual(12)
    expect(min).toBeLessThanOrEqual(15)
  })
  it('scales with speed (driving is faster than walking)', () => {
    const m = 5000
    expect(travelMinutes(m, 40)).toBeLessThan(travelMinutes(m, 5))
  })
  it('floors at 1 minute and handles null', () => {
    expect(walkingMinutes(5)).toBe(1)
    expect(walkingMinutes(null)).toBeNull()
  })
})

describe('bearing / cardinalKey', () => {
  it('points due north (0°) when B is directly north of A', () => {
    const deg = bearing(A, B)
    expect(deg).toBeGreaterThanOrEqual(0)
    expect(deg).toBeLessThan(1)
    expect(cardinalKey(deg)).toBe('n')
  })
  it('points due east for a point east of A', () => {
    const east = { lat: A.lat, lon: A.lon + 0.01 }
    expect(cardinalKey(bearing(A, east))).toBe('e')
  })
  it('wraps 360° back to north', () => {
    expect(cardinalKey(359)).toBe('n')
    expect(cardinalKey(null)).toBeNull()
  })
})

describe('formatDistance', () => {
  it('shows metres below ~1 km and km above', () => {
    expect(formatDistance(450)).toMatch(/m$/)
    expect(formatDistance(2300)).toBe('2.3 km')
  })
  it('supports miles/feet', () => {
    expect(formatDistance(8047, 'mi')).toBe('5.0 mi')
    expect(formatDistance(100, 'mi')).toMatch(/ft$/)
  })
  it('returns empty string for null', () => {
    expect(formatDistance(null)).toBe('')
  })
})

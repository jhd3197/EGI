// Multi-modal routing helper tests (plan-21, Phase 6). Pure + server-free: per
// mode arrival ranges, the long-walk battery warning, nearest-hub selection, and
// the long-distance hub-to-hub evacuation plan.
import { describe, expect, it } from 'vitest'
import {
  MODES, estimateArrival, batteryWarning, nearestHub, hubToHub,
} from '../src/lib/multimodal.js'

describe('estimateArrival', () => {
  it('returns a min<max minute range for walking', () => {
    const r = estimateArrival(5000, 'walk')
    expect(r).not.toBeNull()
    expect(r.minMinutes).toBeLessThan(r.maxMinutes)
  })

  it('makes driving faster than walking for the same distance', () => {
    const walk = estimateArrival(5000, 'walk')
    const drive = estimateArrival(5000, 'drive')
    expect(drive.maxMinutes).toBeLessThan(walk.minMinutes)
  })

  it('returns null for transit (no GTFS data yet) and unknown distance', () => {
    expect(estimateArrival(5000, 'transit')).toBeNull()
    expect(estimateArrival(null, 'walk')).toBeNull()
  })

  it('exposes the three supported modes', () => {
    expect(MODES).toEqual(['walk', 'drive', 'transit'])
  })
})

describe('batteryWarning', () => {
  it('warns on a long (12 km) walk', () => {
    expect(batteryWarning(12000, 'walk')).toBe(true)
  })
  it('does not warn for a 12 km drive or a 1 km walk', () => {
    expect(batteryWarning(12000, 'drive')).toBe(false)
    expect(batteryWarning(1000, 'walk')).toBe(false)
  })
})

describe('nearestHub', () => {
  const origin = { lat: 10.5, lon: -66.9 }
  const hubs = [
    { id: 'far', lat: 11.0, lon: -66.9 },
    { id: 'near', lat: 10.51, lon: -66.9 },
    { id: 'mid', lat: 10.7, lon: -66.9 },
  ]
  it('picks the closest hub', () => {
    expect(nearestHub(origin, hubs).id).toBe('near')
  })
  it('returns null with no usable hubs', () => {
    expect(nearestHub(origin, [])).toBeNull()
    expect(nearestHub(null, hubs)).toBeNull()
  })
})

describe('hubToHub', () => {
  // Origin near Caracas; a far destination ~0.5° east (~55 km), with a hub
  // close to the origin so the two-leg plan is meaningfully better.
  const origin = { lat: 10.5, lon: -66.9 }
  const farDest = { lat: 10.5, lon: -66.4 }
  const hubs = [{ id: 'h1', name: 'Hub 1', lat: 10.51, lon: -66.89 }]

  it('returns a 2-leg plan for a far destination with a closer hub', () => {
    const plan = hubToHub(origin, farDest, hubs, { directThresholdM: 25000 })
    expect(plan).not.toBeNull()
    expect(plan.legs).toHaveLength(2)
    expect(plan.hub.id).toBe('h1')
    expect(plan.totalMeters).toBeGreaterThan(0)
    expect(plan.legs[0].from).toBe(origin)
    expect(plan.legs[1].to).toBe(farDest)
  })

  it('returns null for a near destination (direct route is fine)', () => {
    const nearDest = { lat: 10.51, lon: -66.9 }
    expect(hubToHub(origin, nearDest, hubs, { directThresholdM: 25000 })).toBeNull()
  })
})

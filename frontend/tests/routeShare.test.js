// Tests for the shared-route pure helpers (plan-21, Phase 5): payload building
// and the polyline → straight-line latlngs fallback. Server-free by design.
import { describe, expect, it } from 'vitest'
import { buildSharePayload, routeShareLatLngs } from '../src/lib/routeShare.js'

const origin = { lat: 10.5, lon: -66.9 }
const dest = { lat: 10.51, lon: -66.9, name: 'Refugio Norte' }
const POLY = [[10.5, -66.9], [10.505, -66.9], [10.51, -66.9]]

describe('routeShareLatLngs', () => {
  it('uses the stored polyline when present', () => {
    const rec = { polyline: POLY, origin_lat: 1, origin_lon: 2, dest_lat: 3, dest_lon: 4 }
    expect(routeShareLatLngs(rec)).toBe(POLY)
  })

  it('falls back to [[origin],[dest]] when the polyline is null', () => {
    const rec = { polyline: null, origin_lat: 10.5, origin_lon: -66.9, dest_lat: 10.51, dest_lon: -66.9 }
    expect(routeShareLatLngs(rec)).toEqual([[10.5, -66.9], [10.51, -66.9]])
  })

  it('falls back when the polyline has fewer than 2 points', () => {
    const rec = { polyline: [[1, 2]], origin_lat: 0, origin_lon: 0, dest_lat: 9, dest_lon: 9 }
    expect(routeShareLatLngs(rec)).toEqual([[0, 0], [9, 9]])
  })

  it('returns [] when neither polyline nor full endpoints are available', () => {
    expect(routeShareLatLngs({ polyline: null, origin_lat: 1, origin_lon: 2, dest_lat: null, dest_lon: 4 })).toEqual([])
    expect(routeShareLatLngs(null)).toEqual([])
  })
})

describe('buildSharePayload', () => {
  it('keeps the polyline when one is provided', () => {
    const p = buildSharePayload({ disasterId: 'd1', origin, dest, polyline: POLY, mode: 'walk', alias: 'Ana', now: 'T' })
    expect(p.polyline).toBe(POLY)
  })

  it('stores null when the polyline is absent (straight-line-only share)', () => {
    const p = buildSharePayload({ disasterId: 'd1', origin, dest, polyline: null, alias: 'Ana', now: 'T' })
    expect(p.polyline).toBeNull()
  })

  it('builds the right shape and stamps source + timestamps', () => {
    const p = buildSharePayload({ disasterId: 'd1', origin, dest, polyline: POLY, mode: 'drive', note: ' hola ', alias: 'Ana', now: 'STAMP' })
    expect(p).toEqual({
      disaster_id: 'd1',
      origin_lat: 10.5, origin_lon: -66.9,
      dest_lat: 10.51, dest_lon: -66.9,
      dest_name: 'Refugio Norte',
      polyline: POLY,
      mode: 'drive',
      author_alias: 'Ana',
      note: 'hola',
      source: 'web',
      createdAt: 'STAMP',
      updatedAt: 'STAMP',
    })
  })

  it('defaults alias to Invitado and mode to walk; trims note', () => {
    const p = buildSharePayload({ origin, dest, now: 'T' })
    expect(p.author_alias).toBe('Invitado')
    expect(p.mode).toBe('walk')
    expect(p.note).toBe('')
    expect(p.disaster_id).toBeNull()
  })

  it('coerces an unknown mode to walk', () => {
    expect(buildSharePayload({ origin, dest, mode: 'fly', now: 'T' }).mode).toBe('walk')
  })
})

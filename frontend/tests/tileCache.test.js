// Tests for the offline map-tile slippy-map math (plan-10). tilesForBounds is
// pure geometry, so it's testable without IndexedDB or the network.
import { describe, expect, it } from 'vitest'
import { tilesForBounds, tileKey } from '../src/lib/tileCache.js'

// A minimal Leaflet LatLngBounds-like stub.
const bounds = (w, s, e, n) => ({
  getWest: () => w, getSouth: () => s, getEast: () => e, getNorth: () => n,
})

describe('tilesForBounds', () => {
  it('returns the single covering tile at zoom 0', () => {
    // Bounds just inside the world edges: at z0 the whole map is one tile (0,0).
    const tiles = tilesForBounds(bounds(-179, -84, 179, 84), 0, 0)
    expect(tiles).toEqual([{ z: 0, x: 0, y: 0 }])
  })

  it('covers more tiles as zoom increases', () => {
    const small = tilesForBounds(bounds(-66.95, 10.45, -66.85, 10.55), 6, 6)
    const big = tilesForBounds(bounds(-66.95, 10.45, -66.85, 10.55), 6, 12)
    expect(big.length).toBeGreaterThan(small.length)
    // Every entry is a well-formed {z,x,y} with non-negative integer coords.
    for (const t of big) {
      expect(Number.isInteger(t.x) && t.x >= 0).toBe(true)
      expect(Number.isInteger(t.y) && t.y >= 0).toBe(true)
      expect(t.z).toBeGreaterThanOrEqual(6)
      expect(t.z).toBeLessThanOrEqual(12)
    }
  })

  it('honors the maxTiles cap so a careless download cannot run away', () => {
    const capped = tilesForBounds(bounds(-180, -85, 180, 85), 0, 19, 100)
    expect(capped.length).toBe(100)
  })

  it('builds a z/x/y cache key', () => {
    expect(tileKey(6, 17, 28)).toBe('6/17/28')
  })
})

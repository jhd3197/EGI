// Unit tests for the pure hazard-geometry helpers (plan-21, Phase 4) and for
// hazard-aware A* rerouting. Everything here is pure (no IndexedDB, no worker),
// so the helpers run verbatim the way they do inside the routing Web Worker.
import { describe, expect, it } from 'vitest'
import {
  pointInPolygon, pointInCircle, pointInHazard,
  segmentCrossesHazard, routeCrossesHazards, isHazardActive,
  makeBlockedEdge, HAZARD_META,
} from '../src/lib/hazards.js'
import { aStar, haversine } from '../src/lib/routeGraph.js'

// A square polygon hazard around (10.000..10.010, -66.010..-66.000).
const SQUARE = {
  type: 'flood',
  geometry: {
    kind: 'polygon',
    coords: [[10.000, -66.010], [10.000, -66.000], [10.010, -66.000], [10.010, -66.010]],
  },
}
// A circle hazard centred at (10.005, -66.005), radius 300 m.
const CIRCLE = {
  type: 'fire',
  geometry: { kind: 'circle', center: [10.005, -66.005], radius_m: 300 },
}

describe('pointInPolygon', () => {
  it('detects a point inside the ring', () => {
    expect(pointInPolygon([10.005, -66.005], SQUARE.geometry.coords)).toBe(true)
  })
  it('rejects a point outside the ring', () => {
    expect(pointInPolygon([10.020, -66.005], SQUARE.geometry.coords)).toBe(false)
    expect(pointInPolygon([10.005, -65.990], SQUARE.geometry.coords)).toBe(false)
  })
  it('is false for a degenerate ring', () => {
    expect(pointInPolygon([0, 0], [[0, 0], [1, 1]])).toBe(false)
    expect(pointInPolygon(null, SQUARE.geometry.coords)).toBe(false)
  })
})

describe('pointInCircle', () => {
  it('is true inside the radius and false outside', () => {
    expect(pointInCircle([10.005, -66.005], [10.005, -66.005], 300)).toBe(true) // centre
    // ~547 m east of centre -> outside a 300 m radius.
    expect(pointInCircle([10.005, -66.000], [10.005, -66.005], 300)).toBe(false)
  })
  it('is false for malformed input', () => {
    expect(pointInCircle(null, [0, 0], 100)).toBe(false)
    expect(pointInCircle([0, 0], null, 100)).toBe(false)
    expect(pointInCircle([0, 0], [0, 0], null)).toBe(false)
  })
})

describe('pointInHazard', () => {
  it('dispatches on geometry kind', () => {
    expect(pointInHazard([10.005, -66.005], SQUARE)).toBe(true)
    expect(pointInHazard([10.005, -66.005], CIRCLE)).toBe(true)
    expect(pointInHazard([11.0, -66.0], CIRCLE)).toBe(false)
  })
})

describe('segmentCrossesHazard', () => {
  it('is true when the segment passes through the hazard between its endpoints', () => {
    // Both endpoints are OUTSIDE the 300 m circle, but the segment's midpoint is
    // the circle centre -> sampling must catch it.
    const a = [10.005, -66.010]
    const b = [10.005, -66.000]
    expect(pointInHazard(a, CIRCLE)).toBe(false)
    expect(pointInHazard(b, CIRCLE)).toBe(false)
    expect(segmentCrossesHazard(a, b, CIRCLE)).toBe(true)
  })
  it('is false when the segment stays clear of the hazard', () => {
    const a = [10.030, -66.010]
    const b = [10.030, -66.000]
    expect(segmentCrossesHazard(a, b, CIRCLE)).toBe(false)
    expect(segmentCrossesHazard(a, b, SQUARE)).toBe(false)
  })
  it('is true when an endpoint is inside the hazard', () => {
    expect(segmentCrossesHazard([10.005, -66.005], [11.0, -66.0], CIRCLE)).toBe(true)
  })
})

describe('routeCrossesHazards', () => {
  it('returns the hazards a polyline intersects', () => {
    const line = [[10.005, -66.010], [10.005, -66.000]] // crosses the circle centre
    const hit = routeCrossesHazards(line, [CIRCLE, SQUARE])
    // The line runs along the polygon's mid-row too, so both are crossed.
    expect(hit).toContain(CIRCLE)
    expect(hit.length).toBeGreaterThanOrEqual(1)
  })
  it('returns [] when nothing is crossed', () => {
    const line = [[10.030, -66.010], [10.030, -66.000]]
    expect(routeCrossesHazards(line, [CIRCLE, SQUARE])).toEqual([])
  })
  it('handles a single-point polyline as a point test', () => {
    expect(routeCrossesHazards([[10.005, -66.005]], [CIRCLE])).toEqual([CIRCLE])
    expect(routeCrossesHazards([[11.0, -66.0]], [CIRCLE])).toEqual([])
  })
})

describe('isHazardActive', () => {
  const now = Date.parse('2026-06-27T12:00:00Z')
  it('treats missing time bounds as always active', () => {
    expect(isHazardActive({}, now)).toBe(true)
  })
  it('is inactive before active_from and after active_until', () => {
    expect(isHazardActive({ active_from: '2026-06-28T00:00:00Z' }, now)).toBe(false)
    expect(isHazardActive({ active_until: '2026-06-26T00:00:00Z' }, now)).toBe(false)
  })
  it('is active within the window', () => {
    expect(isHazardActive(
      { active_from: '2026-06-27T00:00:00Z', active_until: '2026-06-28T00:00:00Z' }, now,
    )).toBe(true)
  })
})

describe('HAZARD_META', () => {
  it('maps each hazard type to a label key + colour', () => {
    for (const tp of ['flood', 'landslide', 'fire', 'blocked_road', 'unsafe_zone']) {
      expect(HAZARD_META[tp].key).toBe('hazards.' + tp)
      expect(HAZARD_META[tp].color).toMatch(/^#[0-9A-Fa-f]{6}$/)
    }
  })
})

// A 4-node grid (no diagonals): node0 top-left, node1 east, node2 south, node3
// south-east. A direct edge 0-1 exists, plus the L-route 0-2-3-1. Spaced ~1.1 km.
//   0 --- 1
//   |     |
//   2 --- 3
function squareGraph() {
  const nodes = [
    [10.000, -66.000], // 0
    [10.000, -66.010], // 1 (east of 0)
    [10.010, -66.000], // 2 (south of 0)
    [10.010, -66.010], // 3 (south-east)
  ]
  const edge = (a, b) => [a, b, haversine(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1]), 2]
  const edges = [edge(0, 1), edge(0, 2), edge(2, 3), edge(1, 3)]
  return { id: 'sq', region: 'Test', bbox: [-66.011, 9.999, -65.999, 10.011], nodes, edges, version: 1 }
}

describe('aStar with hazard blocking', () => {
  const from = { lat: 10.000, lon: -66.000 } // node 0
  const to = { lat: 10.000, lon: -66.010 }   // node 1

  it('takes the direct edge when there is no hazard', () => {
    const res = aStar(squareGraph(), from, to)
    expect(res.ok).toBe(true)
    // Direct 0 -> 1 (two graph nodes visited).
    expect(res.nodes).toBe(2)
  })

  it('reroutes around a hazard that blocks the direct edge (longer path)', () => {
    const g = squareGraph()
    const direct = aStar(g, from, to)
    // A circle on the midpoint of edge 0-1 blocks the direct hop, forcing the
    // detour 0 -> 2 -> 3 -> 1.
    const hazards = [{ type: 'flood', geometry: { kind: 'circle', center: [10.000, -66.005], radius_m: 300 } }]
    const rerouted = aStar(g, from, to, { blockedEdge: makeBlockedEdge(hazards) })
    expect(rerouted.ok).toBe(true)
    expect(rerouted.nodes).toBeGreaterThan(direct.nodes)        // 4 vs 2
    expect(rerouted.meters).toBeGreaterThan(direct.meters)      // L-route is longer
  })

  it('makeBlockedEdge returns null (no-op) when there are no active hazards', () => {
    expect(makeBlockedEdge([])).toBe(null)
    expect(makeBlockedEdge([{ active_until: '2000-01-01T00:00:00Z', geometry: { kind: 'circle', center: [0, 0], radius_m: 1 } }])).toBe(null)
  })
})

// Unit tests for the pure offline-routing core (plan-21, Phase 2). aStar lives
// in src/lib/routeGraph.js so it's shared verbatim by the Web Worker and these
// tests — no IndexedDB or worker needed to exercise pathfinding.
import { describe, expect, it } from 'vitest'
import { aStar, nearestNode, packCovers, haversine } from '../src/lib/routeGraph.js'

// A 3x3 lat/lon grid with only horizontal+vertical edges (no diagonals), and a
// missing centre edge so a route from a corner can't cut straight across — it
// must follow the grid. Node ids are row*3 + col:
//   0 1 2
//   3 4 5
//   6 7 8
// Spaced ~0.001° apart (~111 m) so distances are easy to reason about.
function gridGraph() {
  const nodes = []
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) nodes.push([10.0 + r * 0.001, -66.0 + c * 0.001])
  }
  const edge = (a, b) => [a, b, haversine(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1]), 2]
  // Full horizontal + vertical grid EXCEPT the edges touching the centre node 4
  // along the 0->8 corridor are kept; we instead drop the direct 1-4 and 4-7 to
  // force the path to detour around the middle column.
  const edges = [
    edge(0, 1), edge(1, 2),
    edge(3, 4), edge(4, 5),
    edge(6, 7), edge(7, 8),
    edge(0, 3), edge(3, 6),
    edge(2, 5), edge(5, 8),
    // middle column verticals removed (no 1-4, no 4-7) -> detour required
  ]
  return {
    id: 'grid', region: 'Test',
    bbox: [-66.001, 9.999, -65.997, 10.003], // [minLon, minLat, maxLon, maxLat]
    nodes, edges, version: 1,
  }
}

describe('nearestNode', () => {
  it('snaps a free point to the closest graph node', () => {
    const g = gridGraph()
    // Just past node 0 (top-left) -> should snap to index 0.
    expect(nearestNode(g, { lat: 10.0001, lon: -66.0001 })).toBe(0)
    // Near node 8 (bottom-right).
    expect(nearestNode(g, { lat: 10.0019, lon: -65.9981 })).toBe(8)
  })

  it('returns -1 for an empty graph', () => {
    expect(nearestNode({ nodes: [] }, { lat: 1, lon: 1 })).toBe(-1)
  })
})

describe('aStar', () => {
  it('finds a road-following path that follows edges to the destination', () => {
    const g = gridGraph()
    const from = { lat: 10.0, lon: -66.0 }        // node 0
    const to = { lat: 10.002, lon: -65.998 }       // node 8
    const res = aStar(g, from, to)
    expect(res.ok).toBe(true)
    // Polyline starts at the real origin and ends at the real destination.
    expect(res.polyline[0]).toEqual([from.lat, from.lon])
    expect(res.polyline[res.polyline.length - 1]).toEqual([to.lat, to.lon])
    // It visited several graph nodes (an actual multi-hop path).
    expect(res.nodes).toBeGreaterThanOrEqual(4)
  })

  it('returns a road distance no shorter than the straight line', () => {
    const g = gridGraph()
    const from = { lat: 10.0, lon: -66.0 }
    const to = { lat: 10.002, lon: -65.998 }
    const straight = haversine(from.lat, from.lon, to.lat, to.lon)
    const res = aStar(g, from, to)
    expect(res.ok).toBe(true)
    // Following the L-shaped grid is strictly longer than the diagonal.
    expect(res.meters).toBeGreaterThan(straight)
  })

  it('returns no route when the destination is disconnected', () => {
    const g = gridGraph()
    // Add an isolated node far away with no edges; snap the destination to it.
    g.nodes.push([20.0, -50.0])
    const res = aStar(g, { lat: 10.0, lon: -66.0 }, { lat: 20.0, lon: -50.0 })
    expect(res.ok).toBe(false)
    expect(res.reason).toBe('no_route')
  })

  it('fails cleanly on an empty graph', () => {
    const res = aStar({ nodes: [], edges: [] }, { lat: 1, lon: 1 }, { lat: 2, lon: 2 })
    expect(res.ok).toBe(false)
    expect(res.reason).toBe('empty_graph')
  })
})

describe('packCovers', () => {
  it('tests bbox containment ([minLon,minLat,maxLon,maxLat])', () => {
    const graph = { bbox: [-67, 10, -66, 11] }
    expect(packCovers(graph, { lat: 10.5, lon: -66.5 })).toBe(true)
    expect(packCovers(graph, { lat: 12.0, lon: -66.5 })).toBe(false)   // lat out
    expect(packCovers(graph, { lat: 10.5, lon: -65.0 })).toBe(false)   // lon out
  })

  it('is false for a malformed/absent bbox', () => {
    expect(packCovers({}, { lat: 1, lon: 1 })).toBe(false)
    expect(packCovers({ bbox: [1, 2] }, { lat: 1, lon: 1 })).toBe(false)
  })
})

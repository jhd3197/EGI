// Pure offline road-routing core (plan-21, Phase 2). No DOM, no imports — so it
// runs identically inside the Web Worker (src/workers/routeWorker.js) and under
// vitest. Given a routing-pack graph and two free lat/lon points, it snaps each
// point to the nearest graph node and runs A* (Haversine heuristic) over the
// bidirectional edges, returning a road-following polyline.
//
// Graph format (matches the server's modules/routing.py EXACTLY):
//   nodes: [[lat, lon], ...]                  index = node id
//   edges: [[fromIdx, toIdx, meters, flags]]  bidirectional; meters precomputed

const R = 6371000

// Haversine distance in metres between two {lat,lon}-ish points or [lat,lon].
export function haversine(aLat, aLon, bLat, bLon) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(bLat - aLat)
  const dLon = toRad(bLon - aLon)
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(x))
}

// Index of the graph node nearest to {lat,lon}, or -1 if the graph has no nodes.
export function nearestNode(graph, point) {
  const nodes = (graph && graph.nodes) || []
  if (!point || point.lat == null || point.lon == null) return -1
  let best = -1
  let bestD = Infinity
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i]
    if (!n) continue
    const d = haversine(point.lat, point.lon, n[0], n[1])
    if (d < bestD) { bestD = d; best = i }
  }
  return best
}

// Build an adjacency list { from: [{ to, meters }] } from the bidirectional edge
// list. Cached on the graph object so repeated routes over one pack are cheap.
export function buildAdjacency(graph) {
  if (graph && graph.__adj) return graph.__adj
  const adj = new Map()
  const push = (a, b, m) => {
    if (!adj.has(a)) adj.set(a, [])
    adj.get(a).push({ to: b, meters: m })
  }
  for (const e of (graph && graph.edges) || []) {
    const [a, b, m] = e
    push(a, b, m)
    push(b, a, m) // edges are bidirectional
  }
  if (graph) {
    try { Object.defineProperty(graph, '__adj', { value: adj, enumerable: false }) }
    catch { /* frozen graph: skip cache */ }
  }
  return adj
}

// A* shortest path between two node indices. Returns { path:[idx...], meters } or
// null when unreachable. Uses a simple binary min-heap on the open set, which is
// plenty for the small packs EGI ships (tens–hundreds of nodes).
function aStarNodes(graph, startIdx, goalIdx, opts = {}) {
  const nodes = graph.nodes
  const adj = buildAdjacency(graph)
  // Optional hazard-aware edge filter (plan-21, Phase 4): block any edge whose
  // segment falls inside an active hazard so A* routes around it. Default =
  // no-op, so a route with no hazards behaves exactly as before.
  const blockedEdge = typeof opts.blockedEdge === 'function' ? opts.blockedEdge : null
  const h = (i) => haversine(nodes[i][0], nodes[i][1], nodes[goalIdx][0], nodes[goalIdx][1])

  const gScore = new Map([[startIdx, 0]])
  const cameFrom = new Map()
  // Min-heap of [fScore, nodeIdx].
  const heap = [[h(startIdx), startIdx]]
  const closed = new Set()

  const heapPush = (item) => {
    heap.push(item)
    let i = heap.length - 1
    while (i > 0) {
      const p = (i - 1) >> 1
      if (heap[p][0] <= heap[i][0]) break
      ;[heap[p], heap[i]] = [heap[i], heap[p]]
      i = p
    }
  }
  const heapPop = () => {
    const top = heap[0]
    const last = heap.pop()
    if (heap.length) {
      heap[0] = last
      let i = 0
      for (;;) {
        const l = 2 * i + 1, r = 2 * i + 2
        let s = i
        if (l < heap.length && heap[l][0] < heap[s][0]) s = l
        if (r < heap.length && heap[r][0] < heap[s][0]) s = r
        if (s === i) break
        ;[heap[s], heap[i]] = [heap[i], heap[s]]
        i = s
      }
    }
    return top
  }

  while (heap.length) {
    const [, current] = heapPop()
    if (current === goalIdx) {
      const path = [current]
      let c = current
      while (cameFrom.has(c)) { c = cameFrom.get(c); path.push(c) }
      path.reverse()
      return { path, meters: gScore.get(goalIdx) }
    }
    if (closed.has(current)) continue
    closed.add(current)
    for (const { to, meters } of adj.get(current) || []) {
      if (closed.has(to)) continue
      // Skip edges blocked by an active hazard (plan-21, Phase 4).
      if (blockedEdge && blockedEdge(nodes[current], nodes[to])) continue
      const tentative = (gScore.get(current) ?? Infinity) + meters
      if (tentative < (gScore.get(to) ?? Infinity)) {
        cameFrom.set(to, current)
        gScore.set(to, tentative)
        heapPush([tentative + h(to), to])
      }
    }
  }
  return null
}

// Route from one free point to another over the pack graph. Snaps both ends to
// their nearest node, runs A*, and returns a polyline of [lat,lon] pairs that
// includes the real origin/destination as the first/last points so the drawn
// line connects to where the user actually is.
//
// `opts.blockedEdge(aNode, bNode)` (optional, plan-21 Phase 4) blocks edges that
// fall inside an active hazard so the route avoids hazard zones; omit it (or pass
// {}) for the original hazard-free behaviour.
//
// Returns { ok:true, polyline, meters, nodes } or { ok:false, reason }.
export function aStar(graph, from, to, opts = {}) {
  if (!graph || !Array.isArray(graph.nodes) || graph.nodes.length === 0) {
    return { ok: false, reason: 'empty_graph' }
  }
  const s = nearestNode(graph, from)
  const g = nearestNode(graph, to)
  if (s < 0 || g < 0) return { ok: false, reason: 'no_snap' }
  if (s === g) {
    // Same nearest node: just connect the two free points through it.
    const node = graph.nodes[s]
    const polyline = [[from.lat, from.lon], [node[0], node[1]], [to.lat, to.lon]]
    return { ok: true, polyline, meters: haversine(from.lat, from.lon, to.lat, to.lon), nodes: 1 }
  }
  const res = aStarNodes(graph, s, g, opts)
  if (!res) return { ok: false, reason: 'no_route' }
  const nodeLine = res.path.map((i) => [graph.nodes[i][0], graph.nodes[i][1]])
  // Prepend the real origin and append the real destination so the polyline
  // reaches the actual endpoints, not just the snapped nodes.
  const polyline = [[from.lat, from.lon], ...nodeLine, [to.lat, to.lon]]
  // Total metres = snap-in leg + graph path + snap-out leg.
  const startNode = graph.nodes[s]
  const goalNode = graph.nodes[g]
  const meters =
    haversine(from.lat, from.lon, startNode[0], startNode[1]) +
    res.meters +
    haversine(goalNode[0], goalNode[1], to.lat, to.lon)
  return { ok: true, polyline, meters, nodes: res.path.length }
}

// Bounding-box containment test for a {lat,lon} point against a pack graph's
// bbox ([minLon, minLat, maxLon, maxLat]). Used to decide if a pack can route a
// given origin/destination before spending effort on A*.
export function packCovers(graph, point) {
  if (!graph || !Array.isArray(graph.bbox) || graph.bbox.length !== 4) return false
  if (!point || point.lat == null || point.lon == null) return false
  const [minLon, minLat, maxLon, maxLat] = graph.bbox
  return point.lon >= minLon && point.lon <= maxLon && point.lat >= minLat && point.lat <= maxLat
}

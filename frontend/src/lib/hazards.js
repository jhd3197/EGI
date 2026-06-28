// Pure hazard-geometry helpers for hazard-aware routing (plan-21, Phase 4). No
// DOM, no imports — so it runs identically inside the routing Web Worker
// (src/workers/routeWorker.js), in MapScreen/DirectionsScreen, and under vitest.
//
// A hazard record (see the server's /hazards contract) carries a geometry that
// is either a polygon ({kind:'polygon', coords:[[lat,lon],...]}) or a circle
// ({kind:'circle', center:[lat,lon], radius_m:N}). These helpers answer two
// questions cheaply and offline:
//   1. is a point inside a hazard?              (pointInHazard)
//   2. does a route/edge pass through a hazard? (segmentCrossesHazard / routeCrossesHazards)
// They are deliberately approximate (segment sampling, not exact polygon-segment
// intersection) — good enough for EGI's small, on-device hazard sets and cheap
// enough to call per graph edge during A*.

const R = 6371000

// Haversine distance in metres between two [lat,lon]-ish coordinate pairs.
function haversine(aLat, aLon, bLat, bLon) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(bLat - aLat)
  const dLon = toRad(bLon - aLon)
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(x))
}

// type → { i18n label key, map/overlay colour }. Used by view.js (display label
// + colour) and MapScreen (overlay/legend colours). Keep the type set in sync
// with the server's hazard `type` enum.
export const HAZARD_META = {
  flood: { key: 'hazards.flood', color: '#1F5E96' },
  landslide: { key: 'hazards.landslide', color: '#9A6400' },
  fire: { key: 'hazards.fire', color: '#C2272D' },
  blocked_road: { key: 'hazards.blocked_road', color: '#5A534C' },
  unsafe_zone: { key: 'hazards.unsafe_zone', color: '#7A3FA0' },
}

// Ray-casting point-in-polygon. `point` is [lat,lon]; `coords` is a ring of
// [lat,lon] pairs (lat as y, lon as x). Returns false for a degenerate ring.
export function pointInPolygon(point, coords) {
  if (!point || !Array.isArray(coords) || coords.length < 3) return false
  const lat = point[0]
  const lon = point[1]
  let inside = false
  for (let i = 0, j = coords.length - 1; i < coords.length; j = i++) {
    const latI = coords[i][0]
    const lonI = coords[i][1]
    const latJ = coords[j][0]
    const lonJ = coords[j][1]
    const intersect =
      ((latI > lat) !== (latJ > lat)) &&
      lon < ((lonJ - lonI) * (lat - latI)) / (latJ - latI) + lonI
    if (intersect) inside = !inside
  }
  return inside
}

// True when `point` ([lat,lon]) is within `radiusM` metres of `center`
// ([lat,lon]) by Haversine distance.
export function pointInCircle(point, center, radiusM) {
  if (!point || !Array.isArray(center) || radiusM == null) return false
  return haversine(point[0], point[1], center[0], center[1]) <= radiusM
}

// Dispatch a point test on the hazard's geometry kind.
export function pointInHazard(point, hazard) {
  if (!point || !hazard || !hazard.geometry) return false
  const g = hazard.geometry
  if (g.kind === 'polygon') return pointInPolygon(point, g.coords || [])
  if (g.kind === 'circle') return pointInCircle(point, g.center, g.radius_m)
  return false
}

// Whether the straight segment a→b ([lat,lon] each) passes through `hazard`.
//
// APPROXIMATION: rather than computing an exact polygon/circle–segment
// intersection, we sample the segment at its endpoints plus `samples`-1 evenly
// spaced interior points and test each. This can miss a hazard that the segment
// only clips between samples, but for EGI's short graph edges and modestly sized
// hazard zones it is accurate enough and cheap enough to call per A* edge. Bump
// `samples` for longer segments / smaller hazards if needed.
export function segmentCrossesHazard(a, b, hazard, samples = 12) {
  if (!a || !b || !hazard) return false
  if (pointInHazard(a, hazard) || pointInHazard(b, hazard)) return true
  const n = Math.max(2, samples | 0)
  for (let i = 1; i < n; i++) {
    const f = i / n
    const lat = a[0] + (b[0] - a[0]) * f
    const lon = a[1] + (b[1] - a[1]) * f
    if (pointInHazard([lat, lon], hazard)) return true
  }
  return false
}

// Given a polyline (`latlngs` = [[lat,lon],...]) and a list of hazards, return
// the subset of hazards the polyline intersects (each at most once). A single-
// point "polyline" degrades to a point-in-hazard test.
export function routeCrossesHazards(latlngs, hazards) {
  const out = []
  if (!Array.isArray(latlngs) || latlngs.length < 1 || !Array.isArray(hazards)) return out
  for (const h of hazards) {
    if (!h || !h.geometry) continue
    let hit = false
    if (latlngs.length === 1) {
      hit = pointInHazard(latlngs[0], h)
    } else {
      for (let i = 0; i < latlngs.length - 1 && !hit; i++) {
        if (segmentCrossesHazard(latlngs[i], latlngs[i + 1], h)) hit = true
      }
    }
    if (hit) out.push(h)
  }
  return out
}

// A hazard is "active" when `now` falls within its [active_from, active_until]
// window. Missing bounds are treated as open (always-on), and unparseable dates
// are ignored rather than hiding the hazard.
export function isHazardActive(hazard, now = Date.now()) {
  if (!hazard) return false
  const from = hazard.active_from ? Date.parse(hazard.active_from) : NaN
  const until = hazard.active_until ? Date.parse(hazard.active_until) : NaN
  if (!Number.isNaN(from) && now < from) return false
  if (!Number.isNaN(until) && now > until) return false
  return true
}

// Build a `blockedEdge(aNode, bNode)` predicate for aStar (src/lib/routeGraph.js)
// from a list of hazards: an edge is blocked when its segment crosses any ACTIVE
// hazard. Returns null when there are no active hazards so A* can skip the check
// entirely (and so the existing no-hazard behaviour is preserved bit-for-bit).
export function makeBlockedEdge(hazards, now) {
  const active = (Array.isArray(hazards) ? hazards : []).filter(
    (h) => h && h.geometry && isHazardActive(h, now),
  )
  if (!active.length) return null
  return (a, b) => active.some((h) => segmentCrossesHazard(a, b, h))
}

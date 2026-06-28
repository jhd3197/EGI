// Location-aware suggestions (plan-27.5 Phase 6). When a volunteer grants
// location access, the app proposes nearby actions: operations to join near you,
// facilities to check for matches. Suggestions are opt-in, respect Plan 24 quiet
// hours, and degrade gracefully offline (they only need the already-cached
// operation/facility lists plus one position fix).
import { getCurrentLocation, distanceMeters } from './directions.js'

export { getCurrentLocation }

// Default radius (metres) within which a target is "near you".
export const SUGGEST_RADIUS_M = 4000

// True when the local clock is inside the user's configured quiet hours. Mirrors
// the wrap-around handling used by the notification layer (e.g. 22→7). Quiet
// hours suppress proactive proximity prompts but never block manual navigation.
export function isQuietHours(settings, now = new Date()) {
  if (!settings) return false
  const start = settings.quietStart
  const end = settings.quietEnd
  if (start == null || end == null) return false
  const h = now.getHours()
  if (start === end) return false
  if (start < end) return h >= start && h < end
  // Wrap-around window (e.g. 22:00–07:00).
  return h >= start || h < end
}

// Build proximity suggestions from a position fix and the cached lists. Returns
// at most `limit` items sorted by ascending distance, each:
//   { id, kind: 'operation' | 'facility', name, distanceM }
// The caller turns these into localized labels + tap targets so this stays pure
// and testable.
export function buildSuggestions({ pos, operations = [], facilities = [], radiusM = SUGGEST_RADIUS_M, limit = 4 } = {}) {
  if (!pos || pos.lat == null || pos.lon == null) return []
  const out = []
  for (const op of operations) {
    if (op == null) continue
    if (op.status && op.status !== 'active') continue
    const lat = op.zone_lat, lon = op.zone_lon
    if (lat == null || lon == null) continue
    const d = distanceMeters(pos, { lat, lon })
    if (d == null || d > radiusM) continue
    out.push({ id: op.id, kind: 'operation', name: op.name || op.id, distanceM: Math.round(d) })
  }
  for (const fac of facilities) {
    if (fac == null || fac.lat == null || fac.lon == null) continue
    const d = distanceMeters(pos, { lat: fac.lat, lon: fac.lon })
    if (d == null || d > radiusM) continue
    out.push({ id: fac.id, kind: 'facility', name: fac.name || fac.id, distanceM: Math.round(d), kindLabel: fac.kind })
  }
  out.sort((a, b) => a.distanceM - b.distanceM)
  return out.slice(0, limit)
}

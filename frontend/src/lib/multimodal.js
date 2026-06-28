// Multi-modal routing helpers (plan-21, Phase 6). Pure + offline: turns a
// straight-line/road distance into per-mode arrival estimates, flags a long
// walk that warrants a "carry water / battery may not last" note (§9.4), and
// builds a long-distance hub-to-hub evacuation plan (§9.2). Nothing here throws;
// every path degrades to a sane default (null / false) so the UI stays simple.
import { distanceMeters, travelMinutes } from './directions.js'

// Supported travel modes + their per-mode cruising speed (km/h) and i18n key.
// Transit has no speed/GTFS data yet, so its estimate degrades to "no data".
export const MODES = ['walk', 'drive', 'transit']

export const MODE_META = {
  walk: { kmh: 5, key: 'directions.mode.walk' },
  drive: { kmh: 40, key: 'directions.mode.drive' },
  transit: { kmh: null, key: 'directions.mode.transit' },
}

// Per-mode arrival-time range in minutes: a single ETA padded by a spread that
// reflects each mode's real-world variability (walk ±15%, drive ±30% traffic).
// Returns null when the mode has no usable estimate (transit: no GTFS data yet),
// or when the distance is unknown. The range always satisfies min < max.
export function estimateArrival(meters, mode = 'walk') {
  const meta = MODE_META[mode]
  if (!meta || meta.kmh == null) return null
  const base = travelMinutes(meters, meta.kmh)
  if (base == null) return null
  const spread = mode === 'drive' ? 0.30 : 0.15
  const minMinutes = Math.max(1, Math.round(base * (1 - spread)))
  const maxMinutes = Math.max(minMinutes + 1, Math.round(base * (1 + spread)))
  return { minMinutes, maxMinutes }
}

// Long-walk warning (§9.4): true when the trip is on foot AND long enough that a
// walker should carry water and expect their phone battery to run low — over
// 10 km, or more than two hours of walking. Driving/transit never warn.
export function batteryWarning(meters, mode = 'walk') {
  if (mode !== 'walk' || meters == null) return false
  const min = travelMinutes(meters, MODE_META.walk.kmh)
  return meters > 10000 || (min != null && min > 120)
}

// The hub (shelter with coords) closest to `origin` by straight-line distance,
// or null when there are no usable hubs.
export function nearestHub(origin, hubs) {
  if (!origin || origin.lat == null || !Array.isArray(hubs)) return null
  let best = null
  let bestD = Infinity
  for (const h of hubs) {
    if (!h || h.lat == null || h.lon == null) continue
    const d = distanceMeters(origin, h)
    if (d != null && d < bestD) { bestD = d; best = h }
  }
  return best
}

// Long-distance evacuation helper (§9.2). When origin↔dest is farther than
// `directThresholdM` (e.g. 25 km) AND a hub sits meaningfully closer to the
// origin than the destination is (under 80% of the direct distance), return a
// two-leg plan origin → nearest hub → dest. Otherwise null (a direct route is
// fine, or no hub helps).
export function hubToHub(origin, dest, hubs, { directThresholdM = 25000 } = {}) {
  if (!origin || !dest || origin.lat == null || dest.lat == null) return null
  const direct = distanceMeters(origin, dest)
  if (direct == null || direct <= directThresholdM) return null
  const hub = nearestHub(origin, hubs)
  if (!hub) return null
  const originToHub = distanceMeters(origin, hub)
  const hubToDest = distanceMeters(hub, dest)
  if (originToHub == null || hubToDest == null) return null
  // The hub only helps if it's meaningfully closer to the origin than the
  // destination already is — otherwise a direct route is just as good.
  if (originToHub >= direct * 0.8) return null
  return {
    legs: [
      { from: origin, to: hub, meters: originToHub },
      { from: hub, to: dest, meters: hubToDest },
    ],
    hub,
    totalMeters: originToHub + hubToDest,
  }
}

// Directions helper (plan-20 §5). Offline-first "how to get there":
//   * Prefer a native turn-by-turn handoff when running inside the Android app
//     (window.EgiNative.openTurnByTurn → Google Maps / OsmAnd / Waze intent).
//   * Fall back to an OpenStreetMap directions URL in a plain browser.
//   * Expose the device location + a straight-line distance/time estimate so the
//     embedded offline map can draw a simple route without any network.
// Nothing here throws; every path degrades to a sane default.
import { metaGet, metaSet } from './db.js'

const hasNative = () => typeof window !== 'undefined' && !!window.EgiNative

// Launch external turn-by-turn navigation to (lat,lng). Returns true if handled.
export function openTurnByTurn(lat, lng, label = '') {
  if (lat == null || lng == null) return false
  if (hasNative() && typeof window.EgiNative.openTurnByTurn === 'function') {
    try { window.EgiNative.openTurnByTurn(Number(lat), Number(lng), String(label || '')); return true }
    catch (e) { console.debug('[dir] native openTurnByTurn failed', e) }
  }
  try {
    const q = `${lat}%2C${lng}`
    const url = `https://www.openstreetmap.org/directions?to=${q}`
    if (typeof window !== 'undefined' && window.open) window.open(url, '_blank', 'noopener')
    return true
  } catch (e) { console.debug('[dir] url fallback failed', e); return false }
}

// Resolve the device's current location, or null if denied/unavailable.
export function getCurrentLocation(timeoutMs = 8000) {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) { resolve(null); return }
    try {
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 },
      )
    } catch { resolve(null) }
  })
}

// Haversine straight-line distance in metres between {lat,lon} points.
export function distanceMeters(a, b) {
  if (!a || !b || a.lat == null || b.lat == null) return null
  const R = 6371000, toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon)
  const x = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(x))
}

// Rough walking time in minutes (≈5 km/h). Minimum 1 min.
export function walkingMinutes(meters) {
  if (meters == null) return null
  return Math.max(1, Math.round(meters / (5000 / 60)))
}

// Cache the last requested route for offline reference (plan-20 §5).
export async function cacheRoute(route) {
  try { await metaSet('lastRoute', route) } catch { /* ignore */ }
}
export async function getCachedRoute() {
  try { return (await metaGet('lastRoute')) || null } catch { return null }
}

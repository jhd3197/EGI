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

// Read a cached/native fix from the Android bridge, or null. Synchronous +
// instant (plan-21 §3.4): the native side caches the last known position so
// "my location" routing needs no GPS round-trip. Returns {lat,lon[,at]} | null.
function nativePosition() {
  try {
    if (!hasNative() || typeof window.EgiNative.getCurrentPosition !== 'function') return null
    const raw = window.EgiNative.getCurrentPosition()
    if (!raw) return null
    const p = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (p && typeof p.lat === 'number' && typeof p.lon === 'number') {
      return { lat: p.lat, lon: p.lon, at: p.at }
    }
  } catch (e) { console.debug('[dir] native getCurrentPosition failed', e) }
  return null
}

// Resolve the device's current location, or null if denied/unavailable. Prefers
// the native bridge's cached fix (instant, works inside the Android WebView where
// navigator.geolocation may be ungranted), then falls back to the browser API.
export function getCurrentLocation(timeoutMs = 8000) {
  const native = nativePosition()
  if (native) return Promise.resolve(native)
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

// Travel time in minutes for a given speed in km/h (plan-21 §9 multi-modal).
export function travelMinutes(meters, kmh = 5) {
  if (meters == null || !kmh) return null
  return Math.max(1, Math.round(meters / ((kmh * 1000) / 60)))
}

// Initial bearing in degrees (0–360, 0 = north) from a → b along the great circle.
export function bearing(a, b) {
  if (!a || !b || a.lat == null || b.lat == null) return null
  const toRad = (d) => (d * Math.PI) / 180
  const toDeg = (r) => (r * 180) / Math.PI
  const lat1 = toRad(a.lat), lat2 = toRad(b.lat)
  const dLon = toRad(b.lon - a.lon)
  const y = Math.sin(dLon) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon)
  return (toDeg(Math.atan2(y, x)) + 360) % 360
}

// 8-point compass key for a bearing (i18n key suffix: dir.n, dir.ne, …). The
// caller translates `dir.<key>` so the cardinal name stays language-correct.
const COMPASS = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']
export function cardinalKey(deg) {
  if (deg == null) return null
  return COMPASS[Math.round(deg / 45) % 8]
}

// Human distance string. `unit` is 'km' (default) or 'mi'. Sub-1km/mi shows metres/feet.
export function formatDistance(meters, unit = 'km') {
  if (meters == null) return ''
  if (unit === 'mi') {
    const miles = meters / 1609.344
    if (miles < 0.19) return `${Math.round(meters / 0.3048)} ft`
    return `${miles.toFixed(miles < 10 ? 1 : 0)} mi`
  }
  if (meters < 950) return `${Math.round(meters / 10) * 10} m`
  const km = meters / 1000
  return `${km.toFixed(km < 10 ? 1 : 0)} km`
}

// Cache the last requested route for offline reference (plan-20 §5).
export async function cacheRoute(route) {
  try { await metaSet('lastRoute', route) } catch { /* ignore */ }
}
export async function getCachedRoute() {
  try { return (await metaGet('lastRoute')) || null } catch { return null }
}

// Rolling history of the last 20 computed routes (plan-21 §4.5), newest first.
// De-duplicated by destination name + coords so re-routing the same place
// refreshes rather than piling up. Stored in IndexedDB `meta` (device-only).
const ROUTE_HISTORY_KEY = 'routeHistory'
const ROUTE_HISTORY_MAX = 20

export async function getRouteHistory() {
  try {
    const list = await metaGet(ROUTE_HISTORY_KEY)
    return Array.isArray(list) ? list : []
  } catch { return [] }
}

export async function addRouteToHistory(route) {
  if (!route || !route.to) return []
  try {
    const list = await getRouteHistory()
    const key = (r) => `${r.to && r.to.lat},${r.to && r.to.lon}`
    const next = [route, ...list.filter((r) => key(r) !== key(route))].slice(0, ROUTE_HISTORY_MAX)
    await metaSet(ROUTE_HISTORY_KEY, next)
    return next
  } catch { return [] }
}

export async function clearRouteHistory() {
  try { await metaSet(ROUTE_HISTORY_KEY, []) } catch { /* ignore */ }
}

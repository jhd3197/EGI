// Shared-route helpers (plan-21 Phase 5). A responder computes a (verified-safe)
// route and shares it to nearby devices; others see it as a suggestion. These
// are pure, server-free helpers so the payload shape and the polyline fallback
// can be unit-tested in isolation (see tests/routeShare.test.js).

// Build the POST /routes/share request body from the directions-screen inputs.
// `origin`/`dest` are { lat, lon, name? }; `polyline` is [[lat,lon],...] or null
// (null = only a straight line is known). createdAt/updatedAt are stamped now
// (override via `now` for deterministic tests).
export function buildSharePayload({
  disasterId = null, origin = null, dest = null, polyline = null,
  mode = 'walk', note = '', alias = 'Invitado', now = null,
} = {}) {
  const ts = now || new Date().toISOString()
  const hasPolyline = Array.isArray(polyline) && polyline.length > 1
  return {
    disaster_id: disasterId || null,
    origin_lat: origin ? origin.lat : null,
    origin_lon: origin ? origin.lon : null,
    dest_lat: dest ? dest.lat : null,
    dest_lon: dest ? dest.lon : null,
    dest_name: (dest && dest.name) || '',
    polyline: hasPolyline ? polyline : null,
    mode: mode === 'drive' ? 'drive' : 'walk',
    author_alias: (alias && String(alias).trim()) || 'Invitado',
    note: (note || '').trim(),
    source: 'web',
    createdAt: ts,
    updatedAt: ts,
  }
}

// Resolve the latlngs to draw for a shared-route record: prefer the stored
// polyline, else fall back to a 2-point [origin, dest] straight line. Returns []
// when neither is usable (so a caller can skip drawing).
export function routeShareLatLngs(record) {
  if (!record) return []
  const poly = record.polyline
  if (Array.isArray(poly) && poly.length > 1) return poly
  const o = [record.origin_lat, record.origin_lon]
  const d = [record.dest_lat, record.dest_lon]
  if (o[0] == null || o[1] == null || d[0] == null || d[1] == null) return []
  return [o, d]
}

// Map view (plan-10): persons/reports by location with clustering, an "search
// this area" radius query, and offline tile caching for a pre-downloaded region.
//
// Leaflet + markercluster are imported here (not at app top level) so they only
// load when the map screen is opened. The whole UI keeps the project's inline-
// style convention; Leaflet's own CSS is imported for the map canvas/controls.
import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { getTile, tileKey, prefetchRegion, countTiles, clearTiles } from '../lib/tileCache.js'

const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_SUBDOMAINS = ['a', 'b', 'c']
// A safe default view (Venezuela) until we have points to fit.
const DEFAULT_CENTER = [8.0, -66.0]
const DEFAULT_ZOOM = 6

// Status → marker colour, matching the registry status palette.
const STATUS_COLOR = {
  missing: '#E5343B', sighted: '#C77D11', safe: '#1B7A45',
  care: '#1F5E96', deceased: '#5A534C', found: '#1B7A45',
}
const colorFor = (s) => STATUS_COLOR[s] || '#E5343B'

// Build the OSM URL for a tile coord, round-robining subdomains deterministically.
const tileUrlFor = ({ z, x, y }) =>
  TILE_URL
    .replace('{s}', TILE_SUBDOMAINS[(x + y) % TILE_SUBDOMAINS.length])
    .replace('{z}', z).replace('{x}', x).replace('{y}', y)

// A TileLayer that serves a cached tile from IndexedDB when present, else loads
// it from the network — so a region downloaded for offline use keeps rendering
// with no connectivity. Never auto-caches on pan (that's the explicit "download"
// action's job), keeping storage bounded and predictable.
const OfflineTileLayer = L.TileLayer.extend({
  createTile(coords, done) {
    const img = document.createElement('img')
    img.setAttribute('role', 'presentation')
    img.alt = ''
    const onDone = () => done(null, img)
    img.addEventListener('load', onDone)
    img.addEventListener('error', onDone)
    const key = tileKey(coords.z, coords.x, coords.y)
    getTile(key).then((blob) => {
      if (blob) img.src = URL.createObjectURL(blob)
      else img.src = this.getTileUrl(coords)
    }).catch(() => { img.src = this.getTileUrl(coords) })
    return img
  },
})

// Small colour dot marker (a divIcon avoids Leaflet's default-marker asset paths,
// which break under bundlers, and lets us colour by status).
const dotIcon = (color) =>
  L.divIcon({
    className: '',
    html: `<span style="display:block;width:16px;height:16px;border-radius:50%;background:${color};border:2.5px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })

export default function MapScreen({ view, actions }) {
  const { t } = useI18n()
  const mapEl = useRef(null)
  const mapRef = useRef(null)
  const clusterRef = useRef(null)
  const radiusRef = useRef(null)
  const routeRef = useRef(null)
  const hazardRef = useRef(null)
  const [tileCount, setTileCount] = useState(0)
  const [downloading, setDownloading] = useState(null) // {done,total} | null
  const [nearbyMsg, setNearbyMsg] = useState('')
  // Hazard reporting (plan-21 Phase 4): drop a circle hazard at the map centre.
  const [hazardType, setHazardType] = useState('flood')

  const people = view.mapPeople || []
  // Active, non-rejected hazards to draw (view.hazards is already decorated).
  const hazards = (view.hazards || []).filter((h) => h.active)

  // --- init the map once ---
  useEffect(() => {
    if (mapRef.current || !mapEl.current) return
    const map = L.map(mapEl.current, { zoomControl: true }).setView(DEFAULT_CENTER, DEFAULT_ZOOM)
    new OfflineTileLayer(TILE_URL, {
      subdomains: TILE_SUBDOMAINS,
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(map)
    const cluster = L.markerClusterGroup({ maxClusterRadius: 50 })
    map.addLayer(cluster)
    mapRef.current = map
    clusterRef.current = cluster
    countTiles().then(setTileCount)
    // Leaflet needs a size recalculation once the container has laid out.
    setTimeout(() => map.invalidateSize(), 60)
    return () => { map.remove(); mapRef.current = null; clusterRef.current = null }
  }, [])

  // --- (re)draw markers when the people set changes ---
  useEffect(() => {
    const cluster = clusterRef.current
    const map = mapRef.current
    if (!cluster || !map) return
    cluster.clearLayers()
    const latlngs = []
    for (const p of people) {
      if (typeof p.lat !== 'number' || typeof p.lon !== 'number') continue
      const m = L.marker([p.lat, p.lon], { icon: dotIcon(colorFor(p.status)) })
      const safeName = (p.name || t('common.noName'))
      m.bindPopup(
        `<strong>${escapeHtml(safeName)}</strong><br>${escapeHtml(p.statusLabel || p.status || '')}` +
        `<br><span style="color:#6E685E">${escapeHtml(p.location || '')}</span>`
      )
      m.on('click', () => { if (p.open) setTimeout(p.open, 10) })
      cluster.addLayer(m)
      latlngs.push([p.lat, p.lon])
    }
    if (latlngs.length) {
      try { map.fitBounds(L.latLngBounds(latlngs).pad(0.2), { maxZoom: 14 }) } catch (e) { /* single point */ }
    }
  }, [people, t])

  // --- draw the offline road-route polyline (plan-21 Phase 2) ---
  // When the Directions screen computes a road-following route it stashes the
  // polyline in state; draw it here and fit the map to it. Cleaned up on change.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (routeRef.current) { map.removeLayer(routeRef.current); routeRef.current = null }
    const line = view.routePolyline
    if (!line || !line.length) return
    routeRef.current = L.polyline(line, { color: '#1F5E96', weight: 5, opacity: 0.8 }).addTo(map)
    try { map.fitBounds(routeRef.current.getBounds().pad(0.2), { maxZoom: 16 }) } catch (e) { /* single point */ }
  }, [view.routePolyline])

  // --- draw hazard overlays (plan-21 Phase 4) ---
  // Each active hazard renders as a coloured polygon or circle; unverified
  // (reviewed=0, crowd-reported) hazards get a dashed outline + an "unverified"
  // note in their popup. The whole group is rebuilt on change.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (hazardRef.current) { map.removeLayer(hazardRef.current); hazardRef.current = null }
    if (!hazards.length) return
    const group = L.layerGroup()
    for (const h of hazards) {
      const g = h.geometry || {}
      const style = {
        color: h.color, weight: 2, fillColor: h.color, fillOpacity: 0.18,
        dashArray: h.unverified ? '6 4' : undefined,
      }
      let layer = null
      if (g.kind === 'polygon' && Array.isArray(g.coords) && g.coords.length >= 3) {
        layer = L.polygon(g.coords, style)
      } else if (g.kind === 'circle' && Array.isArray(g.center)) {
        layer = L.circle(g.center, { radius: g.radius_m || 100, ...style })
      }
      if (!layer) continue
      const note = h.note ? `<br>${escapeHtml(h.note)}` : ''
      const unv = h.unverified
        ? `<br><span style="color:#9A6400">⚠ ${escapeHtml(t('hazards.unverified'))}</span>`
        : ''
      layer.bindPopup(`<strong>${escapeHtml(h.typeLabel || h.type || '')}</strong>${note}${unv}`)
      group.addLayer(layer)
    }
    group.addTo(map)
    hazardRef.current = group
  }, [hazards, t])

  // --- "search this area": radius query around the current map centre ---
  const searchArea = async () => {
    const map = mapRef.current
    if (!map) return
    const c = map.getCenter()
    // Radius = distance from centre to the visible edge (metres).
    const edge = map.getBounds().getNorthEast()
    const radius = Math.round(map.distance(c, edge))
    if (radiusRef.current) { map.removeLayer(radiusRef.current); radiusRef.current = null }
    radiusRef.current = L.circle([c.lat, c.lng], {
      radius, color: '#E5343B', weight: 1.5, fillColor: '#E5343B', fillOpacity: 0.08,
    }).addTo(map)
    setNearbyMsg(t('map.searching'))
    try {
      const res = await actions.searchNearby(c.lat, c.lng, radius)
      const n = (res && res.records ? res.records.length : 0)
      setNearbyMsg(t('map.nearbyResult', { n }))
    } catch (e) {
      setNearbyMsg(t('map.searchError'))
    }
  }

  // --- download the visible region for offline use ---
  const downloadRegion = async () => {
    const map = mapRef.current
    if (!map || downloading) return
    const z = map.getZoom()
    const minZoom = Math.max(1, z - 1)
    const maxZoom = Math.min(16, z + 2)
    setDownloading({ done: 0, total: 0 })
    const { saved } = await prefetchRegion(
      map.getBounds(), minZoom, maxZoom, tileUrlFor,
      (done, total) => setDownloading({ done, total }),
    )
    setDownloading(null)
    const total = await countTiles()
    setTileCount(total)
    setNearbyMsg(t('map.downloaded', { n: saved }))
  }

  const clearOffline = async () => {
    await clearTiles()
    setTileCount(0)
    setNearbyMsg(t('map.cacheCleared'))
  }

  // --- report a hazard at the current map centre (plan-21 Phase 4) ---
  // Drops a circle hazard of the chosen type at the map centre. Queued for
  // moderation server-side (reviewed=0); shows immediately via the optimistic add.
  const reportHazardHere = () => {
    const map = mapRef.current
    if (!map) return
    const c = map.getCenter()
    actions.reportHazard({
      type: hazardType,
      geometry: { kind: 'circle', center: [c.lat, c.lng], radius_m: 150 },
      note: '',
    })
    setNearbyMsg(t('hazards.reported'))
  }

  // Hazard types present among the active overlays, for a compact legend.
  const HAZARD_TYPES = ['flood', 'landslide', 'fire', 'blocked_road', 'unsafe_zone']
  const HAZARD_COLOR = { flood: '#1F5E96', landslide: '#9A6400', fire: '#C2272D', blocked_road: '#5A534C', unsafe_zone: '#7A3FA0' }
  const legendTypes = HAZARD_TYPES.filter((tp) => hazards.some((h) => h.type === tp))

  const withCoords = people.filter((p) => typeof p.lat === 'number' && typeof p.lon === 'number').length

  return (
    <div style={css('padding:16px 16px 28px;display:flex;flex-direction:column;gap:12px;')}>
      <div>
        <h1 style={css("font:600 19px 'IBM Plex Sans';color:#1A1714;margin:0;")}>{t('map.title')}</h1>
        <p style={css("font:400 12.5px 'IBM Plex Sans';color:#6E685E;margin:4px 0 0;")}>
          {t('map.subtitle', { n: withCoords })}
        </p>
      </div>

      <div
        ref={mapEl}
        role="application"
        aria-label={t('map.title')}
        style={css('width:100%;height:58vh;min-height:320px;border-radius:14px;overflow:hidden;border:1px solid #E2DED8;z-index:0;')}
      />

      <div style={css('display:flex;flex-wrap:wrap;gap:8px;align-items:center;')}>
        <button onClick={searchArea} className="egi-tap"
          style={css("padding:10px 14px;border:none;border-radius:11px;background:#E5343B;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>
          {t('map.searchArea')}
        </button>
        <button onClick={() => actions.openDirections()} className="egi-tap"
          style={css("padding:10px 14px;border:1px solid #E2DED8;border-radius:11px;background:#fff;color:#1A1714;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>
          {t('nav.directions')}
        </button>
        <button onClick={downloadRegion} disabled={!!downloading} className="egi-tap"
          style={{ ...css("padding:10px 14px;border:1px solid #E2DED8;border-radius:11px;background:#fff;color:#1A1714;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"), opacity: downloading ? 0.6 : 1 }}>
          {downloading
            ? t('map.downloading', { done: downloading.done, total: downloading.total })
            : t('map.download')}
        </button>
        {tileCount > 0 && (
          <button onClick={clearOffline} className="egi-tap"
            style={css("padding:10px 14px;border:1px solid #E2DED8;border-radius:11px;background:#fff;color:#6E685E;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>
            {t('map.clearCache', { n: tileCount })}
          </button>
        )}
      </div>

      {/* Report a hazard zone at the map centre (plan-21 Phase 4) */}
      <div style={css('display:flex;flex-wrap:wrap;gap:8px;align-items:center;')}>
        <select value={hazardType} onChange={(e) => setHazardType(e.target.value)} aria-label={t('hazards.report')}
          style={css("padding:9px 10px;border:1px solid #E2DED8;border-radius:11px;background:#fff;color:#1A1714;font:600 12px 'IBM Plex Sans';cursor:pointer;")}>
          {['flood', 'landslide', 'fire', 'blocked_road', 'unsafe_zone'].map((tp) => (
            <option key={tp} value={tp}>{t('hazards.' + tp)}</option>
          ))}
        </select>
        <button onClick={reportHazardHere} className="egi-tap"
          style={css("padding:10px 14px;border:1px solid #E2DED8;border-radius:11px;background:#FCEDEC;color:#B7242A;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>
          {t('hazards.reportHere')}
        </button>
      </div>

      {nearbyMsg && (
        <div aria-live="polite" style={css("font:500 12px 'IBM Plex Mono';color:#15683A;")}>{nearbyMsg}</div>
      )}

      {/* Hazard legend (only the types currently shown) */}
      {legendTypes.length > 0 && (
        <div style={css('display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:2px;')}>
          <span style={css("font:600 11px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;text-transform:uppercase;")}>{t('hazards.legend')}</span>
          {legendTypes.map((tp) => (
            <span key={tp} style={css('display:flex;align-items:center;gap:6px;')}>
              <span style={{ ...css('width:12px;height:12px;border-radius:3px;'), background: HAZARD_COLOR[tp], opacity: 0.5, border: `2px solid ${HAZARD_COLOR[tp]}` }} />
              <span style={css("font:500 11px 'IBM Plex Sans';color:#5A534C;")}>{t('hazards.' + tp)}</span>
            </span>
          ))}
        </div>
      )}

      {/* Status legend */}
      <div style={css('display:flex;flex-wrap:wrap;gap:12px;margin-top:2px;')}>
        {[['missing', t('filter.missing')], ['sighted', t('filter.sighted')], ['safe', t('filter.safe')], ['care', t('filter.care')]].map(([k, lbl]) => (
          <span key={k} style={css('display:flex;align-items:center;gap:6px;')}>
            <span style={{ ...css('width:12px;height:12px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.25);'), background: colorFor(k) }} />
            <span style={css("font:500 11px 'IBM Plex Sans';color:#5A534C;")}>{lbl}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// Minimal HTML escaping for popup text (names/locations are user-supplied).
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

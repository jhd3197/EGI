// Offline "Directions" screen (plan-21, Phase 1). Pick an origin X (my location,
// typed coordinates, or a landmark on the registry) and a destination Y (a
// shelter, a person's last-known location, or typed coordinates) and get a
// straight-line distance, walking-time estimate, compass bearing, and a simple
// step list — all computed on-device with no network. A native turn-by-turn
// handoff (Android maps app) is offered when a destination has coordinates.
//
// Road-following routes (Phase 2) layer on top of this fallback; this screen
// always works because Haversine + a walking-speed heuristic need no data pack.
import { useEffect, useMemo, useRef, useState } from 'react'
import { css } from '../lib/css.js'
import { routeCrossesHazards } from '../lib/hazards.js'
import { useI18n } from '../i18n/index.js'
import {
  getCurrentLocation, distanceMeters, walkingMinutes, bearing, cardinalKey,
  formatDistance, openTurnByTurn, cacheRoute, addRouteToHistory, getRouteHistory,
} from '../lib/directions.js'
import {
  findCoveringLocalPack, computeRoadRoute, fetchPackIndex, fetchAndCachePack, packCovers,
} from '../lib/routePack.js'

// API base for pack downloads: same-origin by default, overridable like store.js.
const API_BASE = (typeof window !== 'undefined' && localStorage.getItem('egi_api_url')) || ''
const isOnline = () => typeof navigator === 'undefined' || navigator.onLine

// Parse "lat, lon" (or "lat lon") free text into a point, or null.
function parseCoords(text) {
  const m = String(text || '').match(/(-?\d+\.?\d*)\s*[, ]\s*(-?\d+\.?\d*)/)
  if (!m) return null
  const lat = parseFloat(m[1]), lon = parseFloat(m[2])
  if (Number.isNaN(lat) || Number.isNaN(lon)) return null
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
  return { lat, lon }
}

export default function DirectionsScreen({ view, actions }) {
  const { t } = useI18n()
  const dest0 = view.directionsTarget
  const candidates = view.directionsDestinations || { shelters: [], people: [] }

  // Origin: 'me' resolves geolocation on demand; 'coords' uses a typed point.
  const [originMode, setOriginMode] = useState('me')
  const [origin, setOrigin] = useState(null)
  const [originText, setOriginText] = useState('')
  const [locating, setLocating] = useState(false)
  const [locError, setLocError] = useState('')

  // Destination: preselected target, a chosen candidate, or typed coords.
  const [dest, setDest] = useState(dest0 || null)
  const [destText, setDestText] = useState('')
  const [unit, setUnit] = useState('km')
  const [history, setHistory] = useState([])

  // Road-following route (plan-21 Phase 2): computed in a Web Worker over a
  // locally-cached routing pack. null = none; 'computing' = in flight; otherwise
  // { meters, nodes }. `downloadablePack` is a server pack covering the area that
  // isn't cached yet (offers a download affordance); `downloading` gates it.
  const [roadRoute, setRoadRoute] = useState(null)
  const [downloadablePack, setDownloadablePack] = useState(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => { getRouteHistory().then(setHistory) }, [])
  // Re-sync when navigated in with a fresh preselected target.
  useEffect(() => { if (dest0) setDest(dest0) }, [dest0])

  const resolveOrigin = async () => {
    if (originMode === 'coords') {
      const p = parseCoords(originText)
      setLocError(p ? '' : t('directions.badCoords'))
      return p
    }
    setLocating(true); setLocError('')
    const loc = await getCurrentLocation()
    setLocating(false)
    if (!loc) { setLocError(t('directions.noLocation')); return null }
    setOrigin(loc)
    return loc
  }

  const effectiveOrigin = useMemo(() => {
    if (originMode === 'coords') return parseCoords(originText)
    return origin
  }, [originMode, originText, origin])

  // Active hazards (plan-21 Phase 4): used to (a) bias the road route around them
  // via the worker and (b) warn when the shown route crosses one. Kept in a ref
  // so the road-route effect can read the latest set without re-running on every
  // render (view.hazards is a fresh array each render).
  const activeHazards = (view.hazards || []).filter((h) => h.active)
  const activeHazardsRef = useRef(activeHazards)
  activeHazardsRef.current = activeHazards

  // Compute the straight-line route whenever origin + dest are both known.
  const route = useMemo(() => {
    if (!effectiveOrigin || !dest || dest.lat == null) return null
    const meters = distanceMeters(effectiveOrigin, dest)
    const deg = bearing(effectiveOrigin, dest)
    const ck = cardinalKey(deg)
    return {
      meters,
      minutes: walkingMinutes(meters),
      bearingDeg: deg == null ? null : Math.round(deg),
      cardinal: ck ? t('dir.' + ck) : '',
      distLabel: formatDistance(meters, unit),
    }
  }, [effectiveOrigin, dest, unit, t])

  // Hazard awareness (plan-21 Phase 4): test whichever route is actually shown —
  // the road-following polyline when available, otherwise the straight-line
  // segment — against the active hazards. Computed during render (a memo, not an
  // effect) so it never causes a re-render loop off the fresh hazard arrays.
  const hazardCross = useMemo(() => {
    if (!effectiveOrigin || !dest || dest.lat == null) return { crossed: [], avoids: false }
    const active = (view.hazards || []).filter((h) => h.active)
    if (!active.length) return { crossed: [], avoids: false }
    const roadLine = view.routePolyline
    const usingRoad = Array.isArray(roadLine) && roadLine.length > 1
    const line = usingRoad
      ? roadLine
      : [[effectiveOrigin.lat, effectiveOrigin.lon], [dest.lat, dest.lon]]
    const crossed = routeCrossesHazards(line, active)
    return { crossed, avoids: usingRoad && crossed.length === 0 }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveOrigin, dest, view.hazards, view.routePolyline])

  // Unique, translated type labels of the hazards the route crosses.
  const crossedLabels = [...new Set(hazardCross.crossed.map((h) => h.typeLabel || h.type))]

  // Try to upgrade the straight-line route to a road-following one whenever both
  // endpoints are known. Looks for a locally-cached pack that covers both points
  // and runs A* in the worker; if none is cached but the server has one for the
  // area, surfaces a download affordance. Always non-blocking — the straight-line
  // result above is shown regardless.
  useEffect(() => {
    let cancelled = false
    setDownloadablePack(null)
    if (!effectiveOrigin || !dest || dest.lat == null) {
      setRoadRoute(null)
      actions.setRoutePolyline(null)
      return
    }
    const o = { lat: effectiveOrigin.lat, lon: effectiveOrigin.lon }
    const d = { lat: dest.lat, lon: dest.lon }
    ;(async () => {
      const graph = await findCoveringLocalPack(o, d)
      if (cancelled) return
      if (graph) {
        setRoadRoute('computing')
        const res = await computeRoadRoute(graph, o, d, activeHazardsRef.current)
        if (cancelled) return
        if (res && res.ok && res.polyline && res.polyline.length > 1) {
          setRoadRoute({ meters: res.meters, nodes: res.nodes })
          actions.setRoutePolyline(res.polyline)
        } else {
          setRoadRoute(null)
          actions.setRoutePolyline(null)
        }
        return
      }
      // No local pack: clear any stale road route, then see if the server has one.
      setRoadRoute(null)
      actions.setRoutePolyline(null)
      if (!isOnline()) return
      const index = await fetchPackIndex(API_BASE)
      if (cancelled) return
      const match = index.find((p) => packCovers({ bbox: p.bbox }, o) && packCovers({ bbox: p.bbox }, d))
      if (match) setDownloadablePack(match)
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveOrigin, dest])

  const downloadPack = async () => {
    if (!downloadablePack || downloading) return
    setDownloading(true)
    const graph = await fetchAndCachePack(API_BASE, downloadablePack.id)
    setDownloading(false)
    if (!graph || !effectiveOrigin || !dest) return
    setDownloadablePack(null)
    const o = { lat: effectiveOrigin.lat, lon: effectiveOrigin.lon }
    const d = { lat: dest.lat, lon: dest.lon }
    setRoadRoute('computing')
    const res = await computeRoadRoute(graph, o, d, activeHazardsRef.current)
    if (res && res.ok && res.polyline && res.polyline.length > 1) {
      setRoadRoute({ meters: res.meters, nodes: res.nodes })
      actions.setRoutePolyline(res.polyline)
    } else {
      setRoadRoute(null)
    }
  }

  const onComputeFromMe = async () => {
    const o = await resolveOrigin()
    if (o && dest) persistRoute(o, dest)
  }

  const persistRoute = async (o, d) => {
    const rec = {
      from: o, to: { lat: d.lat, lon: d.lon, name: d.name || '' },
      name: d.name || '', at: new Date().toISOString(),
    }
    cacheRoute(rec)
    setHistory(await addRouteToHistory(rec))
  }

  const chooseDest = (d) => {
    setDest(d)
    setDestText('')
    if (effectiveOrigin) persistRoute(effectiveOrigin, d)
  }

  const applyTypedDest = () => {
    const p = parseCoords(destText)
    if (p) chooseDest({ ...p, name: t('directions.typedDest') })
  }

  const navigate = () => {
    if (dest && dest.lat != null) {
      openTurnByTurn(dest.lat, dest.lon, dest.name || '')
      if (effectiveOrigin) persistRoute(effectiveOrigin, dest)
    }
  }

  const card = css('background:#fff;border:1px solid #ECE8E2;border-radius:14px;padding:14px;')
  const label = css("font:600 11px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;text-transform:uppercase;margin-bottom:8px;")
  const input = css("width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #E2DED8;border-radius:11px;font:500 13px 'IBM Plex Sans';color:#1A1714;outline:none;")
  const chip = (on) => ({ ...css("padding:8px 12px;border-radius:20px;font:600 12px 'IBM Plex Sans';cursor:pointer;border:1px solid;"), background: on ? '#1A1714' : '#fff', color: on ? '#fff' : '#5A534C', borderColor: on ? '#1A1714' : '#E2DED8' })

  return (
    <div style={css('padding:16px 16px 32px;display:flex;flex-direction:column;gap:14px;')}>
      <div>
        <h1 style={css("font:600 19px 'IBM Plex Sans';color:#1A1714;margin:0;")}>{t('directions.title')}</h1>
        <p style={css("font:400 12.5px 'IBM Plex Sans';color:#6E685E;margin:4px 0 0;")}>{t('directions.subtitle')}</p>
      </div>

      {/* Origin */}
      <div style={card}>
        <div style={label}>{t('directions.from')}</div>
        <div style={css('display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;')}>
          <button className="egi-tap" style={chip(originMode === 'me')} onClick={() => setOriginMode('me')}>{t('directions.myLocation')}</button>
          <button className="egi-tap" style={chip(originMode === 'coords')} onClick={() => setOriginMode('coords')}>{t('directions.typedOrigin')}</button>
        </div>
        {originMode === 'me' ? (
          <button className="egi-tap" onClick={onComputeFromMe} disabled={locating}
            style={{ ...css("padding:11px 14px;border:1px solid #E2DED8;border-radius:11px;background:#F4EFE7;color:#1A1714;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"), opacity: locating ? 0.6 : 1 }}>
            {locating ? t('directions.locating') : (origin ? t('directions.locationSet') : t('directions.useMyLocation'))}
          </button>
        ) : (
          <input style={input} value={originText} onChange={(e) => setOriginText(e.target.value)} placeholder={t('directions.coordsPlaceholder')} inputMode="decimal" />
        )}
        {locError && <div aria-live="polite" style={css("font:500 11.5px 'IBM Plex Mono';color:#B7242A;margin-top:8px;")}>{locError}</div>}
      </div>

      {/* Destination */}
      <div style={card}>
        <div style={label}>{t('directions.to')}</div>
        {dest && (
          <div style={css('display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:9px 11px;background:#F1F8F3;border:1px solid #CDE9D6;border-radius:11px;')}>
            <span style={css("flex:1;font:600 13px 'IBM Plex Sans';color:#15683A;")}>{dest.name || t('directions.typedDest')}</span>
            <button className="egi-tap" onClick={() => setDest(null)} style={css("border:none;background:transparent;cursor:pointer;font:600 11px 'IBM Plex Mono';color:#6E685E;")}>{t('common.change')}</button>
          </div>
        )}
        <div style={css('display:flex;gap:8px;margin-bottom:10px;')}>
          <input style={input} value={destText} onChange={(e) => setDestText(e.target.value)} placeholder={t('directions.coordsPlaceholder')} inputMode="decimal" />
          <button className="egi-tap" onClick={applyTypedDest} style={css("padding:0 14px;border:1px solid #E2DED8;border-radius:11px;background:#fff;color:#1A1714;font:600 12.5px 'IBM Plex Sans';cursor:pointer;flex:none;")}>{t('directions.set')}</button>
        </div>
        {(candidates.shelters.length > 0 || candidates.people.length > 0) && (
          <div style={css('display:flex;flex-direction:column;gap:6px;max-height:200px;overflow-y:auto;')}>
            {candidates.shelters.map((d) => (
              <DestRow key={'s-' + d.id} d={d} tag={t('directions.tagShelter')} onClick={() => chooseDest(d)} />
            ))}
            {candidates.people.map((d) => (
              <DestRow key={'p-' + d.id} d={d} tag={t('directions.tagPerson')} onClick={() => chooseDest(d)} />
            ))}
          </div>
        )}
      </div>

      {/* Result */}
      {route ? (
        <div style={card}>
          <div style={css('display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;')}>
            <span style={css("font:600 28px 'IBM Plex Sans';color:#1A1714;")}>{route.distLabel}</span>
            <span style={css("font:500 13px 'IBM Plex Sans';color:#6E685E;")}>{t('directions.walkEst', { min: route.minutes })}</span>
            <button className="egi-tap" onClick={() => setUnit(unit === 'km' ? 'mi' : 'km')}
              style={css("margin-left:auto;border:1px solid #E2DED8;background:#fff;border-radius:8px;padding:4px 8px;font:600 10px 'IBM Plex Mono';color:#6E685E;cursor:pointer;")}>
              {unit === 'km' ? 'mi' : 'km'}
            </button>
          </div>
          <div style={css('display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid #F0ECE6;')}>
            <span aria-hidden="true" style={{ ...css('display:inline-block;width:22px;height:22px;'), transform: `rotate(${route.bearingDeg || 0}deg)` }}>
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#E5343B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5" /><path d="M5 12l7-7 7 7" /></svg>
            </span>
            <span style={css("font:500 13px 'IBM Plex Sans';color:#1A1714;")}>
              {t('directions.step', { dir: route.cardinal, dist: route.distLabel, name: (dest && dest.name) || t('directions.destination') })}
            </span>
          </div>
          <button className="egi-tap" onClick={navigate}
            style={css("margin-top:12px;width:100%;padding:13px;background:#E5343B;border:none;border-radius:12px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>
            {t('directions.openInMaps')}
          </button>
          <p style={css("font:400 11px 'IBM Plex Sans';color:#9A938A;margin:8px 0 0;")}>{t('directions.straightLineNote')}</p>

          {/* Hazard crossing warning (plan-21 Phase 4) */}
          {crossedLabels.length > 0 && (
            <div role="alert" style={css("margin-top:12px;padding:11px 12px;background:#FCEDEC;border:1px solid #F6C9C6;border-radius:11px;font:600 12.5px 'IBM Plex Sans';color:#B7242A;")}>
              {t('directions.crossesHazard', { type: crossedLabels.join(', ') })}
            </div>
          )}
          {crossedLabels.length === 0 && hazardCross.avoids && (
            <div style={css("display:flex;align-items:center;gap:6px;margin-top:10px;font:500 11.5px 'IBM Plex Sans';color:#15683A;")}>
              <span aria-hidden="true">✓</span>
              <span>{t('directions.avoidsHazards')}</span>
            </div>
          )}

          {/* Road-following route (plan-21 Phase 2) */}
          {roadRoute === 'computing' && (
            <div aria-live="polite" style={css("margin-top:10px;padding-top:10px;border-top:1px solid #F0ECE6;font:500 12px 'IBM Plex Mono';color:#1F5E96;")}>
              {t('directions.computingRoute')}
            </div>
          )}
          {roadRoute && roadRoute !== 'computing' && (
            <div style={css('display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid #F0ECE6;')}>
              <span aria-hidden="true" style={css('display:inline-block;width:10px;height:10px;border-radius:2px;background:#1F5E96;flex:none;')} />
              <span style={css("font:600 12.5px 'IBM Plex Sans';color:#1F5E96;")}>
                {t('directions.followsRoads', { dist: formatDistance(roadRoute.meters, unit), min: walkingMinutes(roadRoute.meters) })}
              </span>
            </div>
          )}
          {!roadRoute && downloadablePack && (
            <div style={css('margin-top:10px;padding-top:10px;border-top:1px solid #F0ECE6;')}>
              <p style={css("font:400 11.5px 'IBM Plex Sans';color:#6E685E;margin:0 0 8px;")}>{t('directions.noPack')}</p>
              <button className="egi-tap" onClick={downloadPack} disabled={downloading}
                style={{ ...css("width:100%;padding:11px;background:#1F5E96;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"), opacity: downloading ? 0.6 : 1 }}>
                {downloading ? t('directions.computingRoute') : t('directions.downloadPack', { region: downloadablePack.region || '' })}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div style={{ ...card, ...css("font:400 12.5px 'IBM Plex Sans';color:#6E685E;text-align:center;") }}>
          {t('directions.pickBoth')}
        </div>
      )}

      {/* Recent routes */}
      {history.length > 0 && (
        <div style={card}>
          <div style={label}>{t('directions.recent')}</div>
          <div style={css('display:flex;flex-direction:column;gap:6px;')}>
            {history.slice(0, 8).map((r, i) => (
              <button key={i} className="egi-tap" onClick={() => chooseDest({ lat: r.to.lat, lon: r.to.lon, name: r.to.name || r.name })}
                style={css("display:flex;align-items:center;gap:8px;padding:9px 10px;border:1px solid #ECE8E2;border-radius:10px;background:#fff;cursor:pointer;text-align:left;")}>
                <span style={css("flex:1;font:600 12.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{r.to.name || r.name || t('directions.typedDest')}</span>
                <span style={css("font:500 10px 'IBM Plex Mono';color:#9A938A;flex:none;")}>{String(r.at || '').slice(5, 10)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DestRow({ d, tag, onClick }) {
  return (
    <button className="egi-tap" onClick={onClick}
      style={css("display:flex;align-items:center;gap:8px;padding:9px 11px;border:1px solid #ECE8E2;border-radius:10px;background:#fff;cursor:pointer;text-align:left;")}>
      <span style={css('flex:1;min-width:0;')}>
        <span style={css("display:block;font:600 12.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{d.name}</span>
        {d.sub && <span style={css("display:block;font:400 10.5px 'IBM Plex Sans';color:#9A938A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{d.sub}</span>}
      </span>
      <span style={css("flex:none;font:600 9px 'IBM Plex Mono';color:#8B8278;background:#F1EEE9;border-radius:6px;padding:3px 6px;")}>{tag}</span>
    </button>
  )
}

import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import LocationSuggestions from './LocationSuggestions.jsx'

// SAR operations list (search-and-rescue). Each card taps through to the detail
// board and shows a status chip + sector/volunteer/person counts (active first).
// A create flow (name + optional zone + auto-grid) opens inline.
export default function OperationsScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()
  const [creating, setCreating] = useState(false)

  // Refresh from the server on mount (offline → keep the last list). Also ask for
  // a position fix so proximity suggestions can surface (opt-in + quiet-hours
  // aware inside the action).
  useEffect(() => {
    actions.fetchOperations()
    actions.requestHelpLocation()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={css('padding:16px 18px 24px;')}>
      <div style={css('display:flex;align-items:flex-start;gap:10px;')}>
        <div style={css('flex:1;min-width:0;')}>
          <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('operations.title')}</h1>
          <p style={css("margin:0 0 14px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{t('operations.subtitle')}</p>
        </div>
        {v.operator && !creating && (
          <button onClick={() => setCreating(true)} className="egi-tap" style={css("flex:none;padding:9px 13px;background:#E5343B;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.create')}</button>
        )}
      </div>

      {creating && <CreateForm view={v} actions={actions} onDone={() => setCreating(false)} />}

      <LocationSuggestions view={v} actions={actions} />

      <div style={css('display:flex;flex-direction:column;gap:11px;')}>
        {v.operations.map((o) => (
          <button key={o.id} onClick={o.open} className="egi-tap" style={css('text-align:left;width:100%;padding:14px;background:#fff;border:1px solid #EDE9E3;border-radius:15px;cursor:pointer;')}>
            <div style={css('display:flex;align-items:center;gap:10px;')}>
              <div style={css('flex:1;min-width:0;')}>
                <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{o.name}</div>
                {o.description && <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{o.description}</div>}
              </div>
              <span style={{ ...css("padding:3px 9px;border-radius:7px;font:600 10.5px 'IBM Plex Sans';flex:none;"), background: o.statusBg, color: o.statusColor }}>{o.statusLabel}</span>
            </div>
            <div style={css('display:flex;gap:7px;margin-top:11px;flex-wrap:wrap;')}>
              <Stat label={t('operations.sectors')} value={o.sector_count} />
              <Stat label={t('operations.volunteers')} value={o.volunteer_count} />
              <Stat label={t('operations.persons')} value={o.person_count} />
            </div>
          </button>
        ))}
        {v.operations.length === 0 && !creating && (
          <div style={css("padding:24px 0;text-align:center;font:400 13px 'IBM Plex Sans';color:#A9A299;")}>{t('operations.empty')}</div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <span style={css("display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:8px;background:#F2EFEA;font:600 11px 'IBM Plex Sans';color:#5A534C;")}>
      <strong style={css("font:700 12px 'IBM Plex Mono';color:#1A1714;")}>{value ?? 0}</strong>{label}
    </span>
  )
}

// Inline create flow: name (required) + optional zone lat/lon/radius + auto-grid
// sector count. Kept simple per the contract; persons are linked elsewhere.
function CreateForm({ actions, onDone }) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [radius, setRadius] = useState('')
  const [grid, setGrid] = useState('')

  const inputStyle = css("width:100%;padding:11px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13.5px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")
  const labelStyle = css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;display:block;margin-bottom:5px;")

  const submit = () => {
    const nm = name.trim()
    if (!nm) return
    const payload = { name: nm }
    if (lat.trim() && lon.trim()) {
      payload.zone_lat = parseFloat(lat)
      payload.zone_lon = parseFloat(lon)
      if (radius.trim()) payload.zone_radius_m = parseInt(radius, 10)
    }
    const g = parseInt(grid, 10)
    if (g > 0) payload.auto_grid = g
    actions.createOperation(payload)
    onDone()
  }

  return (
    <div style={css('margin-bottom:16px;padding:15px;border:1px solid #EDE9E3;border-radius:15px;background:#fff;display:flex;flex-direction:column;gap:12px;')}>
      <div style={css("font:600 13.5px 'IBM Plex Sans';color:#1A1714;")}>{t('operations.create')}</div>
      <div>
        <label style={labelStyle}>{t('operations.fieldName')}</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('operations.fieldNamePh')} style={inputStyle} />
      </div>
      <div style={css('display:flex;gap:10px;')}>
        <div style={css('flex:1;')}>
          <label style={labelStyle}>{t('operations.zoneLat')}</label>
          <input value={lat} onChange={(e) => setLat(e.target.value)} placeholder="10.60" inputMode="decimal" style={inputStyle} />
        </div>
        <div style={css('flex:1;')}>
          <label style={labelStyle}>{t('operations.zoneLon')}</label>
          <input value={lon} onChange={(e) => setLon(e.target.value)} placeholder="-66.93" inputMode="decimal" style={inputStyle} />
        </div>
      </div>
      <div style={css('display:flex;gap:10px;')}>
        <div style={css('flex:1;')}>
          <label style={labelStyle}>{t('operations.zoneRadius')}</label>
          <input value={radius} onChange={(e) => setRadius(e.target.value)} placeholder="500" inputMode="numeric" style={inputStyle} />
        </div>
        <div style={css('flex:1;')}>
          <label style={labelStyle}>{t('operations.autoGrid')}</label>
          <input value={grid} onChange={(e) => setGrid(e.target.value)} placeholder="4" inputMode="numeric" style={inputStyle} />
        </div>
      </div>
      <div style={css('display:flex;gap:10px;')}>
        <button onClick={onDone} className="egi-tap" style={css("flex:none;padding:11px 16px;background:#fff;border:1px solid #E2DED8;border-radius:11px;color:#1A1714;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('common.cancel')}</button>
        <button onClick={submit} className="egi-tap" style={css("flex:1;padding:11px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.createConfirm')}</button>
      </div>
    </div>
  )
}

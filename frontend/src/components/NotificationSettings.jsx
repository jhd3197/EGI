import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Notification-specific settings: the global "near me" radius, an optional
// quiet-hours window, and a batch-digest toggle for high-volume users (plan-24
// Phase 2). Reads view.settings; writes via actions.setSetting(key, value).
const RADIUS_STEPS = [0, 1000, 5000, 10000, 25000, 50000]

function radiusLabel(meters, t) {
  if (!meters) return t('settings.radius.any')
  if (meters >= 1000) return t('settings.radius.km', { n: Math.round(meters / 1000) })
  return t('settings.radius.m', { n: meters })
}

export default function NotificationSettings({ view, actions }) {
  const s = view.settings || {}
  const { t } = useI18n()
  const radius = s.radius || 0
  const radiusIdx = Math.max(0, RADIUS_STEPS.indexOf(radius))
  const idx = radiusIdx === -1 ? 0 : radiusIdx

  return (
    <div style={css('display:flex;flex-direction:column;gap:18px;')}>
      {/* Near-me radius */}
      <div>
        <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:10px;')}>
          <label htmlFor="egi-radius" style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>
            {t('settings.radius.title')}
          </label>
          <span style={css("font:600 12px 'IBM Plex Mono';color:#C2272D;")}>
            {radiusLabel(radius, t)}
          </span>
        </div>
        <p style={css("margin:3px 0 8px;font:400 11.5px 'IBM Plex Sans';color:#8A837A;")}>
          {t('settings.radius.desc')}
        </p>
        <input
          id="egi-radius"
          type="range"
          min="0"
          max={RADIUS_STEPS.length - 1}
          step="1"
          value={idx}
          onChange={(e) => actions.setSetting('radius', RADIUS_STEPS[parseInt(e.target.value, 10)])}
          style={css('width:100%;accent-color:#E5343B;cursor:pointer;')}
        />
      </div>

      {/* Quiet hours */}
      <div>
        <div style={css('display:flex;align-items:center;justify-content:space-between;gap:10px;')}>
          <label style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>
            {t('settings.quiet.title')}
          </label>
          <Toggle
            on={s.quietStart != null}
            onClick={() =>
              s.quietStart != null
                ? (actions.setSetting('quietStart', null), actions.setSetting('quietEnd', null))
                : (actions.setSetting('quietStart', 22), actions.setSetting('quietEnd', 7))
            }
            label={t('settings.quiet.title')}
          />
        </div>
        <p style={css("margin:3px 0 8px;font:400 11.5px 'IBM Plex Sans';color:#8A837A;")}>
          {t('settings.quiet.desc')}
        </p>
        {s.quietStart != null && (
          <div style={css('display:flex;align-items:center;gap:10px;')}>
            <HourSelect value={s.quietStart} onChange={(v) => actions.setSetting('quietStart', v)} label={t('settings.quiet.from')} t={t} />
            <span style={css("font:500 11px 'IBM Plex Mono';color:#8A837A;")}>→</span>
            <HourSelect value={s.quietEnd} onChange={(v) => actions.setSetting('quietEnd', v)} label={t('settings.quiet.to')} t={t} />
          </div>
        )}
      </div>

      {/* Batch / digest */}
      <div style={css('display:flex;align-items:center;justify-content:space-between;gap:10px;')}>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('settings.batch.title')}</div>
          <p style={css("margin:3px 0 0;font:400 11.5px 'IBM Plex Sans';color:#8A837A;")}>{t('settings.batch.desc')}</p>
        </div>
        <Toggle on={!!s.batch} onClick={() => actions.setSetting('batch', !s.batch)} label={t('settings.batch.title')} />
      </div>
    </div>
  )
}

function HourSelect({ value, onChange, label, t }) {
  return (
    <label style={css('display:flex;flex-direction:column;gap:3px;')}>
      <span style={css("font:500 9.5px 'IBM Plex Mono';color:#8A837A;letter-spacing:.04em;")}>{label}</span>
      <select
        value={value == null ? 0 : value}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        style={css("border:1px solid #E2DED8;background:#fff;border-radius:10px;color:#1A1714;font:600 12px 'IBM Plex Mono';padding:7px 9px;cursor:pointer;outline:none;")}
      >
        {Array.from({ length: 24 }, (_, h) => (
          <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>
        ))}
      </select>
    </label>
  )
}

// Shared pill toggle. Exported so SettingsScreen reuses the exact same control.
export function Toggle({ on, onClick, label }) {
  return (
    <button
      onClick={onClick}
      className="egi-tap"
      role="switch"
      aria-checked={on}
      aria-label={label}
      style={{ ...css('width:42px;height:24px;border:none;border-radius:13px;flex:none;position:relative;cursor:pointer;transition:background .15s;'), background: on ? '#15683A' : '#CFC9C0' }}
    >
      <span style={{ ...css('position:absolute;top:2.5px;width:19px;height:19px;border-radius:50%;background:#fff;transition:left .15s;'), left: on ? '20px' : '2.5px' }} />
    </button>
  )
}

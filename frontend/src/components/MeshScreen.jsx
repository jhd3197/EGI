import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// "Red local" — surfaces the BLE mesh state and a one-tap sync-nearby action so
// users never have to open Android system UI. In a plain browser the mesh is
// unavailable and the controls explain why (everything degrades gracefully).
function Stat({ label, value }) {
  return (
    <div style={css('padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
      <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;")}>{label}</div>
      <div style={css("font:600 16px 'IBM Plex Sans';color:#2A2520;margin-top:4px;line-height:1.2;")}>{value}</div>
    </div>
  )
}

export default function MeshScreen({ view, actions }) {
  const m = view.mesh
  const { t } = useI18n()
  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('mesh.title')}</h1>
        <span style={{ ...css("padding:4px 10px;border-radius:8px;font:600 10px 'IBM Plex Mono';letter-spacing:.04em;"), background: m.pillBg, color: m.pillFg }}>{m.statusPill}</span>
      </div>
      <p style={css("margin:0 0 16px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>
        {t('mesh.intro')}
      </p>

      <div style={css("padding:13px 14px;background:#F6F3EF;border:1px solid #ECE6DD;border-radius:13px;font:500 12.5px 'IBM Plex Sans';color:#4A443D;margin-bottom:10px;")}>
        {m.statusText}
      </div>

      {m.gatewayBadge && (
        <div style={{ ...css('display:flex;align-items:center;gap:8px;padding:11px 13px;border-radius:12px;margin-bottom:10px;'), background: m.gatewayBadgeBg }}>
          <span style={{ ...css("font:600 12.5px 'IBM Plex Sans';"), color: m.gatewayBadgeFg }}>{m.gatewayBadge}</span>
        </div>
      )}

      {m.available && m.running && m.maxHops != null && (
        <p style={css("margin:0 0 16px;font:400 11.5px 'IBM Plex Sans';color:#A9A299;line-height:1.5;")}>
          {t('mesh.chainHint', { n: m.maxHops })}
        </p>
      )}

      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:16px;')}>
        <Stat label={t('mesh.statDevices')} value={m.peers} />
        <Stat label={t('mesh.statQueued')} value={m.queued} />
        <Stat label={t('mesh.statLastSync')} value={m.lastSync} />
        <Stat label={t('mesh.statThisDevice')} value={m.deviceId} />
      </div>

      {m.available && (
        <div style={css('margin-bottom:16px;')}>
          <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:8px;")}>
            {t('mesh.recentDevices')}
          </div>
          {m.recentPeers.length === 0 ? (
            <div style={css("font:400 12px 'IBM Plex Sans';color:#A9A299;")}>{t('mesh.recentNone')}</div>
          ) : (
            <div style={css('display:flex;flex-direction:column;gap:6px;')}>
              {m.recentPeers.map((p) => (
                <div key={p.id} style={css('display:flex;align-items:center;justify-content:space-between;padding:9px 12px;background:#fff;border:1px solid #EDE9E3;border-radius:11px;')}>
                  <span style={css("font:600 12px 'IBM Plex Mono';color:#2A2520;")}>{p.shortId}</span>
                  {p.seen && <span style={css("font:500 10.5px 'IBM Plex Sans';color:#A9A299;")}>{p.seen}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div style={css('display:flex;gap:9px;')}>
        <button
          onClick={actions.meshSync}
          disabled={!m.available || !m.running}
          className="egi-tap"
          style={{
            ...css("flex:1;padding:13px;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;"),
            background: (!m.available || !m.running) ? '#C9C2B8' : '#E5343B',
            boxShadow: (!m.available || !m.running) ? 'none' : '0 8px 16px -8px rgba(229,52,59,.6)',
            cursor: (!m.available || !m.running) ? 'default' : 'pointer',
          }}
        >
          {t('mesh.syncNearby')}
        </button>
        <button
          onClick={actions.toggleMesh}
          disabled={!m.available}
          className="egi-tap"
          style={{
            ...css("flex:none;padding:13px 16px;background:#fff;border:1px solid #E2DED8;border-radius:13px;font:600 13.5px 'IBM Plex Sans';cursor:pointer;"),
            color: m.available ? '#1A1714' : '#A9A299',
            cursor: m.available ? 'pointer' : 'default',
          }}
        >
          {m.toggleLabel}
        </button>
      </div>

      {/* Tipos de datos que comparto por Bluetooth (plan-24 Phase 5). Relay-only
          toggles per category; reuses the same preference the Settings screen
          edits, and mirrors the change into the native mesh bloom filter. */}
      {m.available && (
        <div style={css('margin-top:20px;')}>
          <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;margin-bottom:2px;")}>
            {t('mesh.shareTypes.title')}
          </div>
          <p style={css("margin:0 0 10px;font:400 11.5px 'IBM Plex Sans';color:#8A837A;line-height:1.4;")}>
            {t('mesh.shareTypes.hint')}
          </p>
          <div style={css('display:flex;flex-direction:column;gap:7px;')}>
            {view.settingsCategories.map((cat) => (
              <div key={cat.key} style={css('display:flex;align-items:center;gap:10px;padding:10px 12px;background:#fff;border:1px solid #EDE9E3;border-radius:11px;')}>
                <span style={css("flex:1;min-width:0;font:600 12.5px 'IBM Plex Sans';color:#1A1714;")}>{cat.label}</span>
                <RelaySwitch on={cat.relay} onClick={() => actions.setCategoryPref(cat.key, 'relay', !cat.relay)} label={cat.label} />
              </div>
            ))}
          </div>
        </div>
      )}

      {!m.available && (
        <p style={css("margin:14px 0 0;font:400 11.5px 'IBM Plex Mono';color:#A9A299;line-height:1.5;")}>
          {t('mesh.androidHint')}
        </p>
      )}
    </div>
  )
}

function RelaySwitch({ on, onClick, label }) {
  return (
    <button onClick={onClick} className="egi-tap" role="switch" aria-checked={on} aria-label={label}
      style={{ ...css('width:42px;height:24px;border:none;border-radius:13px;flex:none;position:relative;cursor:pointer;transition:background .15s;'), background: on ? '#15683A' : '#CFC9C0' }}>
      <span style={{ ...css('position:absolute;top:2.5px;width:19px;height:19px;border-radius:50%;background:#fff;transition:left .15s;'), left: on ? '20px' : '2.5px' }} />
    </button>
  )
}

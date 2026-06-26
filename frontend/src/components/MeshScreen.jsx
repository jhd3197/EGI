import { css } from '../lib/css.js'

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
  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>Red local</h1>
        <span style={{ ...css("padding:4px 10px;border-radius:8px;font:600 10px 'IBM Plex Mono';letter-spacing:.04em;"), background: m.pillBg, color: m.pillFg }}>{m.statusPill}</span>
      </div>
      <p style={css("margin:0 0 16px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>
        Comparte registros con teléfonos cercanos por Bluetooth, sin internet. Los datos viajan cifrados entre dispositivos.
      </p>

      <div style={css("padding:13px 14px;background:#F6F3EF;border:1px solid #ECE6DD;border-radius:13px;font:500 12.5px 'IBM Plex Sans';color:#4A443D;margin-bottom:16px;")}>
        {m.statusText}
      </div>

      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:16px;')}>
        <Stat label="DISPOSITIVOS" value={m.peers} />
        <Stat label="EN COLA" value={m.queued} />
        <Stat label="ÚLTIMA SINCRONIZACIÓN" value={m.lastSync} />
        <Stat label="ESTE DISPOSITIVO" value={m.deviceId} />
      </div>

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
          Sincronizar con dispositivos cercanos
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

      {!m.available && (
        <p style={css("margin:14px 0 0;font:400 11.5px 'IBM Plex Mono';color:#A9A299;line-height:1.5;")}>
          Abre Egi en la app de Android para usar la malla por Bluetooth.
        </p>
      )}
    </div>
  )
}

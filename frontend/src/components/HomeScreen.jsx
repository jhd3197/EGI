import { css } from '../lib/css.js'

export default function HomeScreen({ view, actions }) {
  const v = view
  return (
    <div style={css('padding:16px 18px 28px;')}>
      <div style={css('display:flex;align-items:center;gap:7px;margin:4px 0 9px;')}>
        <span style={css('width:7px;height:7px;border-radius:50%;background:#C2272D;display:inline-block;animation:egiPulse 1.6s ease-in-out infinite;')} />
        <span style={css("font:500 9.5px 'IBM Plex Mono';color:#B7242A;letter-spacing:.12em;")}>EMERGENCIA ACTIVA</span>
      </div>
      <h1 style={css("margin:0 0 7px;font:700 25px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.02em;line-height:1.15;")}>{v.disasterName}</h1>
      <div style={css("font:400 11.5px 'IBM Plex Mono';color:#8B8278;")}>{v.disasterMeta}</div>
      <div style={css('height:1px;background:#E7E1D8;margin:17px 0 15px;')} />
      <p style={css("margin:0 0 12px;font:600 13px 'IBM Plex Sans';color:#4A443D;")}>¿A quién buscas? · Who are you looking for?</p>

      <button onClick={() => actions.setScreen('search')} className="egi-tap" style={css('width:100%;display:flex;align-items:center;gap:10px;padding:13px 14px;background:#fff;border:1px solid #E6E2DC;border-radius:14px;cursor:pointer;text-align:left;box-shadow:0 1px 2px rgba(40,30,20,.04);')}>
        <span style={css('width:18px;height:18px;border:2px solid #B3ABA1;border-radius:50%;position:relative;flex:none;')}>
          <span style={css('position:absolute;width:7px;height:2px;background:#B3ABA1;border-radius:1px;transform:rotate(45deg);right:-5px;bottom:-1px;')} />
        </span>
        <span style={css("font:400 14px 'IBM Plex Sans';color:#9A938A;")}>Buscar por nombre o lugar…</span>
      </button>

      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:14px;')}>
        <button onClick={() => actions.openReport('missing')} className="egi-tap" style={css("display:flex;flex-direction:column;gap:9px;padding:15px 14px;background:#E5343B;border:none;border-radius:13px;cursor:pointer;text-align:left;color:#fff;box-shadow:0 10px 22px -14px rgba(206,53,46,.5);")}>
          <span style={css('width:30px;height:30px;border-radius:9px;background:rgba(255,255,255,.18);position:relative;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:14px;height:3px;background:#fff;border-radius:2px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:3px;height:14px;background:#fff;border-radius:2px;')} />
          </span>
          <span style={css("font:600 14px 'IBM Plex Sans';line-height:1.15;")}>Reportar desaparecido</span>
          <span style={css("font:500 10px 'IBM Plex Mono';color:rgba(255,255,255,.78);")}>Report missing</span>
        </button>
        <button onClick={() => actions.openReport('safe')} className="egi-tap" style={css("display:flex;flex-direction:column;gap:9px;padding:15px 14px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;cursor:pointer;text-align:left;color:#1A1714;")}>
          <span style={css('width:30px;height:30px;border-radius:9px;background:#E3F2E7;position:relative;')}>
            <span style={css('position:absolute;left:9px;top:15px;width:6px;height:2.6px;background:#1B7A45;border-radius:1px;transform:rotate(45deg);transform-origin:left;')} />
            <span style={css('position:absolute;left:13px;top:18px;width:11px;height:2.6px;background:#1B7A45;border-radius:1px;transform:rotate(-50deg);transform-origin:left;')} />
          </span>
          <span style={css("font:600 14px 'IBM Plex Sans';line-height:1.15;")}>Registrar a salvo</span>
          <span style={css("font:500 10px 'IBM Plex Mono';color:#9A938A;")}>Register as safe</span>
        </button>
      </div>

      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin:24px 0 10px;')}>
        <h2 style={css("margin:0;font:600 15px 'IBM Plex Sans';color:#1A1714;")}>Actividad reciente</h2>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#A9A299;")}>Recent activity</span>
      </div>
      <div style={css('display:flex;flex-direction:column;gap:9px;')}>
        {v.activity.map((a, idx) => (
          <div key={idx} style={css('display:flex;gap:11px;align-items:flex-start;padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
            <span style={{ ...css('width:9px;height:9px;border-radius:50%;margin-top:3px;flex:none;'), background: a.dot }} />
            <div style={css('flex:1;min-width:0;')}>
              <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;line-height:1.3;")}>{a.t}</div>
              <div style={css("font:400 11px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{a.s}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

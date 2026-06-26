import { css } from '../lib/css.js'
import Logo from './Logo.jsx'
import AddDisasterModal from './AddDisasterModal.jsx'

export default function DisasterPicker({ view, actions }) {
  const v = view
  return (
    <div style={css("height:100vh;width:100%;overflow-y:auto;background:#F4EFE7;font-family:'IBM Plex Sans',system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;")}>
      <div style={css('width:100%;max-width:560px;padding:34px 22px 60px;')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:30px;')}>
          <div style={css('display:flex;align-items:center;gap:9px;')}>
            <Logo size={28} radius={8} bar={15} thick={3.6} />
            <span style={css("font:700 19px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>EGI</span>
          </div>
          <button onClick={actions.signOut} className="egi-tap" style={css("border:none;background:transparent;cursor:pointer;font:600 11px 'IBM Plex Mono';color:#A39B90;")}>Salir</button>
        </div>
        <div style={css("font:500 10px 'IBM Plex Mono';color:#A39B90;letter-spacing:.14em;margin-bottom:8px;")}>SELECCIONA LA EMERGENCIA</div>
        <h1 style={css("margin:0 0 7px;font:700 25px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.02em;")}>¿En qué evento trabajas?</h1>
        <p style={css("margin:0 0 22px;font:400 13.5px 'IBM Plex Sans';color:#6A645C;line-height:1.5;")}>Lo que reportes o busques se asociará a esta emergencia. Puedes cambiar de evento cuando quieras.</p>

        <div style={css('display:flex;flex-direction:column;gap:11px;')}>
          {v.disasters.map((d) => (
            <button key={d.id} onClick={d.open} className="egi-tap" style={css('display:flex;align-items:center;gap:14px;padding:15px;background:#fff;border:1px solid #E7E1D8;border-radius:14px;cursor:pointer;text-align:left;')}>
              <span style={css("width:48px;height:48px;border-radius:12px;flex:none;background:#F4EFE7;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 11px 'IBM Plex Mono';color:#8B8278;letter-spacing:.02em;")}>{d.tag}</span>
              <div style={css('flex:1;min-width:0;')}>
                <div style={css("font:600 15.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{d.name}</div>
                <div style={css("font:400 12px 'IBM Plex Sans';color:#8B8278;margin-top:3px;")}>{d.region}</div>
                <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A39B90;margin-top:8px;")}>{d.affected} registradas · {d.shelters} refugios · desde {d.date}</div>
              </div>
              <span style={css("padding:4px 10px;border-radius:7px;font:600 10px 'IBM Plex Sans';background:#FDE7E7;color:#C2272D;flex:none;")}>{d.status}</span>
            </button>
          ))}
        </div>

        <button onClick={actions.openAdd} className="egi-tap" style={css("margin-top:13px;width:100%;display:flex;align-items:center;justify-content:center;gap:9px;padding:14px;background:transparent;border:1px dashed #CFC8BD;border-radius:14px;cursor:pointer;font:600 13.5px 'IBM Plex Sans';color:#6A645C;")}>
          <span style={css('width:15px;height:15px;position:relative;flex:none;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:13px;height:2px;background:#8B8278;border-radius:1px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:2px;height:13px;background:#8B8278;border-radius:1px;')} />
          </span>
          Registrar nueva emergencia
        </button>
      </div>

      {v.addOpen && <AddDisasterModal view={v} actions={actions} />}
    </div>
  )
}

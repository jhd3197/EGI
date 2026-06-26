import { css } from '../lib/css.js'

export default function AddDisasterModal({ view, actions }) {
  const v = view
  return (
    <div style={css('position:fixed;inset:0;z-index:60;background:rgba(20,14,8,.42);display:flex;align-items:center;justify-content:center;padding:24px;')}>
      <div style={css('width:100%;max-width:420px;background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 30px 70px -20px rgba(20,14,8,.5);')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid #EDE9E3;')}>
          <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;")}>Nueva emergencia</div>
          <button onClick={actions.closeAdd} className="egi-tap" style={css('width:30px;height:30px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;position:relative;flex:none;')}>
            <span style={css('position:absolute;left:50%;top:50%;width:12px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(45deg);')} />
            <span style={css('position:absolute;left:50%;top:50%;width:12px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(-45deg);')} />
          </button>
        </div>
        <div style={css('padding:16px 18px;display:flex;flex-direction:column;gap:13px;')}>
          <div>
            <label style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")}>Nombre del evento</label>
            <input value={v.draftName} onChange={(e) => actions.setDraftField('draftName', e.target.value)} placeholder="Ej. Inundaciones Las Tejerías" style={css("width:100%;margin-top:6px;padding:12px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 14px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")} />
          </div>
          <div>
            <label style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")}>Región / país</label>
            <input value={v.draftRegion} onChange={(e) => actions.setDraftField('draftRegion', e.target.value)} placeholder="Ej. Aragua · Venezuela" style={css("width:100%;margin-top:6px;padding:12px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 14px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")} />
          </div>
          <div>
            <label style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")}>Tipo de evento</label>
            <div style={css('display:flex;gap:8px;margin-top:7px;')}>
              {v.addTypeChips.map((c) => (
                <button key={c.key} onClick={c.onClick} className="egi-tap" style={{ ...css("flex:1;padding:10px;border-radius:10px;font:600 12px 'IBM Plex Sans';cursor:pointer;"), background: c.chipBg, color: c.chipFg, border: `1px solid ${c.chipBorder}` }}>{c.label}</button>
              ))}
            </div>
          </div>
        </div>
        <div style={css('padding:6px 18px 18px;')}>
          <button onClick={actions.addDisaster} className="egi-tap" style={css("width:100%;padding:14px;background:#E5343B;border:none;border-radius:12px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>Crear y entrar</button>
        </div>
      </div>
    </div>
  )
}

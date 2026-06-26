import { css } from '../lib/css.js'

// Mobile-only top bar + the disaster strip below it.
export default function TopBar({ view, actions }) {
  const v = view
  const c = v.conn
  return (
    <>
      <div style={{ ...css('align-items:center;justify-content:space-between;padding:14px 18px 10px;flex:none;background:#fff;'), display: v.topbarDisplay }}>
        <div style={css('display:flex;align-items:center;gap:9px;')}>
          <div style={css('width:26px;height:26px;border-radius:8px;background:#E5343B;position:relative;flex:none;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:14px;height:3.4px;background:#fff;border-radius:1px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:3.4px;height:14px;background:#fff;border-radius:1px;')} />
          </div>
          <span style={css("font:700 18px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>EGI</span>
        </div>
        <button onClick={actions.toggleOnline} className="egi-tap" style={{ ...css('display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 11px;border-radius:20px;'), border: `1px solid ${c.border}`, background: c.bg }}>
          <span style={{ ...css('width:7px;height:7px;border-radius:50%;display:inline-block;'), background: c.dot }} />
          <span style={{ ...css("font:600 10px 'IBM Plex Mono';letter-spacing:.03em;"), color: c.fg }}>{c.pill}</span>
        </button>
      </div>

      <button onClick={actions.changeDisaster} className="egi-tap" style={{ ...css('align-items:center;gap:10px;width:100%;padding:9px 18px;background:#F4EFE7;border:none;border-top:1px solid #ECE8E2;border-bottom:1px solid #ECE8E2;cursor:pointer;text-align:left;'), display: v.topbarDisplay }}>
        <span style={css("width:28px;height:28px;border-radius:8px;flex:none;background:#fff;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 8.5px 'IBM Plex Mono';color:#8B8278;")}>{v.selDisaster.tag}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:500 8px 'IBM Plex Mono';color:#A39B90;letter-spacing:.08em;")}>EMERGENCIA ACTIVA</div>
          <div style={css("font:600 12.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.disasterName}</div>
        </div>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#C2272D;flex:none;")}>Cambiar</span>
      </button>
    </>
  )
}

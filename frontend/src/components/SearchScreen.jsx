import { css } from '../lib/css.js'

export default function SearchScreen({ view, actions }) {
  const v = view
  return (
    <div style={css('padding:16px 18px 24px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>Buscar</h1>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{v.visibleCount} personas</span>
      </div>
      <div style={css('display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;margin-bottom:13px;')}>
        <span style={css('width:16px;height:16px;border:2px solid #B3ABA1;border-radius:50%;position:relative;flex:none;')}>
          <span style={css('position:absolute;width:6px;height:2px;background:#B3ABA1;border-radius:1px;transform:rotate(45deg);right:-4px;bottom:-1px;')} />
        </span>
        <input
          value={v.search}
          onChange={(e) => actions.setSearch(e.target.value)}
          placeholder="Nombre, cédula, lugar o caso…"
          style={css("flex:1;min-width:0;border:none;outline:none;background:transparent;font:400 13px 'IBM Plex Sans';color:#1A1714;")}
        />
      </div>
      <div className="egi-scroll" style={css('display:flex;gap:8px;overflow-x:auto;padding-bottom:13px;margin:0 -18px;padding-left:18px;padding-right:18px;')}>
        {v.chips.map((c) => (
          <button key={c.key} onClick={c.onClick} className="egi-tap" style={{ ...css("flex:none;padding:7px 14px;border-radius:20px;font:500 12.5px 'IBM Plex Sans';cursor:pointer;"), background: c.chipBg, color: c.chipFg, border: `1px solid ${c.chipBorder}` }}>{c.label}</button>
        ))}
      </div>
      <div style={css('display:flex;flex-direction:column;gap:10px;')}>
        {v.visiblePeople.map((p) => (
          <button key={p.id} onClick={p.open} className="egi-tap" style={css('display:flex;gap:13px;align-items:center;padding:11px;background:#fff;border:1px solid #EDE9E3;border-radius:15px;cursor:pointer;text-align:left;')}>
            <span style={css("width:54px;height:54px;border-radius:12px;flex:none;background-image:repeating-linear-gradient(45deg,#EFEDE9,#EFEDE9 6px,#E4E1DB 6px,#E4E1DB 12px);display:flex;align-items:center;justify-content:center;font:600 16px 'IBM Plex Mono';color:#A89F94;")}>{p.initials}</span>
            <div style={css('flex:1;min-width:0;')}>
              <div style={css('display:flex;align-items:center;gap:7px;')}>
                <span style={css("font:600 14.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{p.name}</span>
              </div>
              <div style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{p.meta}</div>
              <div style={css('display:flex;align-items:center;gap:6px;margin-top:7px;')}>
                <span style={{ ...css("padding:3px 8px;border-radius:6px;font:600 10px 'IBM Plex Sans';"), background: p.badgeBg, color: p.badgeFg }}>{p.statusLabel}</span>
                <span style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{p.place}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

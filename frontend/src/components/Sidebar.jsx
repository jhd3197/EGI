import { css } from '../lib/css.js'
import { HomeIcon, SearchIcon, SheltersIcon, MineIcon, MeshIcon } from './Icons.jsx'
import Wordmark from './Wordmark.jsx'

function NavButton({ onClick, nav, icon, label }) {
  return (
    <button onClick={onClick} className="egi-tap" style={{ ...css('display:flex;align-items:center;gap:12px;padding:11px 12px;border:none;border-radius:11px;cursor:pointer;text-align:left;'), background: nav.bg, color: nav.color }}>
      {icon}
      <span style={css("font:600 13.5px 'IBM Plex Sans';")}>{label}</span>
    </button>
  )
}

export default function Sidebar({ view, actions }) {
  const v = view
  const c = v.conn
  return (
    <div style={{ ...css('flex-direction:column;width:256px;flex:none;height:100%;background:#fff;border-right:1px solid #ECE8E2;padding:22px 16px;gap:5px;'), display: v.sidebarDisplay }}>
      <div style={css('display:flex;align-items:center;gap:10px;padding:0 8px 4px;')}>
        <div style={css('width:30px;height:30px;border-radius:9px;background:#E5343B;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:16px;height:4px;background:#fff;border-radius:1px;')} />
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:4px;height:16px;background:#fff;border-radius:1px;')} />
        </div>
        <div>
          <Wordmark size={19} />
          <div style={css("font:500 8.5px 'IBM Plex Mono';color:#A39B90;letter-spacing:.04em;margin-top:4px;")}>EMERGENCIA · GENTE · INFO</div>
        </div>
      </div>

      <button onClick={actions.changeDisaster} className="egi-tap" style={css('margin-top:18px;display:flex;align-items:center;gap:10px;padding:10px 11px;background:#F4EFE7;border:1px solid #E7E1D8;border-radius:12px;cursor:pointer;text-align:left;')}>
        <span style={css("width:34px;height:34px;border-radius:9px;flex:none;background:#fff;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 9px 'IBM Plex Mono';color:#8B8278;")}>{v.selDisaster.tag}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:500 8px 'IBM Plex Mono';color:#A39B90;letter-spacing:.08em;")}>EMERGENCIA ACTIVA</div>
          <div style={css("font:600 12.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.disasterName}</div>
        </div>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#C2272D;flex:none;")}>Cambiar</span>
      </button>

      <button onClick={() => actions.openReport('missing')} className="egi-tap" style={css("margin:14px 0 10px;display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;background:#E5343B;border:none;border-radius:12px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 10px 22px -14px rgba(206,53,46,.5);")}>
        <span style={css('width:16px;height:16px;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:13px;height:2.6px;background:#fff;border-radius:2px;')} />
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:2.6px;height:13px;background:#fff;border-radius:2px;')} />
        </span>
        Reportar
      </button>

      <NavButton onClick={() => actions.setScreen('home')} nav={v.navHome} icon={<HomeIcon />} label="Inicio" />
      <NavButton onClick={() => actions.setScreen('search')} nav={v.navSearch} icon={<SearchIcon />} label="Buscar" />
      <NavButton onClick={() => actions.setScreen('shelters')} nav={v.navShelters} icon={<SheltersIcon />} label="Refugios" />
      <NavButton onClick={() => actions.setScreen('mine')} nav={v.navMine} icon={<MineIcon />} label="Mis reportes" />
      <NavButton onClick={() => actions.setScreen('mesh')} nav={v.navMesh} icon={<MeshIcon />} label="Red local" />
      <NavButton onClick={() => actions.setScreen('duplicates')} nav={v.navDuplicates} icon={<MineIcon />} label="Revisar duplicados" />

      <div style={css('flex:1;')} />

      <button onClick={actions.toggleOnline} className="egi-tap" style={{ ...css('display:flex;align-items:center;gap:10px;padding:12px;border-radius:12px;cursor:pointer;text-align:left;'), border: `1px solid ${c.border}`, background: c.bg }}>
        <span style={{ ...css('width:9px;height:9px;border-radius:50%;flex:none;'), background: c.dot }} />
        <div style={css('flex:1;min-width:0;')}>
          <div style={{ ...css("font:600 12px 'IBM Plex Sans';"), color: c.fg }}>{c.title}</div>
          <div style={{ ...css("font:500 9.5px 'IBM Plex Mono';margin-top:2px;"), color: c.sub }}>{c.hint}</div>
        </div>
      </button>

      <div style={css('display:flex;align-items:center;gap:10px;margin-top:12px;padding-top:12px;border-top:1px solid #EFEBE5;')}>
        <span style={css("width:32px;height:32px;border-radius:50%;flex:none;background:#EDE7DE;display:flex;align-items:center;justify-content:center;font:600 11px 'IBM Plex Mono';color:#8B8278;")}>{v.userInitials}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 12px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.userName}</div>
          <div style={css("font:400 9.5px 'IBM Plex Mono';color:#A39B90;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.userEmail}</div>
        </div>
        <button onClick={actions.signOut} className="egi-tap" style={css("border:none;background:transparent;cursor:pointer;font:600 9.5px 'IBM Plex Mono';color:#A39B90;flex:none;")}>Salir</button>
      </div>
    </div>
  )
}

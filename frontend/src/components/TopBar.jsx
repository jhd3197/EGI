import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import Wordmark from './Wordmark.jsx'
import { SettingsIcon, BellIcon } from './Icons.jsx'

// Mobile-only top bar + the disaster strip below it. Consolidated in plan-31 §3.2:
// the language switcher moved to Settings, the mesh + connection pills collapsed
// into one status pill (mesh peers when the local network is on, else online /
// offline), and the disaster strip is a single line.
export default function TopBar({ view, actions }) {
  const v = view
  const c = v.conn
  const { t } = useI18n()

  // Single status pill: shows the local-network peer count while mesh is active,
  // otherwise the online/offline state. Tapping it jumps to mesh / toggles net.
  const meshOn = v.mesh.running
  const statusOnClick = meshOn ? () => actions.setScreen('mesh') : actions.toggleOnline
  const statusBg = meshOn ? '#E9F4ED' : c.bg
  const statusBorder = meshOn ? '#CCE6D6' : c.border
  const statusFg = meshOn ? '#15683A' : c.fg
  const statusDot = meshOn ? '#1B7A45' : c.dot
  const statusText = meshOn ? t('mesh.peersPill', { n: v.mesh.peers }) : c.pill
  const statusAria = meshOn ? t('nav.mesh') : t('conn.statusAria')

  const iconBtn = css('display:flex;align-items:center;cursor:pointer;padding:6px;border-radius:10px;border:none;background:transparent;color:#9A938A;')

  return (
    <>
      <div style={{ ...css('align-items:center;justify-content:space-between;padding:14px 18px 10px;flex:none;background:#fff;'), display: v.topbarDisplay }}>
        <div style={css('display:flex;align-items:center;gap:9px;')}>
          <div aria-hidden="true" style={css('width:26px;height:26px;border-radius:8px;background:#E5343B;position:relative;flex:none;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:14px;height:3.4px;background:#fff;border-radius:1px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:3.4px;height:14px;background:#fff;border-radius:1px;')} />
          </div>
          <Wordmark size={19} />
        </div>
        <div style={css('display:flex;align-items:center;gap:4px;')}>
          <button onClick={() => actions.setScreen('settings')} className="egi-tap" aria-label={t('notif.bellAria')} style={iconBtn}>
            <span aria-hidden="true" style={css('display:flex;')}><BellIcon size={16} /></span>
          </button>
          <button onClick={() => actions.setScreen('settings')} className="egi-tap" aria-label={t('nav.settings')} style={{ ...iconBtn, color: v.isSettings ? '#E5343B' : '#9A938A' }}>
            <span aria-hidden="true" style={css('display:flex;')}><SettingsIcon size={16} /></span>
          </button>
          <button onClick={statusOnClick} className="egi-tap" aria-label={statusAria} aria-live="polite" style={{ ...css('display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 11px;border-radius:20px;margin-left:4px;'), border: `1px solid ${statusBorder}`, background: statusBg }}>
            <span aria-hidden="true" style={{ ...css('width:7px;height:7px;border-radius:50%;display:inline-block;'), background: statusDot }} />
            <span style={{ ...css("font:600 10px 'IBM Plex Mono';letter-spacing:.03em;"), color: statusFg }}>{statusText}</span>
          </button>
        </div>
      </div>

      <button onClick={actions.changeDisaster} className="egi-tap" style={{ ...css('align-items:center;gap:10px;width:100%;padding:9px 18px;background:#F1F3F5;border:none;border-top:1px solid #ECE8E2;border-bottom:1px solid #ECE8E2;cursor:pointer;text-align:left;'), display: v.topbarDisplay }}>
        <span style={css("width:28px;height:28px;border-radius:8px;flex:none;background:#fff;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 8.5px 'IBM Plex Mono';color:#8B8278;")}>{v.selDisaster.tag}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 12.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.disasterName}</div>
        </div>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#C2272D;flex:none;")}>{t('common.change')}</span>
      </button>
    </>
  )
}

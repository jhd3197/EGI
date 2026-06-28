import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { LangSelect } from './Sidebar.jsx'
import Wordmark from './Wordmark.jsx'
import { MeshIcon, SettingsIcon } from './Icons.jsx'

// Mobile-only top bar + the disaster strip below it.
export default function TopBar({ view, actions }) {
  const v = view
  const c = v.conn
  const { t } = useI18n()
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
        <div style={css('display:flex;align-items:center;gap:8px;')}>
          <LangSelect compact />
          <button onClick={() => actions.setScreen('mesh')} className="egi-tap" aria-label={t('nav.mesh')} style={{ ...css('display:flex;align-items:center;gap:5px;cursor:pointer;padding:6px 9px;border-radius:20px;'), border: `1px solid ${v.mesh.running ? '#CCE6D6' : '#E2DED8'}`, background: v.mesh.running ? '#E9F4ED' : '#fff', color: v.mesh.running ? '#15683A' : '#8A837A' }}>
            <span aria-hidden="true" style={css('display:flex;')}><MeshIcon size={14} /></span>
            <span style={css("font:600 10px 'IBM Plex Mono';letter-spacing:.03em;")}>{v.mesh.peers}</span>
          </button>
          <button onClick={() => actions.setScreen('settings')} className="egi-tap" aria-label={t('nav.settings')} style={{ ...css('display:flex;align-items:center;cursor:pointer;padding:6px 9px;border-radius:20px;'), border: `1px solid ${v.isSettings ? '#E5343B' : '#E2DED8'}`, background: v.isSettings ? '#FFF1F0' : '#fff', color: v.isSettings ? '#E5343B' : '#8A837A' }}>
            <span aria-hidden="true" style={css('display:flex;')}><SettingsIcon size={14} /></span>
          </button>
          <button onClick={actions.toggleOnline} className="egi-tap" aria-label={t('conn.statusAria')} aria-live="polite" style={{ ...css('display:flex;align-items:center;gap:6px;cursor:pointer;padding:6px 11px;border-radius:20px;'), border: `1px solid ${c.border}`, background: c.bg }}>
            <span aria-hidden="true" style={{ ...css('width:7px;height:7px;border-radius:50%;display:inline-block;'), background: c.dot }} />
            <span style={{ ...css("font:600 10px 'IBM Plex Mono';letter-spacing:.03em;"), color: c.fg }}>{c.pill}</span>
          </button>
        </div>
      </div>

      <button onClick={actions.changeDisaster} className="egi-tap" style={{ ...css('align-items:center;gap:10px;width:100%;padding:9px 18px;background:#F1F3F5;border:none;border-top:1px solid #ECE8E2;border-bottom:1px solid #ECE8E2;cursor:pointer;text-align:left;'), display: v.topbarDisplay }}>
        <span style={css("width:28px;height:28px;border-radius:8px;flex:none;background:#fff;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 8.5px 'IBM Plex Mono';color:#8B8278;")}>{v.selDisaster.tag}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:500 8px 'IBM Plex Mono';color:#6E685E;letter-spacing:.08em;")}>{t('nav.activeEmergency')}</div>
          <div style={css("font:600 12.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.disasterName}</div>
        </div>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#C2272D;flex:none;")}>{t('common.change')}</span>
      </button>
    </>
  )
}

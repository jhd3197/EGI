import { css } from '../lib/css.js'
import { useI18n, LANGS } from '../i18n/index.js'
import { HomeIcon, SearchIcon, SheltersIcon, MineIcon, MeshIcon } from './Icons.jsx'
import Wordmark from './Wordmark.jsx'

// Compact language selector used in both the sidebar and the mobile top bar.
export function LangSelect({ compact }) {
  const { lang, setLang, t } = useI18n()
  return (
    <select
      value={lang}
      onChange={(e) => setLang(e.target.value)}
      aria-label={t('common.language')}
      style={css(
        "border:1px solid #E2DED8;background:#fff;border-radius:" + (compact ? '20px' : '10px') +
        ";color:#5A534C;font:600 " + (compact ? '10px' : '11.5px') +
        " 'IBM Plex Mono';padding:" + (compact ? '6px 8px' : '8px 10px') + ";cursor:pointer;outline:none;"
      )}
    >
      {LANGS.map((l) => (
        <option key={l.code} value={l.code}>{compact ? l.code.toUpperCase() : l.label}</option>
      ))}
    </select>
  )
}

function NavButton({ onClick, nav, icon, label }) {
  return (
    <button onClick={onClick} className="egi-tap" style={{ ...css('display:flex;align-items:center;gap:12px;padding:11px 12px;border:none;border-radius:11px;cursor:pointer;text-align:left;'), background: nav.bg, color: nav.color }}>
      <span aria-hidden="true" style={css('display:flex;')}>{icon}</span>
      <span style={css("font:600 13.5px 'IBM Plex Sans';")}>{label}</span>
    </button>
  )
}

export default function Sidebar({ view, actions }) {
  const v = view
  const c = v.conn
  const { t } = useI18n()
  return (
    <div style={{ ...css('flex-direction:column;width:256px;flex:none;height:100%;background:#fff;border-right:1px solid #ECE8E2;padding:22px 16px;gap:5px;'), display: v.sidebarDisplay }}>
      <div style={css('display:flex;align-items:center;gap:10px;padding:0 8px 4px;')}>
        <div aria-hidden="true" style={css('width:30px;height:30px;border-radius:9px;background:#E5343B;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:16px;height:4px;background:#fff;border-radius:1px;')} />
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:4px;height:16px;background:#fff;border-radius:1px;')} />
        </div>
        <div>
          <Wordmark size={19} />
          <div style={css("font:500 8.5px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;margin-top:4px;")}>{t('nav.egiSub')}</div>
        </div>
      </div>

      <button onClick={actions.changeDisaster} className="egi-tap" style={css('margin-top:18px;display:flex;align-items:center;gap:10px;padding:10px 11px;background:#F4EFE7;border:1px solid #E7E1D8;border-radius:12px;cursor:pointer;text-align:left;')}>
        <span style={css("width:34px;height:34px;border-radius:9px;flex:none;background:#fff;border:1px solid #E7E1D8;display:flex;align-items:center;justify-content:center;font:600 9px 'IBM Plex Mono';color:#8B8278;")}>{v.selDisaster.tag}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:500 8px 'IBM Plex Mono';color:#6E685E;letter-spacing:.08em;")}>{t('nav.activeEmergency')}</div>
          <div style={css("font:600 12.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.disasterName}</div>
        </div>
        <span style={css("font:500 10px 'IBM Plex Mono';color:#C2272D;flex:none;")}>{t('common.change')}</span>
      </button>

      <button onClick={() => actions.openReport('missing')} className="egi-tap" style={css("margin:14px 0 10px;display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;background:#E5343B;border:none;border-radius:12px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 10px 22px -14px rgba(206,53,46,.5);")}>
        <span aria-hidden="true" style={css('width:16px;height:16px;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:13px;height:2.6px;background:#fff;border-radius:2px;')} />
          <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:2.6px;height:13px;background:#fff;border-radius:2px;')} />
        </span>
        {t('nav.report')}
      </button>

      <NavButton onClick={() => actions.setScreen('home')} nav={v.navHome} icon={<HomeIcon />} label={t('nav.home')} />
      <NavButton onClick={() => actions.setScreen('search')} nav={v.navSearch} icon={<SearchIcon />} label={t('nav.search')} />
      <NavButton onClick={() => actions.setScreen('shelters')} nav={v.navShelters} icon={<SheltersIcon />} label={t('nav.shelters')} />
      <NavButton onClick={() => actions.setScreen('mine')} nav={v.navMine} icon={<MineIcon />} label={t('nav.mine')} />
      <NavButton onClick={() => actions.setScreen('mesh')} nav={v.navMesh} icon={<MeshIcon />} label={t('nav.mesh')} />
      {/* Operator (moderator) mode is a device-only toggle; when on it reveals
          the Moderar entry, which folds in the duplicate-review queue. */}
      {v.operator && (
        <NavButton onClick={() => actions.setScreen('moderation')} nav={v.navModeration} icon={<MineIcon />} label={t('nav.moderation')} />
      )}

      <div style={css('flex:1;')} />

      <button
        onClick={actions.toggleOperator}
        className="egi-tap"
        aria-pressed={v.operator}
        style={{
          ...css('display:flex;align-items:center;gap:10px;padding:10px 11px;border-radius:11px;cursor:pointer;text-align:left;margin-bottom:6px;'),
          border: v.operator ? '1px solid #15683A' : '1px solid #E2DED8',
          background: v.operator ? '#F1F8F3' : '#fff',
        }}
      >
        <span style={css('flex:1;min-width:0;')}>
          <span style={css("display:block;font:600 12px 'IBM Plex Sans';color:#1A1714;")}>{t('nav.operatorMode')}</span>
        </span>
        <span style={{ ...css('width:34px;height:19px;border-radius:11px;flex:none;position:relative;transition:background .15s;'), background: v.operator ? '#15683A' : '#CFC9C0' }}>
          <span style={{ ...css('position:absolute;top:2px;width:15px;height:15px;border-radius:50%;background:#fff;transition:left .15s;'), left: v.operator ? '17px' : '2px' }} />
        </span>
      </button>

      <div style={css('display:flex;align-items:center;gap:8px;margin-bottom:10px;')}>
        <span style={css("font:600 9.5px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;flex:none;")}>{t('common.language')}</span>
        <div style={css('flex:1;')}><LangSelect /></div>
      </div>

      <button onClick={actions.toggleOnline} className="egi-tap" aria-label={t('conn.statusAria')} aria-live="polite" style={{ ...css('display:flex;align-items:center;gap:10px;padding:12px;border-radius:12px;cursor:pointer;text-align:left;'), border: `1px solid ${c.border}`, background: c.bg }}>
        <span aria-hidden="true" style={{ ...css('width:9px;height:9px;border-radius:50%;flex:none;'), background: c.dot }} />
        <div style={css('flex:1;min-width:0;')}>
          <div style={{ ...css("font:600 12px 'IBM Plex Sans';"), color: c.fg }}>{c.title}</div>
          <div style={{ ...css("font:500 9.5px 'IBM Plex Mono';margin-top:2px;"), color: c.sub }}>{c.hint}</div>
        </div>
      </button>

      <div style={css('display:flex;align-items:center;gap:10px;margin-top:12px;padding-top:12px;border-top:1px solid #EFEBE5;')}>
        <span style={css("width:32px;height:32px;border-radius:50%;flex:none;background:#EDE7DE;display:flex;align-items:center;justify-content:center;font:600 11px 'IBM Plex Mono';color:#8B8278;")}>{v.userInitials}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 12px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.userName}</div>
          <div style={css("font:400 9.5px 'IBM Plex Mono';color:#6E685E;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{v.userEmail}</div>
        </div>
        <button onClick={actions.signOut} className="egi-tap" style={css("border:none;background:transparent;cursor:pointer;font:600 9.5px 'IBM Plex Mono';color:#6E685E;flex:none;")}>{t('common.signOut')}</button>
      </div>
    </div>
  )
}

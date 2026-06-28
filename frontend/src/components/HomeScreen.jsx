import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

export default function HomeScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()
  return (
    <div style={css('padding:16px 18px 28px;')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between;gap:7px;margin:4px 0 9px;')}>
        <div style={css('display:flex;align-items:center;gap:7px;')}>
          <span aria-hidden="true" style={css('width:7px;height:7px;border-radius:50%;background:#C2272D;display:inline-block;animation:egiPulse 1.6s ease-in-out infinite;')} />
          <span style={css("font:500 9.5px 'IBM Plex Mono';color:#B7242A;letter-spacing:.12em;")}>{t('nav.activeEmergency')}</span>
        </div>
        <button onClick={actions.toggleSimpleMode} className="egi-tap" aria-pressed={!!v.simpleMode} style={css("flex:none;padding:7px 12px;background:#fff;border:1px solid #E2DED8;border-radius:20px;cursor:pointer;font:600 11px 'IBM Plex Sans';color:#5A534C;")}>
          {t('simple.toggle')}
        </button>
      </div>
      <h1 style={css("margin:0 0 7px;font:700 25px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.02em;line-height:1.15;")}>{v.disasterName}</h1>
      <div style={css("font:400 11.5px 'IBM Plex Mono';color:#8B8278;")}>{v.disasterMeta}</div>
      <div style={css('height:1px;background:#E7E1D8;margin:17px 0 15px;')} />

      {/* Primary action 1 — Busco a alguien → search screen */}
      <button onClick={() => actions.setScreen('search')} className="egi-tap" style={css('width:100%;display:flex;align-items:center;gap:13px;padding:16px;background:#fff;border:1px solid #E6E2DC;border-radius:16px;cursor:pointer;text-align:left;box-shadow:0 1px 2px rgba(40,30,20,.04);')}>
        <span aria-hidden="true" style={css('width:36px;height:36px;border-radius:11px;background:#F2EFEA;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:9px;top:9px;width:14px;height:14px;border:2.4px solid #8A837A;border-radius:50%;')} />
          <span style={css('position:absolute;left:22px;top:22px;width:8px;height:2.4px;background:#8A837A;border-radius:1px;transform:rotate(45deg);')} />
        </span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{t('home.searchTitle')}</div>
        </div>
        <span aria-hidden="true" style={css('width:9px;height:9px;border-top:2.4px solid #C0B9AE;border-right:2.4px solid #C0B9AE;transform:rotate(45deg);flex:none;')} />
      </button>

      {/* Primary action 2 — Reportar (three sub-actions) */}
      <div style={css('margin-top:14px;')}>
        <div style={css('display:flex;align-items:baseline;gap:8px;margin:0 2px 9px;')}>
          <span style={css("font:600 13px 'IBM Plex Sans';color:#4A443D;")}>{t('home.reportGroup')}</span>
        </div>
        <button onClick={() => actions.openReport('missing')} className="egi-tap" style={css("width:100%;display:flex;align-items:center;gap:12px;padding:15px 14px;background:#E5343B;border:none;border-radius:14px;cursor:pointer;text-align:left;color:#fff;box-shadow:0 10px 22px -14px rgba(206,53,46,.5);")}>
          <span aria-hidden="true" style={css('width:32px;height:32px;border-radius:10px;background:rgba(255,255,255,.18);position:relative;flex:none;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:14px;height:3px;background:#fff;border-radius:2px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:3px;height:14px;background:#fff;border-radius:2px;')} />
          </span>
          <span style={css("flex:1;font:600 15px 'IBM Plex Sans';line-height:1.15;")}>{t('report.typeLabel.missing')}</span>
        </button>
        <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;')}>
          <button onClick={() => actions.openReport('sighting')} className="egi-tap" style={css("display:flex;flex-direction:column;gap:8px;padding:14px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;cursor:pointer;text-align:left;color:#1A1714;")}>
            <span aria-hidden="true" style={css('width:28px;height:28px;border-radius:9px;background:#E4EEF6;position:relative;flex:none;')}>
              <span style={css('position:absolute;left:7px;top:7px;width:14px;height:14px;border:2.2px solid #1F5E96;border-radius:50% 50% 50% 0;transform:rotate(45deg);')} />
            </span>
            <span style={css("font:600 13.5px 'IBM Plex Sans';line-height:1.15;")}>{t('report.typeLabel.sighting')}</span>
          </button>
          <button onClick={() => actions.openReport('safe')} className="egi-tap" style={css("display:flex;flex-direction:column;gap:8px;padding:14px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;cursor:pointer;text-align:left;color:#1A1714;")}>
            <span aria-hidden="true" style={css('width:28px;height:28px;border-radius:9px;background:#E3F2E7;position:relative;flex:none;')}>
              <span style={css('position:absolute;left:8px;top:14px;width:6px;height:2.6px;background:#1B7A45;border-radius:1px;transform:rotate(45deg);transform-origin:left;')} />
              <span style={css('position:absolute;left:12px;top:17px;width:11px;height:2.6px;background:#1B7A45;border-radius:1px;transform:rotate(-50deg);transform-origin:left;')} />
            </span>
            <span style={css("font:600 13.5px 'IBM Plex Sans';line-height:1.15;")}>{t('report.typeLabel.safe')}</span>
          </button>
        </div>
      </div>

      {/* Primary action 3 — Estoy bien (one-tap self check-in) */}
      <button onClick={actions.checkInSelf} className="egi-tap" style={css("width:100%;display:flex;align-items:center;gap:12px;padding:15px 14px;margin-top:14px;background:#E9F4ED;border:1px solid #BFE0CB;border-radius:14px;cursor:pointer;text-align:left;")}>
        <span aria-hidden="true" style={css('width:36px;height:36px;border-radius:11px;background:#1B7A45;position:relative;flex:none;')}>
          <span style={css('position:absolute;left:10px;top:19px;width:7px;height:3px;background:#fff;border-radius:1px;transform:rotate(45deg);transform-origin:left;')} />
          <span style={css('position:absolute;left:14px;top:22px;width:13px;height:3px;background:#fff;border-radius:1px;transform:rotate(-50deg);transform-origin:left;')} />
        </span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 15px 'IBM Plex Sans';color:#15683A;")}>{t('home.imOk')}</div>
          <div style={css("font:400 11.5px 'IBM Plex Sans';color:#4A7B5C;margin-top:1px;")}>{t('home.imOkSub')}</div>
        </div>
        {v.checkedInSafe && <span role="status" aria-live="polite" style={css("font:600 10px 'IBM Plex Mono';color:#15683A;flex:none;")}>{t('home.saved')}</span>}
      </button>

      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin:24px 0 10px;')}>
        <h2 style={css("margin:0;font:600 15px 'IBM Plex Sans';color:#1A1714;")}>{t('home.recentActivity')}</h2>
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

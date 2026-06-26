import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

export default function SheltersScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()
  return (
    <div style={css('padding:16px 18px 24px;')}>
      <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('shelters.title')}</h1>
      <p style={css("margin:0 0 16px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{t('shelters.subtitle')}</p>
      <div style={css('display:flex;flex-direction:column;gap:11px;')}>
        {v.institutions.map((i, idx) => (
          <div key={idx} className="egi-tap" style={css('padding:14px;background:#fff;border:1px solid #EDE9E3;border-radius:15px;')}>
            <div style={css('display:flex;align-items:center;gap:10px;')}>
              <span style={{ ...css("width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex:none;font:600 10px 'IBM Plex Mono';"), background: i.tintBg, color: i.tintFg }}>{i.tag}</span>
              <div style={css('flex:1;min-width:0;')}>
                <div style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{i.name}</div>
                <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{i.loc}</div>
              </div>
            </div>
            <div style={css('display:flex;align-items:center;gap:8px;margin-top:11px;flex-wrap:wrap;')}>
              <span style={css("padding:4px 10px;border-radius:7px;font:600 11px 'IBM Plex Mono';background:#F2EFEA;color:#5A534C;")}>{i.count}</span>
              {i.hasMinors && (
                <span style={css("padding:4px 10px;border-radius:7px;font:600 11px 'IBM Plex Sans';background:#FBEEDA;color:#9A6400;")}>{i.minors}</span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div style={css('margin-top:16px;padding:14px;border:1px dashed #D8D2C9;border-radius:15px;text-align:center;')}>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#2A2520;")}>{t('shelters.areYou')}</div>
        <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin:4px 0 11px;")}>{t('shelters.publish')}</div>
        <button onClick={() => actions.openReport('safe')} className="egi-tap" style={css("padding:10px 18px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelters.register')}</button>
      </div>
    </div>
  )
}

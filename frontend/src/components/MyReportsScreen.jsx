import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

export default function MyReportsScreen({ view }) {
  const v = view
  const { t } = useI18n()
  return (
    <div style={css('padding:16px 18px 24px;')}>
      <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('mine.title')}</h1>
      <p style={css("margin:0 0 16px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{t('mine.subtitle')}</p>
      <div style={css('display:flex;flex-direction:column;gap:10px;')}>
        {v.myReports.map((m, idx) => (
          <div key={idx} style={css('display:flex;align-items:center;gap:12px;padding:13px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
            <span style={css('width:40px;height:40px;border-radius:11px;flex:none;background-image:repeating-linear-gradient(45deg,#EFEDE9,#EFEDE9 5px,#E4E1DB 5px,#E4E1DB 10px);')} />
            <div style={css('flex:1;min-width:0;')}>
              <div style={css("font:600 13.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{m.name}</div>
              <div style={css("font:400 11px 'IBM Plex Mono';color:#A9A299;margin-top:3px;")}>{m.sub}</div>
            </div>
            <span style={{ ...css("padding:5px 10px;border-radius:8px;font:600 10.5px 'IBM Plex Sans';flex:none;"), background: m.bg, color: m.fg }}>{m.status}</span>
          </div>
        ))}
      </div>
      <div style={css('margin-top:14px;display:flex;align-items:center;gap:9px;padding:12px 14px;background:#FCEDEC;border-radius:13px;')}>
        <span style={css('width:7px;height:7px;border-radius:50%;background:#C2272D;flex:none;')} />
        <span style={css("font:500 11.5px 'IBM Plex Sans';color:#B7242A;")}>{t('mine.queueNote')}</span>
      </div>
    </div>
  )
}

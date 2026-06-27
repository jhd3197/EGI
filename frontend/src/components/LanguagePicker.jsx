import { css } from '../lib/css.js'
import { useI18n, LANGS } from '../i18n/index.js'

// Offline-capable language picker. All dictionaries are bundled into the app, so
// switching language never touches the network. Rendered as a row of buttons
// (friendlier for low-literacy users than a <select>) that call setLang().
//
// Props:
//   compact — smaller paddings/labels for tight spots (e.g. inside simple mode)
export default function LanguagePicker({ compact = false }) {
  const { lang, setLang, t } = useI18n()
  const pad = compact ? '8px 12px' : '11px 14px'
  const fontPx = compact ? '13px' : '15px'
  return (
    <div role="group" aria-label={t('common.language')} style={css('display:flex;flex-wrap:wrap;gap:8px;justify-content:center;')}>
      {LANGS.map((l) => {
        const on = lang === l.code
        return (
          <button
            key={l.code}
            onClick={() => setLang(l.code)}
            className="egi-tap"
            aria-pressed={on}
            lang={l.code}
            style={{
              ...css('border-radius:11px;cursor:pointer;'),
              padding: pad,
              font: `600 ${fontPx} 'IBM Plex Sans'`,
              border: on ? '1.5px solid #1A1714' : '1px solid #E2DED8',
              background: on ? '#1A1714' : '#fff',
              color: on ? '#fff' : '#5A534C',
            }}
          >
            {l.label}
          </button>
        )
      })}
    </div>
  )
}

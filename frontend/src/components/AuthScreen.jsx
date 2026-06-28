import { useState } from 'react'
import { css } from '../lib/css.js'
import { color } from '../styles/tokens.js'
import { useI18n } from '../i18n/index.js'
import Logo from './Logo.jsx'
import Wordmark from './Wordmark.jsx'
import LanguagePicker from './LanguagePicker.jsx'

// Honest entry: no remote auth. The user either types an alias (kept on this
// device only) or enters anonymously as "Invitado". Nothing is uploaded here.
export default function AuthScreen({ actions }) {
  const { t } = useI18n()
  const [alias, setAlias] = useState('')
  const trimmed = alias.trim()

  const enterAlias = () => {
    if (!trimmed) return
    actions.signIn('alias', trimmed)
  }

  return (
    <div style={{ ...css("height:100vh;width:100%;display:flex;align-items:center;justify-content:center;padding:24px;font-family:'IBM Plex Sans',system-ui,sans-serif;"), background: color.bg }}>
      <div style={css('width:100%;max-width:372px;display:flex;flex-direction:column;align-items:center;text-align:center;')}>
        <div style={css('display:flex;align-items:center;gap:11px;margin-bottom:20px;')}>
          <Logo size={40} radius={12} bar={21} thick={5} />
          <Wordmark size={32} />
        </div>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#C2272D;margin-bottom:8px;")}>{t('auth.tagline')}</div>
        <div style={css("font:500 10px 'IBM Plex Mono';color:#6E685E;letter-spacing:.16em;margin-bottom:16px;")}>{t('auth.eyebrow')}</div>

        {/* Pick a language before entering — fully offline (bundled dicts). */}
        <div style={css('margin-bottom:18px;')}><LanguagePicker /></div>
        <h1 style={css("margin:0 0 10px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;line-height:1.3;text-wrap:balance;")}>{t('auth.title')}</h1>
        <p style={css("margin:0 0 24px;font:400 13.5px 'IBM Plex Sans';color:#6A645C;line-height:1.55;max-width:320px;")}>{t('auth.subtitle')}</p>

        <label htmlFor="egi-alias" style={css("align-self:flex-start;font:600 12px 'IBM Plex Sans';color:#4A443D;margin-bottom:7px;")}>{t('auth.aliasLabel')}</label>
        <input
          id="egi-alias"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') enterAlias() }}
          placeholder={t('auth.aliasPlaceholder')}
          autoComplete="off"
          style={css("width:100%;padding:13px 14px;background:#fff;border:1px solid #DCD6CD;border-radius:12px;outline:none;font:400 14px 'IBM Plex Sans';color:#1A1714;margin-bottom:9px;box-sizing:border-box;")}
        />
        <button
          onClick={enterAlias}
          disabled={!trimmed}
          className="egi-tap"
          style={{
            ...css("width:100%;padding:14px;border:none;border-radius:12px;font:600 14px 'IBM Plex Sans';color:#fff;margin-bottom:9px;"),
            background: trimmed ? '#E5343B' : '#E0B9B7',
            cursor: trimmed ? 'pointer' : 'default',
          }}
        >
          {t('auth.enterAlias')}
        </button>
        <button onClick={() => actions.signIn('guest')} className="egi-tap" style={css('width:100%;display:flex;flex-direction:column;align-items:center;gap:3px;padding:12px;background:transparent;border:1px solid #E2DCD2;border-radius:12px;cursor:pointer;')}>
          <span style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;")}>{t('auth.enterGuest')}</span>
          <span style={css("font:400 10.5px 'IBM Plex Mono';color:#6E685E;")}>{t('auth.guestNote')}</span>
        </button>

        <div style={css('margin-top:26px;display:flex;align-items:center;gap:7px;')}>
          <span style={css('width:6px;height:6px;border-radius:50%;background:#C2272D;display:inline-block;')} />
          <span style={css("font:400 10.5px 'IBM Plex Mono';color:#6E685E;")}>{t('auth.signalNote')}</span>
        </div>
      </div>
    </div>
  )
}

import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { speak, canSpeak } from '../lib/speech.js'
import LanguagePicker from './LanguagePicker.jsx'

// SimpleHomeScreen — the low-literacy / panic "Modo simple" home (plan-14,
// Phase 5). Three GIANT, high-contrast, full-width actions with large icons and
// minimal text. Each action has a round speaker button that reads its label
// aloud (TTS) for people who cannot read. The existing report/search flows are
// reused as-is — this screen only changes the entry point, not the flows.

// A round "listen" (🔊) button. Speaks `text` in the current language on tap.
function SpeakButton({ text, lang, ariaLabel }) {
  if (!canSpeak()) return null
  return (
    <button
      onClick={(e) => { e.stopPropagation(); speak(text, lang) }}
      className="egi-tap"
      aria-label={ariaLabel}
      style={css('flex:none;width:52px;height:52px;border-radius:50%;border:none;background:rgba(255,255,255,.22);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:24px;color:#fff;')}
    >
      <span aria-hidden="true">🔊</span>
    </button>
  )
}

// A single giant action. `onActivate` runs the existing flow; the speaker reads
// `audio` aloud. `icon` is a presentational element (reused HomeScreen style).
function BigAction({ label, audio, lang, bg, fg, icon, onActivate, listenAria }) {
  return (
    <div style={{ ...css('display:flex;align-items:center;gap:14px;border-radius:20px;padding:0 18px 0 0;'), background: bg }}>
      <button
        onClick={onActivate}
        className="egi-tap"
        style={{
          ...css('flex:1;display:flex;align-items:center;gap:16px;min-height:84px;padding:18px;background:transparent;border:none;border-radius:20px;cursor:pointer;text-align:left;'),
          color: fg,
        }}
      >
        <span aria-hidden="true" style={css('width:52px;height:52px;border-radius:14px;background:rgba(255,255,255,.22);position:relative;flex:none;')}>
          {icon}
        </span>
        <span style={{ ...css("flex:1;font:700 24px 'IBM Plex Sans';line-height:1.15;"), color: fg }}>{label}</span>
      </button>
      <SpeakButton text={audio} lang={lang} ariaLabel={listenAria} />
    </div>
  )
}

export default function SimpleHomeScreen({ actions }) {
  const { t, lang } = useI18n()
  const listenAria = (label) => t('simple.listen') + ': ' + label

  return (
    <div style={css('padding:20px 18px 32px;display:flex;flex-direction:column;gap:16px;')}>
      <div style={css('display:flex;align-items:center;gap:8px;margin:4px 0 2px;')}>
        <span aria-hidden="true" style={css('width:8px;height:8px;border-radius:50%;background:#C2272D;display:inline-block;animation:egiPulse 1.6s ease-in-out infinite;')} />
        <span style={css("font:600 11px 'IBM Plex Mono';color:#B7242A;letter-spacing:.1em;")}>{t('nav.activeEmergency')}</span>
      </div>

      {/* 1 — Busco a alguien → search screen */}
      <BigAction
        label={t('simple.search')}
        audio={t('simple.searchAudio')}
        lang={lang}
        bg="#1A1714"
        fg="#fff"
        listenAria={listenAria(t('simple.search'))}
        onActivate={() => actions.setScreen('search')}
        icon={
          <>
            <span style={css('position:absolute;left:14px;top:14px;width:18px;height:18px;border:3px solid #fff;border-radius:50%;')} />
            <span style={css('position:absolute;left:31px;top:31px;width:11px;height:3px;background:#fff;border-radius:2px;transform:rotate(45deg);')} />
          </>
        }
      />

      {/* 2 — Reportar a alguien → report flow (missing) */}
      <BigAction
        label={t('simple.report')}
        audio={t('simple.reportAudio')}
        lang={lang}
        bg="#E5343B"
        fg="#fff"
        listenAria={listenAria(t('simple.report'))}
        onActivate={() => actions.openReport('missing')}
        icon={
          <>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:22px;height:4px;background:#fff;border-radius:2px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:4px;height:22px;background:#fff;border-radius:2px;')} />
          </>
        }
      />

      {/* 3 — Estoy bien → one-tap self check-in */}
      <BigAction
        label={t('simple.safe')}
        audio={t('simple.safeAudio')}
        lang={lang}
        bg="#1B7A45"
        fg="#fff"
        listenAria={listenAria(t('simple.safe'))}
        onActivate={actions.checkInSelf}
        icon={
          <>
            <span style={css('position:absolute;left:15px;top:28px;width:11px;height:4px;background:#fff;border-radius:2px;transform:rotate(45deg);transform-origin:left;')} />
            <span style={css('position:absolute;left:21px;top:32px;width:20px;height:4px;background:#fff;border-radius:2px;transform:rotate(-50deg);transform-origin:left;')} />
          </>
        }
      />

      {/* Language picker — reachable in simple mode (offline, bundled dicts). */}
      <div style={css('margin-top:8px;')}>
        <LanguagePicker compact />
      </div>

      {/* Exit back to the full UI. */}
      <button
        onClick={actions.toggleSimpleMode}
        className="egi-tap"
        style={css("margin-top:4px;width:100%;min-height:56px;padding:14px;background:#fff;border:1px solid #E2DED8;border-radius:14px;cursor:pointer;font:600 16px 'IBM Plex Sans';color:#5A534C;")}
      >
        {t('simple.exit')}
      </button>
    </div>
  )
}

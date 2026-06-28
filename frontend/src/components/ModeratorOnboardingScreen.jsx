import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n, LANGS } from '../i18n/index.js'

// Remote-moderator onboarding (plan-25 Phase 3). A logged-in user picks the
// languages + regions they can cover, reads a short training example, and joins.
// Joining signs them up then marks them trained in one tap. Server-backed; with
// no operator token set the join button gently no-ops (returns null).
export default function ModeratorOnboardingScreen({ view, actions }) {
  const { t } = useI18n()
  const [langs, setLangs] = useState([])
  const [regions, setRegions] = useState('')
  const [joined, setJoined] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => { actions.fetchModeratorMe() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const profile = view.moderatorProfile
  const already = !!(profile && profile.trained)

  const toggleLang = (code) =>
    setLangs((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]))

  const join = async () => {
    setBusy(true)
    const regionList = regions.split(',').map((r) => r.trim()).filter(Boolean)
    const res = await actions.moderatorSignup({ languages: langs, regions: regionList })
    if (res) { await actions.markModeratorTrained(); setJoined(true) }
    setBusy(false)
  }

  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;margin-bottom:14px;')}>
        <button onClick={() => actions.setScreen('moderation')} className="egi-tap" style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('modOnboard.title')}</h1>
      </div>
      <p style={css("margin:0 0 18px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>{t('modOnboard.intro')}</p>

      {(joined || already) ? (
        <div style={css("padding:18px;background:#E9F4ED;border:1px solid #BFE0CB;border-radius:14px;font:600 13.5px 'IBM Plex Sans';color:#15683A;line-height:1.45;")}>
          {t('modOnboard.joined')}
        </div>
      ) : (
        <>
          <h2 style={css("margin:0 0 9px;font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('modOnboard.languages')}</h2>
          <div style={css('display:flex;gap:7px;flex-wrap:wrap;margin-bottom:18px;')}>
            {LANGS.map((l) => {
              const on = langs.includes(l.code)
              return (
                <button
                  key={l.code}
                  onClick={() => toggleLang(l.code)}
                  className="egi-tap"
                  style={{
                    ...css("padding:8px 14px;border-radius:18px;font:600 12px 'IBM Plex Sans';cursor:pointer;"),
                    border: on ? '1px solid #1A1714' : '1px solid #E2DED8',
                    background: on ? '#1A1714' : '#fff',
                    color: on ? '#fff' : '#5A534C',
                  }}
                >
                  {l.label}
                </button>
              )
            })}
          </div>

          <h2 style={css("margin:0 0 9px;font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('modOnboard.regions')}</h2>
          <input
            value={regions}
            onChange={(e) => setRegions(e.target.value)}
            placeholder={t('modOnboard.regionsPlaceholder')}
            style={css("width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;margin-bottom:18px;")}
          />

          <h2 style={css("margin:0 0 9px;font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('modOnboard.training')}</h2>
          <p style={css("margin:0 0 20px;padding:14px;background:#F6F3EF;border-radius:13px;font:400 13px 'IBM Plex Sans';color:#4A443D;line-height:1.5;")}>
            {t('modOnboard.trainingExample')}
          </p>

          <button
            onClick={join}
            disabled={busy}
            className="egi-tap"
            style={{
              ...css("width:100%;padding:14px;background:#15683A;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;"),
              opacity: busy ? 0.6 : 1,
            }}
          >
            {t('modOnboard.join')}
          </button>
        </>
      )}
    </div>
  )
}

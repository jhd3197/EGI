import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

export default function PersonDetail({ view, actions }) {
  const v = view
  const sel = v.sel
  const { t } = useI18n()
  const [note, setNote] = useState('')
  const [confidence, setConfidence] = useState('witness')
  if (!sel) return null
  const submitNote = () => {
    const text = note.trim()
    if (!text) return
    actions.addPersonReport(sel.id, text, confidence)
    setNote('')
  }
  const confidenceOptions = [
    ['self', t('detail.conf.self')], ['official', t('detail.conf.official')],
    ['witness', t('detail.conf.witness')], ['ocr', t('detail.conf.ocr')],
  ]
  return (
    <div style={css('padding:0 0 24px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;padding:8px 16px 12px;')}>
        <button onClick={() => actions.setScreen('search')} className="egi-tap" style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{t('detail.casePrefix')} {sel.caseId}</span>
      </div>

      <div style={css('padding:0 18px;')}>
        <div style={css('position:relative;width:100%;height:230px;border-radius:18px;overflow:hidden;background-image:repeating-linear-gradient(45deg,#EFEDE9,#EFEDE9 9px,#E4E1DB 9px,#E4E1DB 18px);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;')}>
          <span style={css("font:600 40px 'IBM Plex Mono';color:#BCB3A8;")}>{sel.initials}</span>
          <span style={css("font:500 10px 'IBM Plex Mono';color:#B3ABA1;letter-spacing:.08em;")}>{t('detail.photo')}</span>
          <span style={{ ...css("position:absolute;top:13px;left:13px;padding:5px 11px;border-radius:8px;font:600 11px 'IBM Plex Sans';"), background: sel.badgeBg, color: sel.badgeFg }}>{sel.statusLabel}</span>
        </div>

        <h1 style={css("margin:16px 0 3px;font:700 23px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{sel.name}</h1>
        <p style={css("margin:0 0 14px;font:400 13px 'IBM Plex Sans';color:#8A837A;")}>{sel.meta}</p>

        <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:14px;')}>
          <div style={css('padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
            <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;")}>{t('detail.lastPlace')}</div>
            <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;margin-top:4px;line-height:1.3;")}>{sel.place}</div>
          </div>
          <div style={css('padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
            <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;")}>{t('detail.date')}</div>
            <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;margin-top:4px;line-height:1.3;")}>{sel.date}</div>
          </div>
          <div style={css('padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;grid-column:1 / -1;')}>
            <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;")}>{t('detail.marks')}</div>
            <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;margin-top:4px;line-height:1.3;")}>{sel.clothes}</div>
          </div>
        </div>

        <p style={css("margin:0 0 16px;font:400 13.5px 'IBM Plex Sans';color:#4A443D;line-height:1.5;")}>{sel.desc}</p>

        <div style={css('display:flex;gap:9px;margin-bottom:18px;')}>
          <button onClick={() => actions.openReport('sighting')} className="egi-tap" style={css("flex:1;padding:13px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('detail.haveInfo')}</button>
          <button onClick={actions.markSafe} className="egi-tap" style={css("flex:none;padding:13px 16px;background:#fff;border:1px solid #BFE0CB;border-radius:13px;color:#15683A;font:600 13.5px 'IBM Plex Sans';cursor:pointer;")}>{t('detail.markSafe')}</button>
        </div>

        <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:11px;')}>
          <h2 style={css("margin:0;font:600 15px 'IBM Plex Sans';color:#1A1714;")}>{t('detail.updates')}</h2>
          <span style={css("font:500 10px 'IBM Plex Mono';color:#A9A299;")}>{t('detail.timeline')}</span>
        </div>

        <div style={css('display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;')}>
          {confidenceOptions.map(([key, label]) => {
            const on = confidence === key
            return (
              <button
                key={key}
                onClick={() => setConfidence(key)}
                className="egi-tap"
                style={{
                  ...css("padding:6px 11px;border-radius:18px;font:600 11px 'IBM Plex Mono';cursor:pointer;"),
                  border: on ? '1px solid #1A1714' : '1px solid #E2DED8',
                  background: on ? '#1A1714' : '#fff',
                  color: on ? '#fff' : '#5A534C',
                }}
              >
                {label}
              </button>
            )
          })}
        </div>
        <div style={css('display:flex;gap:8px;margin-bottom:14px;')}>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submitNote() }}
            placeholder={t('detail.notePlaceholder')}
            style={css("flex:1;min-width:0;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")}
          />
          <button onClick={submitNote} className="egi-tap" style={css("flex:none;padding:11px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('detail.addNote')}</button>
        </div>

        <div style={css('position:relative;padding-left:6px;')}>
          {sel.updates.map((u, idx) => (
            <div key={idx} style={css('display:flex;gap:13px;padding-bottom:16px;position:relative;')}>
              <div style={css('display:flex;flex-direction:column;align-items:center;flex:none;')}>
                <span style={{ ...css('width:11px;height:11px;border-radius:50%;border:2.5px solid #FBFAF8;z-index:2;'), background: u.dot, boxShadow: `0 0 0 1px ${u.dot}` }} />
                <span style={css('flex:1;width:2px;background:#EAE6E0;margin-top:2px;')} />
              </div>
              <div style={css('flex:1;')}>
                <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;line-height:1.35;")}>{u.t}</div>
                <div style={css("font:400 11px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{u.s}</div>
              </div>
            </div>
          ))}
        </div>

        <div style={css('display:flex;align-items:center;gap:11px;padding:13px;background:#F6F3EF;border-radius:13px;')}>
          <span style={css("width:36px;height:36px;border-radius:50%;background:#E8E3DC;display:flex;align-items:center;justify-content:center;font:600 13px 'IBM Plex Mono';color:#9A8F82;flex:none;")}>{sel.reporterInitials}</span>
          <div style={css('flex:1;min-width:0;')}>
            <div style={css("font:500 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;")}>{t('detail.reportedBy')}</div>
            <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;margin-top:2px;")}>{sel.reportedBy}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

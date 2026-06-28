import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Community flag dialog (plan-25): anyone can flag a record as wrong / outdated /
// duplicate / inappropriate / deceased / other, with an optional note. The POST
// is public + rate-limited and queues offline, so submission is optimistic — we
// show a thank-you and close regardless of delivery. Mirrors MeshWarningModal's
// overlay pattern.
const REASONS = ['wrong', 'outdated', 'duplicate', 'inappropriate', 'deceased', 'other']

export default function FlagModal({ open, recordType, recordId, onClose, actions }) {
  const { t } = useI18n()
  const [reason, setReason] = useState('wrong')
  const [note, setNote] = useState('')
  const [sent, setSent] = useState(false)

  if (!open) return null

  const close = () => { setSent(false); setReason('wrong'); setNote(''); onClose() }

  const submit = async () => {
    await actions.flagRecord(recordType, recordId, reason, note)
    setSent(true)
    setTimeout(close, 2200)
  }

  return (
    <div
      role="presentation"
      onClick={close}
      onKeyDown={(e) => { if (e.key === 'Escape') close() }}
      style={css('position:fixed;inset:0;z-index:70;background:rgba(26,23,20,.45);display:flex;align-items:flex-end;justify-content:center;padding:0;')}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="egi-flag-title"
        onClick={(e) => e.stopPropagation()}
        style={css('width:100%;max-width:480px;background:#fff;border-radius:24px 24px 0 0;padding:22px 20px 26px;box-shadow:0 -16px 48px -16px rgba(0,0,0,.35);max-height:92%;overflow-y:auto;')}
      >
        {sent ? (
          <div style={css('padding:24px 8px;text-align:center;')}>
            <p style={css("margin:0;font:600 15px 'IBM Plex Sans';color:#15683A;line-height:1.45;")}>{t('flag.sent')}</p>
          </div>
        ) : (
          <>
            <h2 id="egi-flag-title" style={css("margin:0 0 16px;font:700 18px 'IBM Plex Sans';color:#1A1714;")}>{t('flag.title')}</h2>

            <div style={css('display:flex;flex-direction:column;gap:8px;margin-bottom:16px;')}>
              {REASONS.map((key) => {
                const on = reason === key
                return (
                  <button
                    key={key}
                    onClick={() => setReason(key)}
                    className="egi-tap"
                    style={{
                      ...css("display:flex;align-items:center;gap:11px;padding:12px 13px;border-radius:12px;cursor:pointer;text-align:left;"),
                      border: on ? '1px solid #1A1714' : '1px solid #E2DED8',
                      background: on ? '#FBFAF8' : '#fff',
                    }}
                  >
                    <span style={{ ...css('width:18px;height:18px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;'), border: on ? '2px solid #1A1714' : '2px solid #CFC9C0' }}>
                      {on && <span style={css('width:8px;height:8px;border-radius:50%;background:#1A1714;')} />}
                    </span>
                    <span style={css("font:500 13.5px 'IBM Plex Sans';color:#2A2520;")}>{t('flag.reason.' + key)}</span>
                  </button>
                )
              })}
            </div>

            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('flag.note.placeholder')}
              rows={3}
              style={css("width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #E2DED8;border-radius:12px;font:400 13px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;resize:vertical;margin-bottom:16px;")}
            />

            <div style={css('display:flex;gap:9px;')}>
              <button
                onClick={close}
                className="egi-tap"
                style={css("flex:none;padding:13px 18px;background:#fff;border:1px solid #E2DED8;border-radius:13px;color:#5A534C;font:600 13.5px 'IBM Plex Sans';cursor:pointer;")}
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={submit}
                className="egi-tap"
                style={css("flex:1;padding:13px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;")}
              >
                {t('flag.submit')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

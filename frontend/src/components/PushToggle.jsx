import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { pushSupported, getPushState, enablePush, disablePush } from '../lib/push.js'

// Self-contained Web-Push opt-in toggle (plan-11). Subscribes the device to the
// active operation's alert topic so commanders' broadcasts reach this phone.
// Degrades quietly: hidden entirely on browsers without push support.
export default function PushToggle({ topic }) {
  const { t } = useI18n()
  const [on, setOn] = useState(false)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    let alive = true
    getPushState().then((s) => { if (alive) setOn(s.subscribed) })
    return () => { alive = false }
  }, [])

  if (!pushSupported()) return null

  const toggle = async () => {
    if (busy) return
    setBusy(true)
    setNote('')
    try {
      if (on) {
        await disablePush()
        setOn(false)
      } else {
        const res = await enablePush(topic || null)
        if (res.ok) {
          setOn(true)
        } else {
          const map = {
            denied: 'notif.denied',
            unsupported: 'notif.unsupported',
            'server-not-configured': 'notif.notConfigured',
          }
          setNote(t(map[res.reason] || 'notif.unsupported'))
        }
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={css('margin-bottom:8px;')}>
      <button
        onClick={toggle}
        disabled={busy}
        className="egi-tap"
        aria-pressed={on}
        style={{
          ...css('display:flex;align-items:center;gap:10px;padding:10px 11px;border-radius:11px;cursor:pointer;text-align:left;width:100%;'),
          border: on ? '1px solid #15683A' : '1px solid #E2DED8',
          background: on ? '#F1F8F3' : '#fff',
        }}
      >
        <span style={css('flex:1;min-width:0;')}>
          <span style={css("display:block;font:600 12px 'IBM Plex Sans';color:#1A1714;")}>
            {on ? t('notif.enabled') : t('notif.enable')}
          </span>
        </span>
        <span style={{ ...css('width:34px;height:19px;border-radius:11px;flex:none;position:relative;transition:background .15s;'), background: on ? '#15683A' : '#CFC9C0' }}>
          <span style={{ ...css('position:absolute;top:2px;width:15px;height:15px;border-radius:50%;background:#fff;transition:left .15s;'), left: on ? '17px' : '2px' }} />
        </span>
      </button>
      {note && (
        <div style={css("font:500 9.5px 'IBM Plex Mono';color:#B23B3B;margin-top:4px;padding:0 2px;")}>{note}</div>
      )}
    </div>
  )
}

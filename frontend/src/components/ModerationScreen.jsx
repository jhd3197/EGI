import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { Cluster } from './DuplicatesScreen.jsx'

// Phase 9 — Moderator UI. Three tabs: pending records, duplicate clusters, and
// stats. Moderation always requires the server, so each tab shows a gentle
// "needs connection" state when offline instead of crashing.

// A small colored badge for the record's source (ocr / ai_draft / pfif / sms…).
function SourceBadge({ source }) {
  const s = source || 'web'
  const tint = {
    ocr: ['#E4EEF6', '#1F5E96'],
    ai_draft: ['#F3E9F8', '#7A3E96'],
    pfif_import: ['#FBF0E2', '#9A6A1F'],
    sms: ['#E3F2E7', '#1B7A45'],
  }[s] || ['#F1EEE9', '#8A837A']
  return (
    <span style={{ ...css("padding:3px 8px;border-radius:7px;font:600 9.5px 'IBM Plex Mono';letter-spacing:.03em;flex:none;"), background: tint[0], color: tint[1] }}>
      {s.toUpperCase()}
    </span>
  )
}

function NeedsConnection() {
  const { t } = useI18n()
  return (
    <div style={css("padding:24px;text-align:center;background:#FCEDEC;border:1px solid #F6DAD7;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#B7242A;")}>
      {t('moderation.offline')}
    </div>
  )
}

function PendingTab({ view, actions }) {
  const m = view.moderation
  const { t } = useI18n()
  useEffect(() => { actions.fetchModerationPending() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  if (view.offline) return <NeedsConnection />
  if (m.loading) return <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>
  if (m.count === 0) {
    return (
      <div style={css("padding:24px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
        {t('moderation.empty')}
      </div>
    )
  }
  return (
    <div style={css('display:flex;flex-direction:column;gap:10px;')}>
      {m.pending.map((r) => (
        <div key={r.id} style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:13px 14px;')}>
          <div style={css('display:flex;align-items:center;gap:9px;margin-bottom:6px;')}>
            <div style={css("flex:1;min-width:0;font:600 13.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
              {r.name || r.given_name || t('common.noName')}
            </div>
            <SourceBadge source={r.source} />
          </div>
          <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-bottom:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
            {[r.cedula, r.location, (r.created_at || r.createdAt || '').slice(0, 10), r.id].filter(Boolean).join(' · ')}
          </div>
          <div style={css('display:flex;gap:9px;')}>
            <button
              onClick={() => actions.approveRecord(r.id)}
              className="egi-tap"
              style={css("flex:1;padding:10px;background:#15683A;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
            >
              {t('moderation.approve')}
            </button>
            <button
              onClick={() => actions.rejectRecord(r.id)}
              className="egi-tap"
              style={css("flex:none;padding:10px 16px;background:#fff;border:1px solid #F6DAD7;border-radius:11px;color:#C2272D;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
            >
              {t('moderation.reject')}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function DuplicatesTab({ view, actions }) {
  const d = view.duplicates
  const { t } = useI18n()
  useEffect(() => { actions.fetchDuplicates() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  if (view.offline) return <NeedsConnection />
  if (d.loading) return <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>
  if (d.count === 0) {
    return (
      <div style={css("padding:24px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
        {t('duplicates.empty')}
      </div>
    )
  }
  return d.clusters.map((c) => <Cluster key={c.cluster_id} cluster={c} actions={actions} />)
}

// Community flags tab (plan-25): the open flag queue. Critical flags are marked
// with a red badge. Each flag can be resolved (action taken) or dismissed.
function FlagsTab({ view, actions }) {
  const f = view.flags
  const { t } = useI18n()
  useEffect(() => { actions.fetchFlags() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  if (view.offline) return <NeedsConnection />
  if (f.loading) return <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>
  if (f.count === 0) {
    return (
      <div style={css("padding:24px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
        {t('mod.flags.empty')}
      </div>
    )
  }
  return (
    <div style={css('display:flex;flex-direction:column;gap:10px;')}>
      {f.list.map((fl) => {
        const critical = fl.severity === 'critical' || fl.severity === 'high'
        return (
          <div key={fl.id} style={{ ...css('background:#fff;border-radius:14px;padding:13px 14px;'), border: critical ? '1px solid #F6DAD7' : '1px solid #EDE9E3' }}>
            <div style={css('display:flex;align-items:center;gap:9px;margin-bottom:6px;')}>
              <span style={css("flex:1;min-width:0;font:600 13px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
                {t('flag.reason.' + (fl.flag_reason || 'other'))}
              </span>
              {critical && (
                <span style={{ ...css("padding:3px 8px;border-radius:7px;font:700 9.5px 'IBM Plex Mono';letter-spacing:.03em;flex:none;"), background: '#FCEDEC', color: '#B7242A' }}>
                  {t('mod.flags.critical')}
                </span>
              )}
            </div>
            <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
              {[fl.record_type, fl.record_id, fl.flagged_by, (fl.created_at || '').slice(0, 10)].filter(Boolean).join(' · ')}
            </div>
            {fl.note && (
              <p style={css("margin:0 0 10px;font:400 12.5px 'IBM Plex Sans';color:#4A443D;line-height:1.4;")}>{fl.note}</p>
            )}
            <div style={css('display:flex;gap:9px;')}>
              <button
                onClick={() => actions.resolveFlag(fl.id, 'resolved', 'rejected')}
                className="egi-tap"
                style={css("flex:1;padding:10px;background:#15683A;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
              >
                {t('mod.flags.resolve')}
              </button>
              <button
                onClick={() => actions.resolveFlag(fl.id, 'dismissed')}
                className="egi-tap"
                style={css("flex:none;padding:10px 16px;background:#fff;border:1px solid #E2DED8;border-radius:11px;color:#5A534C;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
              >
                {t('mod.flags.dismiss')}
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// A labeled count row with a proportional bar (no charting deps).
function StatBar({ label, value, max, color }) {
  const pct = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0
  return (
    <div style={css('margin-bottom:9px;')}>
      <div style={css('display:flex;justify-content:space-between;margin-bottom:4px;')}>
        <span style={css("font:500 12px 'IBM Plex Sans';color:#5A534C;")}>{label}</span>
        <span style={css("font:600 12px 'IBM Plex Mono';color:#1A1714;")}>{value}</span>
      </div>
      <div style={css('height:7px;border-radius:5px;background:#EFEBE5;overflow:hidden;')}>
        <div style={{ ...css('height:100%;border-radius:5px;'), width: pct + '%', background: color || '#C2272D' }} />
      </div>
    </div>
  )
}

function StatsTab({ view, actions }) {
  const stats = view.moderation.stats
  const { t } = useI18n()
  useEffect(() => { actions.fetchModerationStats() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  if (view.offline) return <NeedsConnection />
  if (!stats) return <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>

  const totals = [
    [t('moderation.statPending'), stats.pending || 0, '#C2272D'],
    [t('moderation.statApproved'), stats.approved || 0, '#15683A'],
    [t('moderation.statRejected'), stats.rejected || 0, '#8A837A'],
  ]
  const bySource = Object.entries(stats.by_source || {})
  const byStatus = Object.entries(stats.by_status || {})
  const maxSource = Math.max(1, ...bySource.map(([, v]) => v))
  const maxStatus = Math.max(1, ...byStatus.map(([, v]) => v))

  return (
    <div style={css('display:flex;flex-direction:column;gap:16px;')}>
      <div style={css('display:flex;gap:9px;')}>
        {totals.map(([label, value, color]) => (
          <div key={label} style={css('flex:1;background:#fff;border:1px solid #EDE9E3;border-radius:13px;padding:13px 12px;text-align:center;')}>
            <div style={{ ...css("font:700 22px 'IBM Plex Sans';"), color }}>{value}</div>
            <div style={css("font:600 9.5px 'IBM Plex Mono';color:#8A837A;letter-spacing:.03em;margin-top:3px;")}>{label}</div>
          </div>
        ))}
      </div>

      {bySource.length > 0 && (
        <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:14px;')}>
          <h2 style={css("margin:0 0 11px;font:600 12px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;")}>{t('moderation.bySource')}</h2>
          {bySource.map(([k, v]) => <StatBar key={k} label={k} value={v} max={maxSource} color="#1F5E96" />)}
        </div>
      )}

      {byStatus.length > 0 && (
        <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:14px;')}>
          <h2 style={css("margin:0 0 11px;font:600 12px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;")}>{t('moderation.byStatus')}</h2>
          {byStatus.map(([k, v]) => <StatBar key={k} label={k} value={v} max={maxStatus} color="#15683A" />)}
        </div>
      )}
    </div>
  )
}

// Session-only operator token gate. Renders a password field until a bearer
// token is entered this session; the token never touches localStorage / IndexedDB
// (the store holds it in a module-level variable wiped on reload or 401).
export function TokenGate({ actions, invalid }) {
  const { t } = useI18n()
  const [value, setValue] = useState('')
  const submit = (e) => {
    e.preventDefault()
    const token = value.trim()
    if (!token) return
    actions.setOperatorToken(token)
  }
  return (
    <form onSubmit={submit} style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:11px;')}>
      <p style={css("margin:0;font:500 13px 'IBM Plex Sans';color:#5A534C;line-height:1.45;")}>{t('moderation.tokenPrompt')}</p>
      {invalid && (
        <div style={css("padding:9px 11px;background:#FCEDEC;border:1px solid #F6DAD7;border-radius:10px;font:500 12px 'IBM Plex Sans';color:#B7242A;")}>
          {t('moderation.tokenInvalid')}
        </div>
      )}
      <input
        type="password"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t('moderation.tokenPlaceholder')}
        style={css("width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:500 13px 'IBM Plex Sans';color:#1A1714;background:#FBFAF8;")}
      />
      <button
        type="submit"
        className="egi-tap"
        style={css("padding:11px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 13px 'IBM Plex Sans';cursor:pointer;")}
      >
        {t('moderation.tokenSubmit')}
      </button>
      <p style={css("margin:0;font:400 11px 'IBM Plex Sans';color:#A9A299;line-height:1.45;")}>{t('moderation.tokenHint')}</p>
    </form>
  )
}

export default function ModerationScreen({ view, actions }) {
  const { t } = useI18n()
  const [tab, setTab] = useState('pending')
  // Session-only token gate. Mirror the store's module-level token flag locally
  // and subscribe to changes (a 401 clears it, flipping us back to the prompt).
  const [tokenSet, setTokenSet] = useState(() => actions.isOperatorTokenSet())
  const [tokenInvalid, setTokenInvalid] = useState(false)
  useEffect(() => {
    const unsub = actions.subscribeOperatorToken(({ set, invalid }) => {
      setTokenSet(set)
      setTokenInvalid(!!invalid)
    })
    return unsub
  }, [actions])

  const tabs = [
    ['pending', t('moderation.tabPending')],
    ['flags', t('mod.flags.tab')],
    ['duplicates', t('moderation.tabDuplicates')],
    ['stats', t('moderation.tabStats')],
  ]

  if (!tokenSet) {
    return (
      <div style={css('padding:14px 18px 28px;')}>
        <h1 style={css("margin:0 0 4px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('moderation.title')}</h1>
        <p style={css("margin:0 0 14px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>{t('moderation.intro')}</p>
        <TokenGate actions={actions} invalid={tokenInvalid} />
      </div>
    )
  }

  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:flex-start;gap:10px;margin-bottom:4px;')}>
        <h1 style={css("flex:1;margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('moderation.title')}</h1>
        <button
          onClick={() => actions.clearOperatorToken()}
          className="egi-tap"
          style={css("flex:none;margin-top:2px;padding:7px 12px;background:#fff;border:1px solid #E2DED8;border-radius:9px;color:#5A534C;font:600 11px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('moderation.tokenClear')}
        </button>
      </div>
      <p style={css("margin:0 0 14px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>{t('moderation.intro')}</p>

      <div style={css('display:flex;gap:6px;margin-bottom:16px;')}>
        {tabs.map(([key, label]) => {
          const on = tab === key
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="egi-tap"
              style={{
                ...css("flex:1;padding:9px;border-radius:10px;cursor:pointer;font:600 12px 'IBM Plex Sans';"),
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

      {tab === 'pending' && <PendingTab view={view} actions={actions} />}
      {tab === 'flags' && <FlagsTab view={view} actions={actions} />}
      {tab === 'duplicates' && <DuplicatesTab view={view} actions={actions} />}
      {tab === 'stats' && <StatsTab view={view} actions={actions} />}

      <div style={css('display:flex;gap:9px;margin-top:20px;padding-top:16px;border-top:1px solid #EFEBE5;')}>
        <button
          onClick={() => actions.setScreen('moderatorOnboarding')}
          className="egi-tap"
          style={css("flex:1;padding:11px;background:#fff;border:1px solid #E2DED8;border-radius:11px;color:#5A534C;font:600 12px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('modOnboard.title')}
        </button>
        <button
          onClick={() => actions.setScreen('orgAdmin')}
          className="egi-tap"
          style={css("flex:1;padding:11px;background:#fff;border:1px solid #E2DED8;border-radius:11px;color:#5A534C;font:600 12px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('orgAdmin.title')}
        </button>
      </div>
    </div>
  )
}

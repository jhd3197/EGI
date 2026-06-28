import { useEffect } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Plan-13 — Operational-intelligence dashboard. Read-only situational awareness
// for commanders: global totals + the selected operation's status breakdown,
// daily intake, active tasks and review queues. Server-backed (the /stats
// endpoints), so it shows a gentle "needs connection" state when offline rather
// than crashing. No charting deps — proportional bars, like the moderation tab.

function NeedsConnection() {
  const { t } = useI18n()
  return (
    <div style={css("padding:24px;text-align:center;background:#FCEDEC;border:1px solid #F6DAD7;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#B7242A;")}>
      {t('dashboard.offline')}
    </div>
  )
}

function StatCard({ value, label, color }) {
  return (
    <div style={css('flex:1;min-width:96px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;padding:13px 12px;text-align:center;')}>
      <div style={{ ...css("font:700 22px 'IBM Plex Sans';"), color: color || '#1A1714' }}>{value}</div>
      <div style={css("font:600 9.5px 'IBM Plex Mono';color:#8A837A;letter-spacing:.03em;margin-top:3px;")}>{label}</div>
    </div>
  )
}

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

function Section({ title, children }) {
  return (
    <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:14px;')}>
      <h2 style={css("margin:0 0 11px;font:600 12px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;")}>{title}</h2>
      {children}
    </div>
  )
}

// Localized status labels (mirror the server SITREP order). Falls back to key.
const STATUS_KEYS = ['missing', 'found', 'safe', 'deceased', 'sighted', 'care']

function StatusBars({ byStatus, t }) {
  const entries = STATUS_KEYS
    .map((k) => [k, (byStatus || {})[k] || 0])
    .filter(([, v]) => v > 0)
  if (entries.length === 0) {
    return <p style={css("margin:0;font:400 12px 'IBM Plex Sans';color:#A9A299;")}>{t('dashboard.noRecords')}</p>
  }
  const max = Math.max(1, ...entries.map(([, v]) => v))
  const color = {
    missing: '#C2272D', found: '#15683A', safe: '#1F7A45',
    deceased: '#5A534C', sighted: '#1F5E96', care: '#9A6A1F',
  }
  return entries.map(([k, v]) => (
    <StatBar key={k} label={t('dashboard.status.' + k)} value={v} max={max} color={color[k]} />
  ))
}

// SAR operations widgets (search-and-rescue): active operations, sectors needing
// a recheck, and recent "found" reports. Additive — reads view.operationsSummary,
// which is derived from the operations list + the open operation detail.
function SarWidgets({ view, t }) {
  const sum = view.operationsSummary || { activeCount: 0, needingAttention: 0, recentFound: 0 }
  return (
    <Section title={t('operations.dashboardTitle')}>
      <div style={css('display:flex;gap:9px;flex-wrap:wrap;')}>
        <StatCard value={sum.activeCount} label={t('operations.activeOps')} color="#1B7A45" />
        <StatCard value={sum.needingAttention} label={t('operations.needingAttention')} color="#C2272D" />
        <StatCard value={sum.recentFound} label={t('operations.recentFound')} color="#15683A" />
      </div>
    </Section>
  )
}

export default function DashboardScreen({ view, actions }) {
  const { t } = useI18n()
  useEffect(() => { actions.fetchDashboard(); actions.fetchOperations() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const d = view.dashboard
  if (view.offline) {
    return (
      <div style={css('padding:14px 18px 28px;')}>
        <h1 style={css("margin:0 0 14px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('dashboard.title')}</h1>
        <NeedsConnection />
      </div>
    )
  }
  if (d.loading && !d.data) {
    return (
      <div style={css('padding:14px 18px 28px;')}>
        <h1 style={css("margin:0 0 14px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('dashboard.title')}</h1>
        <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>
      </div>
    )
  }

  const g = (d.data && d.data.global) || null
  const op = (d.data && d.data.operation) || null
  const intake = op && op.records_per_day ? op.records_per_day.slice(0, 10) : []
  const maxIntake = Math.max(1, ...intake.map((r) => r.count))

  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:flex-start;gap:10px;margin-bottom:4px;')}>
        <h1 style={css("flex:1;margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('dashboard.title')}</h1>
        <button
          onClick={() => actions.fetchDashboard()}
          className="egi-tap"
          style={css("flex:none;margin-top:2px;padding:7px 12px;background:#fff;border:1px solid #E2DED8;border-radius:9px;color:#5A534C;font:600 11px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('dashboard.refresh')}
        </button>
      </div>
      <p style={css("margin:0 0 16px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>{t('dashboard.intro')}</p>

      <div style={css('display:flex;flex-direction:column;gap:16px;')}>
        <SarWidgets view={view} t={t} />
        {g && (
          <>
            <div style={css('display:flex;gap:9px;flex-wrap:wrap;')}>
              <StatCard value={g.persons_total} label={t('dashboard.persons')} />
              <StatCard value={g.operations_total} label={t('dashboard.operations')} />
              <StatCard value={g.moderation_queue} label={t('dashboard.moderationQueue')} color="#C2272D" />
              <StatCard value={g.duplicate_clusters} label={t('dashboard.duplicates')} color="#9A6A1F" />
            </div>
            <Section title={t('dashboard.globalByStatus')}>
              <StatusBars byStatus={g.persons_by_status} t={t} />
            </Section>
          </>
        )}

        {op ? (
          <>
            <Section title={t('dashboard.operationTitle', { name: op.name || op.operation_id })}>
              <div style={css('display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px;')}>
                <StatCard value={op.persons_total} label={t('dashboard.persons')} />
                <StatCard value={op.tasks ? op.tasks.active : 0} label={t('dashboard.activeTasks')} color="#1F5E96" />
                <StatCard value={op.pending_review} label={t('dashboard.pending')} color="#C2272D" />
                <StatCard value={op.geolocated_persons} label={t('dashboard.geolocated')} color="#15683A" />
              </div>
              <StatusBars byStatus={op.persons_by_status} t={t} />
            </Section>

            {intake.length > 0 && (
              <Section title={t('dashboard.recentIntake')}>
                {intake.map((r) => (
                  <StatBar key={r.day} label={r.day} value={r.count} max={maxIntake} color="#1F5E96" />
                ))}
              </Section>
            )}
          </>
        ) : (
          <div style={css("padding:18px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
            {t('dashboard.noOperation')}
          </div>
        )}
      </div>
    </div>
  )
}

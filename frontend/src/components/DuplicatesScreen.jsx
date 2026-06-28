import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import MergeReviewModal from './MergeReviewModal.jsx'

// "Revisar duplicados" — moderator queue for fuzzy-matched person records.
// A merge is always explicit and human-driven (never automatic): the moderator
// picks the record to keep, and the others are soft-merged into it.
export function Cluster({ cluster, actions }) {
  const members = cluster.members || []
  const { t } = useI18n()
  const [canonical, setCanonical] = useState(members[0]?.id)
  return (
    <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:14px;padding:14px;margin-bottom:12px;')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;')}>
        <span style={css("font:600 11px 'IBM Plex Mono';color:#B7242A;letter-spacing:.03em;")}>{t('duplicates.possible')}</span>
        <span style={css("padding:3px 9px;border-radius:7px;background:#FCEDEC;color:#B7242A;font:600 10px 'IBM Plex Mono';")}>{cluster.reason}</span>
      </div>

      <div style={css('display:flex;flex-direction:column;gap:8px;margin-bottom:12px;')}>
        {members.map((m) => {
          const on = canonical === m.id
          return (
            <button
              key={m.id}
              onClick={() => setCanonical(m.id)}
              className="egi-tap"
              style={{
                ...css('display:flex;align-items:center;gap:11px;padding:11px 12px;border-radius:11px;cursor:pointer;text-align:left;'),
                border: on ? '1.5px solid #15683A' : '1px solid #E6E2DC',
                background: on ? '#F1F8F3' : '#fff',
              }}
            >
              <span style={{ ...css('width:15px;height:15px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;'), border: on ? '4px solid #15683A' : '2px solid #C9C2B8' }} />
              <div style={css('flex:1;min-width:0;')}>
                <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{m.name || m.given_name || t('common.noName')}</div>
                <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
                  {[m.cedula, m.age != null ? m.age + ' ' + t('common.years') : null, m.location, m.id].filter(Boolean).join(' · ')}
                </div>
              </div>
              {on && <span style={css("font:600 9.5px 'IBM Plex Mono';color:#15683A;flex:none;")}>{t('duplicates.keep')}</span>}
            </button>
          )
        })}
      </div>

      <div style={css('display:flex;gap:9px;')}>
        <button
          onClick={() => actions.mergeDuplicate(cluster.cluster_id, canonical)}
          className="egi-tap"
          style={css("flex:1;padding:11px;background:#15683A;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('duplicates.merge')}
        </button>
        <button
          onClick={() => actions.rejectDuplicate(cluster.cluster_id)}
          className="egi-tap"
          style={css("flex:none;padding:11px 14px;background:#fff;border:1px solid #E2DED8;border-radius:11px;color:#5A534C;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
        >
          {t('duplicates.notDup')}
        </button>
      </div>
    </div>
  )
}

// Compact row for one persisted merge candidate (plan-27). Highest-confidence
// pairs first; a "Review" button opens the side-by-side MergeReviewModal.
function CandidateRow({ candidate, onReview }) {
  const { t } = useI18n()
  const a = candidate.person_a
  const b = candidate.person_b
  const pct = Math.round((candidate.confidence || 0) * 100)
  const tierColor = candidate.tier === 'exact' ? '#15683A'
    : candidate.tier === 'strong' ? '#1F5E96' : '#9A6A1F'
  const nameOf = (p) => (p && (p.name || [p.given_name, p.family_name].filter(Boolean).join(' ').trim())) || t('common.noName')
  return (
    <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:13px;padding:12px;margin-bottom:10px;display:flex;align-items:center;gap:11px;')}>
      <span style={{ ...css("flex:none;width:42px;text-align:center;padding:5px 0;border-radius:9px;font:700 12px 'IBM Plex Mono';color:#fff;"), background: tierColor }}>{pct}%</span>
      <div style={css('flex:1;min-width:0;')}>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>
          {nameOf(a)} ↔ {nameOf(b)}
        </div>
        <div style={css('display:flex;gap:5px;flex-wrap:wrap;margin-top:5px;')}>
          <span style={{ ...css("padding:2px 7px;border-radius:6px;font:600 8.5px 'IBM Plex Mono';letter-spacing:.04em;text-transform:uppercase;"), background: '#F1EDE7', color: tierColor }}>{candidate.tier}</span>
          {(candidate.reasons || []).map((r) => (
            <span key={r} style={css("padding:2px 7px;border-radius:6px;background:#EAF4ED;color:#15683A;font:600 9px 'IBM Plex Sans';")}>{t('dedup.reason.' + r)}</span>
          ))}
        </div>
      </div>
      <button
        onClick={() => onReview(candidate)}
        className="egi-tap"
        style={css("flex:none;padding:9px 14px;background:#15683A;border:none;border-radius:10px;color:#fff;font:600 12px 'IBM Plex Sans';cursor:pointer;")}
      >
        {t('duplicates.review')}
      </button>
    </div>
  )
}

export default function DuplicatesScreen({ view, actions }) {
  const d = view.duplicates
  const mc = view.mergeCandidates
  const { t } = useI18n()
  const [reviewing, setReviewing] = useState(null)
  useEffect(() => { actions.fetchDuplicates(); actions.fetchMergeCandidates() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('duplicates.title')}</h1>
        <button onClick={actions.fetchDuplicates} className="egi-tap" style={css("border:none;background:transparent;cursor:pointer;font:600 11px 'IBM Plex Mono';color:#C2272D;")}>{t('common.update')}</button>
      </div>
      <p style={css("margin:0 0 16px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>
        {t('duplicates.intro')}
      </p>

      {/* Persisted, scored merge-candidate queue (plan-27) */}
      <div style={css('margin-bottom:22px;')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;')}>
          <h2 style={css("margin:0;font:600 13px 'IBM Plex Mono';color:#6E685E;letter-spacing:.03em;")}>{t('duplicates.candidatesTitle')}</h2>
          <button
            onClick={() => actions.scanMergeCandidates()}
            className="egi-tap"
            style={css("flex:none;padding:7px 12px;background:#fff;border:1px solid #E2DED8;border-radius:9px;color:#5A534C;font:600 11px 'IBM Plex Sans';cursor:pointer;")}
          >
            {t('duplicates.scan')}
          </button>
        </div>
        {mc.loading && <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>}
        {!mc.loading && mc.count === 0 && (
          <div style={css("padding:18px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 12.5px 'IBM Plex Sans';color:#8A837A;")}>
            {t('duplicates.candidatesEmpty')}
          </div>
        )}
        {mc.items.map((c) => (
          <CandidateRow key={c.id} candidate={c} onReview={setReviewing} />
        ))}
      </div>

      {d.loading && <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>}
      {!d.loading && d.count === 0 && (
        <div style={css("padding:24px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
          {t('duplicates.empty')}
        </div>
      )}
      {d.clusters.map((c) => (
        <Cluster key={c.cluster_id} cluster={c} actions={actions} />
      ))}

      {reviewing && (
        <MergeReviewModal candidate={reviewing} actions={actions} onClose={() => setReviewing(null)} />
      )}
    </div>
  )
}

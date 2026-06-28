import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Plan-27 Phase 3 — side-by-side human review of one persisted merge candidate.
// The merge is always explicit and human-driven: the reviewer picks the record
// to keep (canonical), then confirms. Matching fields are highlighted green and
// conflicting fields amber so a moderator can eyeball the decision in seconds.

const FIELDS = [
  'name', 'cedula', 'age', 'sex', 'gender', 'contact',
  'location', 'last_known_location', 'last_seen_date', 'status', 'notes',
]

// Short, readable column labels (language-neutral field names; the data itself
// is what the reviewer compares). Falls back to the raw field key.
const FIELD_LABELS = {
  name: 'Nombre', cedula: 'Cédula', age: 'Edad', sex: 'Sexo', gender: 'Género',
  contact: 'Contacto', location: 'Ubicación', last_known_location: 'Últ. ubicación',
  last_seen_date: 'Últ. visto', status: 'Estado', notes: 'Notas',
}

function displayName(p) {
  if (!p) return ''
  return p.name || [p.given_name, p.family_name].filter(Boolean).join(' ').trim()
}

function fieldValue(p, field) {
  if (!p) return ''
  if (field === 'name') return displayName(p)
  const v = p[field]
  return v == null ? '' : String(v)
}

function norm(v) {
  return String(v == null ? '' : v).trim().toLowerCase()
}

export default function MergeReviewModal({ candidate, actions, onClose }) {
  const { t } = useI18n()
  const a = candidate.person_a
  const b = candidate.person_b
  const [canonical, setCanonical] = useState(a?.id)
  const [busy, setBusy] = useState(false)

  const conflicts = candidate.conflicts || {}
  const pct = Math.round((candidate.confidence || 0) * 100)

  const run = async (decision, canonicalId) => {
    if (busy) return
    setBusy(true)
    try {
      await actions.resolveMergeCandidate(candidate.id, decision, canonicalId)
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const tierColor = candidate.tier === 'exact' ? '#15683A'
    : candidate.tier === 'strong' ? '#1F5E96' : '#9A6A1F'

  // Which fields to render: the curated list, but only rows where at least one
  // record has a value (don't show a wall of empty cells).
  const rows = FIELDS.filter((f) => fieldValue(a, f) || fieldValue(b, f))

  return (
    <div
      onClick={onClose}
      style={css('position:fixed;inset:0;z-index:60;background:rgba(20,16,12,.55);display:flex;align-items:flex-end;justify-content:center;')}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={css('width:100%;max-width:640px;max-height:92vh;overflow:auto;background:#FAF8F4;border-radius:18px 18px 0 0;padding:18px 16px 22px;')}
      >
        <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;')}>
          <h2 style={css("margin:0;font:700 18px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('duplicates.review')}</h2>
          <button
            onClick={onClose}
            className="egi-tap"
            style={css("border:none;background:transparent;cursor:pointer;font:600 12px 'IBM Plex Mono';color:#8A837A;")}
          >
            {t('merge.close')}
          </button>
        </div>

        {/* Confidence + tier + reason chips */}
        <div style={css('display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:14px;')}>
          <span style={{ ...css("padding:4px 11px;border-radius:9px;font:700 13px 'IBM Plex Mono';color:#fff;"), background: tierColor }}>{pct}%</span>
          <span style={{ ...css("padding:4px 10px;border-radius:9px;font:600 10px 'IBM Plex Mono';letter-spacing:.04em;text-transform:uppercase;"), background: '#F1EDE7', color: tierColor }}>{candidate.tier}</span>
          {(candidate.reasons || []).map((r) => (
            <span key={r} style={css("padding:4px 10px;border-radius:9px;background:#EAF4ED;color:#15683A;font:600 10.5px 'IBM Plex Sans';")}>
              {t('dedup.reason.' + r)}
            </span>
          ))}
        </div>

        {/* Two record headers (radio = pick canonical) */}
        <div style={css('display:flex;gap:10px;margin-bottom:6px;')}>
          {[['A', a, t('merge.recordA')], ['B', b, t('merge.recordB')]].map(([slot, p, label]) => {
            const on = canonical === p?.id
            return (
              <button
                key={slot}
                onClick={() => p && setCanonical(p.id)}
                className="egi-tap"
                style={{
                  ...css('flex:1;min-width:0;text-align:left;padding:11px 12px;border-radius:12px;cursor:pointer;'),
                  border: on ? '1.5px solid #15683A' : '1px solid #E6E2DC',
                  background: on ? '#F1F8F3' : '#fff',
                }}
              >
                <div style={css('display:flex;align-items:center;gap:8px;margin-bottom:4px;')}>
                  <span style={{ ...css('width:14px;height:14px;border-radius:50%;flex:none;'), border: on ? '4px solid #15683A' : '2px solid #C9C2B8' }} />
                  <span style={css("font:600 9.5px 'IBM Plex Mono';color:#8A837A;letter-spacing:.04em;")}>{label}</span>
                </div>
                <div style={css("font:600 13.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{displayName(p) || t('common.noName')}</div>
                <div style={css("font:400 10px 'IBM Plex Mono';color:#A9A299;margin-top:3px;")}>
                  {[p?.source, p?.created_at ? String(p.created_at).slice(0, 10) : null].filter(Boolean).join(' · ')}
                </div>
                {on && <div style={css("font:600 9.5px 'IBM Plex Mono';color:#15683A;margin-top:5px;")}>{t('merge.canonical')}</div>}
              </button>
            )
          })}
        </div>

        {/* Side-by-side field comparison */}
        <div style={css('background:#fff;border:1px solid #EDE9E3;border-radius:13px;overflow:hidden;margin:12px 0 14px;')}>
          {rows.map((field, i) => {
            const va = fieldValue(a, field)
            const vb = fieldValue(b, field)
            const conflict = !!conflicts[field]
            const match = va && vb && norm(va) === norm(vb)
            const bg = match ? '#F1F8F3' : conflict ? '#FCF6EA' : i % 2 ? '#FBFAF7' : '#fff'
            const valColor = match ? '#15683A' : conflict ? '#9A6A1F' : '#1A1714'
            return (
              <div key={field} style={{ ...css('display:grid;grid-template-columns:88px 1fr 1fr;gap:8px;padding:8px 11px;border-top:1px solid #F1EDE7;'), background: bg }}>
                <span style={css("font:600 10px 'IBM Plex Mono';color:#8A837A;align-self:center;letter-spacing:.02em;")}>{FIELD_LABELS[field] || field}</span>
                <span style={{ ...css("font:500 12px 'IBM Plex Sans';word-break:break-word;"), color: valColor }}>{va || '—'}</span>
                <span style={{ ...css("font:500 12px 'IBM Plex Sans';word-break:break-word;"), color: valColor }}>{vb || '—'}</span>
              </div>
            )
          })}
        </div>

        {/* Provenance */}
        <div style={css('display:flex;gap:10px;margin-bottom:16px;')}>
          {[a, b].map((p, i) => (
            <div key={i} style={css('flex:1;min-width:0;background:#F6F3EF;border-radius:10px;padding:9px 11px;')}>
              <div style={css("font:600 9px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:3px;")}>{t('merge.provenance')}</div>
              <div style={css("font:500 11px 'IBM Plex Sans';color:#5A534C;word-break:break-word;")}>
                {[p?.source, p?.provenance, p?.id].filter(Boolean).join(' · ') || '—'}
              </div>
            </div>
          ))}
        </div>

        {/* Reviewer actions */}
        <div style={css('display:flex;flex-direction:column;gap:9px;')}>
          <button
            onClick={() => run('merge', canonical)}
            disabled={busy || !canonical}
            className="egi-tap"
            style={{
              ...css("padding:13px;border:none;border-radius:12px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;"),
              background: '#15683A', opacity: busy || !canonical ? 0.6 : 1,
            }}
          >
            {t('merge.confirmMerge')}
          </button>
          <div style={css('display:flex;gap:9px;')}>
            <button
              onClick={() => run('not_match')}
              disabled={busy}
              className="egi-tap"
              style={{
                ...css("flex:1;padding:12px;background:#fff;border:1px solid #F0C9C7;border-radius:12px;color:#B7242A;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"),
                opacity: busy ? 0.6 : 1,
              }}
            >
              {t('merge.notMatch')}
            </button>
            <button
              onClick={() => run('needs_info')}
              disabled={busy}
              className="egi-tap"
              style={{
                ...css("flex:1;padding:12px;background:#fff;border:1px solid #E2DED8;border-radius:12px;color:#5A534C;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"),
                opacity: busy ? 0.6 : 1,
              }}
            >
              {t('merge.needsInfo')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

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

export default function DuplicatesScreen({ view, actions }) {
  const d = view.duplicates
  const { t } = useI18n()
  useEffect(() => { actions.fetchDuplicates() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('duplicates.title')}</h1>
        <button onClick={actions.fetchDuplicates} className="egi-tap" style={css("border:none;background:transparent;cursor:pointer;font:600 11px 'IBM Plex Mono';color:#C2272D;")}>{t('common.update')}</button>
      </div>
      <p style={css("margin:0 0 16px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>
        {t('duplicates.intro')}
      </p>

      {d.loading && <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('common.loading')}</p>}
      {!d.loading && d.count === 0 && (
        <div style={css("padding:24px;text-align:center;background:#F6F3EF;border-radius:14px;font:500 13px 'IBM Plex Sans';color:#8A837A;")}>
          {t('duplicates.empty')}
        </div>
      )}
      {d.clusters.map((c) => (
        <Cluster key={c.cluster_id} cluster={c} actions={actions} />
      ))}
    </div>
  )
}

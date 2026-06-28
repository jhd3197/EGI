import { useEffect } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Facility watcher integration (plan-27.5 Phase 4). A verified hospital/shelter
// watcher (operator mode) picks their facility, subscribes to nearby SAR
// operations, and cross-checks each operation's linked missing persons against
// their patients/guests with one-tap verdicts. Reads only the match-relevant
// person fields the server returns — never the full record.
const VERDICTS = [
  { key: 'person_is_here', bg: '#1B7A45', fg: '#fff' },
  { key: 'person_not_here', bg: '#fff', fg: '#8A837A', border: '1px solid #E6E2DC' },
  { key: 'needs_verification', bg: '#FBEEDA', fg: '#9A6400' },
]

export default function FacilityMatchScreen({ view, actions }) {
  const { t } = useI18n()
  const f = view.facility
  const isOperator = view.operator && view.operatorTokenSet

  // When a facility is chosen, pull the operations near it.
  useEffect(() => {
    if (isOperator && f.id) actions.fetchFacilityOperations(f.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.id, isOperator])

  return (
    <div style={css('padding:12px 16px 28px;')}>
      <div style={css('display:flex;align-items:center;gap:8px;margin:4px 0 4px;')}>
        <span aria-hidden="true" style={css('width:7px;height:7px;border-radius:50%;background:#9A5B14;display:inline-block;')} />
        <span style={css("font:500 10.5px 'IBM Plex Mono';color:#9A5B14;letter-spacing:.1em;")}>{t('facility.eyebrow')}</span>
      </div>
      <h1 style={css("margin:0 0 4px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('facility.title')}</h1>
      <div style={css("font:400 12.5px 'IBM Plex Sans';color:#8A837A;margin-bottom:14px;")}>{t('facility.subtitle')}</div>

      {!isOperator && (
        <div style={css('padding:14px;background:#FCF6EC;border:1px solid #EAD9BC;border-radius:13px;margin-bottom:14px;')}>
          <div style={css("font:600 13px 'IBM Plex Sans';color:#7A5212;")}>{t('facility.needOperator')}</div>
          <div style={css("font:400 11.5px 'IBM Plex Sans';color:#9A7B45;margin-top:3px;")}>{t('facility.needOperatorHint')}</div>
        </div>
      )}

      {/* Facility selector */}
      <label style={css("display:block;font:600 10.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;")}>{t('facility.pickFacility')}</label>
      <select
        value={f.id || ''}
        onChange={(e) => { actions.setFacility(e.target.value || null); if (e.target.value) actions.fetchFacilityOperations(e.target.value) }}
        style={css("width:100%;padding:11px 12px;border:1px solid #E2DED8;border-radius:11px;font:500 13px 'IBM Plex Sans';background:#fff;color:#2A2520;outline:none;cursor:pointer;margin-bottom:16px;")}
      >
        <option value="">{t('facility.pickFacilityNone')}</option>
        {f.facilities.map((fac) => (
          <option key={fac.id} value={fac.id}>{fac.name}{fac.kind ? ` (${fac.kind})` : ''}</option>
        ))}
      </select>

      {isOperator && f.id && (
        <>
          {/* Nearby operations to subscribe to */}
          <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;text-transform:uppercase;margin-bottom:9px;")}>{t('facility.nearbyOps')}</div>
          {f.ops.length === 0 ? (
            <div style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;margin-bottom:14px;")}>{t('facility.noOps')}</div>
          ) : (
            <div style={css('display:flex;flex-direction:column;gap:9px;margin-bottom:18px;')}>
              {f.ops.map((op) => (
                <div key={op.id} style={css('padding:13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
                  <div style={css('display:flex;align-items:center;gap:8px;')}>
                    <div style={css('flex:1;min-width:0;')}>
                      <div style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;")}>{op.name}</div>
                      {op.distance_m != null && <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{Math.round(op.distance_m)} m</div>}
                    </div>
                    {op.watching
                      ? <span style={css("padding:5px 10px;border-radius:8px;font:600 11px 'IBM Plex Sans';background:#E3F2E7;color:#1B7A45;flex:none;")}>{t('facility.watching')}</span>
                      : <button onClick={() => actions.subscribeFacility(op.id)} className="egi-tap" style={css("padding:8px 13px;border-radius:10px;border:1px solid #E6E2DC;background:#fff;color:#5A534C;font:600 11.5px 'IBM Plex Sans';cursor:pointer;flex:none;")}>{t('facility.subscribe')}</button>}
                  </div>
                  <button onClick={() => actions.fetchFacilityCandidates(op.id)} className="egi-tap" style={{ ...css("margin-top:10px;width:100%;padding:10px;border-radius:10px;border:none;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;"), background: f.opId === op.id ? '#1A1714' : '#1F5E96' }}>{t('facility.showMatches')}</button>

                  {/* Candidate persons for this operation */}
                  {f.opId === op.id && (
                    <div style={css('margin-top:12px;display:flex;flex-direction:column;gap:9px;')}>
                      {f.candidates.length === 0 && <div style={css("font:400 12px 'IBM Plex Sans';color:#A9A299;")}>{t('facility.noCandidates')}</div>}
                      {f.candidates.map((p) => (
                        <div key={p.id} style={css('padding:11px;background:#FAF7F2;border:1px solid #EDE9E3;border-radius:11px;')}>
                          <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{p.name || p.id}</div>
                          <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{[p.cedula, p.last_known_location].filter(Boolean).join(' · ')}</div>
                          {p.facility_verdict && <div style={css("font:600 10.5px 'IBM Plex Mono';color:#1B7A45;margin-top:4px;")}>{t('facility.verdict.' + p.facility_verdict)}</div>}
                          <div style={css('display:flex;gap:7px;margin-top:9px;flex-wrap:wrap;')}>
                            {VERDICTS.map((vd) => (
                              <button key={vd.key} onClick={() => actions.fileFacilityMatch(op.id, p.id, vd.key)} className="egi-tap" style={{ ...css("padding:7px 11px;border-radius:9px;font:600 11px 'IBM Plex Sans';cursor:pointer;"), background: vd.bg, color: vd.fg, border: vd.border || 'none' }}>{t('facility.verdict.' + vd.key)}</button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Shelter list (plan-20): each row taps through to the detail card and shows a
// capacity bar, accepting/full badge, trust badge and supply-need chips. Quick
// filters (has space / pets / medical / needs supplies) sit above the list.
export default function SheltersScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()
  const [claimToken, setClaimToken] = useState('')

  // Refresh shelters from the server when the screen mounts (offline → cache).
  useEffect(() => { actions.fetchShelters() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={css('padding:16px 18px 24px;')}>
      <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('shelters.title')}</h1>
      <p style={css("margin:0 0 14px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{t('shelters.subtitle')}</p>

      {/* Quick filters */}
      <div style={css('display:flex;gap:7px;margin-bottom:14px;flex-wrap:wrap;')}>
        {v.shelterFilters.map((f) => (
          <button key={f.key} onClick={f.onClick} aria-pressed={f.active} className="egi-tap" style={{ ...css("padding:7px 13px;border-radius:18px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: f.chipBg, color: f.chipFg, border: `1px solid ${f.chipBorder}` }}>{f.label}</button>
        ))}
      </div>

      <div style={css('display:flex;flex-direction:column;gap:11px;')}>
        {v.institutions.map((i) => (
          <button key={i.id} onClick={i.open} className="egi-tap" style={css('text-align:left;width:100%;padding:14px;background:#fff;border:1px solid #EDE9E3;border-radius:15px;cursor:pointer;')}>
            <div style={css('display:flex;align-items:center;gap:10px;')}>
              <span style={{ ...css("width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex:none;font:600 10px 'IBM Plex Mono';"), background: i.tintBg, color: i.tintFg }}>{i.tag}</span>
              <div style={css('flex:1;min-width:0;')}>
                <div style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{i.name}</div>
                <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{i.address || i.loc}</div>
              </div>
              <span style={{ ...css("padding:3px 9px;border-radius:7px;font:600 10px 'IBM Plex Sans';flex:none;"), background: i.trustBg, color: i.trustFg }}>{i.trustLabel}</span>
            </div>

            {/* Capacity bar */}
            {i.occPct != null && (
              <div style={css('margin-top:11px;')}>
                <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;')}>
                  <span style={css("font:500 11.5px 'IBM Plex Sans';color:#5A534C;")}>{i.capLabel}</span>
                  <span style={{ ...css("padding:3px 9px;border-radius:7px;font:600 10.5px 'IBM Plex Sans';"), background: i.acceptingBg, color: i.acceptingFg }}>{i.acceptingLabel}</span>
                </div>
                <div style={css('height:7px;background:#EEEAE3;border-radius:5px;overflow:hidden;')}>
                  <div style={{ ...css('height:100%;border-radius:5px;'), width: `${i.occPct}%`, background: i.barColor }} />
                </div>
              </div>
            )}

            <div style={css('display:flex;align-items:center;gap:7px;margin-top:10px;flex-wrap:wrap;')}>
              {!i.occPct && <span style={css("padding:4px 10px;border-radius:7px;font:600 11px 'IBM Plex Mono';background:#F2EFEA;color:#5A534C;")}>{i.count}</span>}
              {i.supplyNeeds.slice(0, 3).map((c) => (
                <span key={c} style={css("padding:4px 10px;border-radius:7px;font:600 11px 'IBM Plex Sans';background:#FCEDEC;color:#B7242A;")}>{t('shelterDetail.supply.' + c)}</span>
              ))}
              {i.hasMinors && <span style={css("padding:4px 10px;border-radius:7px;font:600 11px 'IBM Plex Sans';background:#FBEEDA;color:#9A6400;")}>{i.minors || t('shelterDetail.pop.minors')}</span>}
            </div>
          </button>
        ))}
        {v.institutions.length === 0 && (
          <div style={css("padding:24px 0;text-align:center;font:400 13px 'IBM Plex Sans';color:#A9A299;")}>{t('shelters.empty')}</div>
        )}
      </div>

      {/* Operator: claim a shelter with a one-time token (plan-20 §9) */}
      {v.operator && (
        <div style={css('margin-top:16px;padding:14px;border:1px solid #EDE9E3;border-radius:15px;background:#fff;')}>
          <div style={css("font:600 13px 'IBM Plex Sans';color:#2A2520;")}>{t('shelters.claimTitle')}</div>
          <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin:4px 0 10px;")}>{t('shelters.claimHint')}</div>
          <div style={css('display:flex;gap:8px;')}>
            <input value={claimToken} onChange={(e) => setClaimToken(e.target.value)} placeholder={t('shelters.claimPlaceholder')} style={css("flex:1;min-width:0;padding:10px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")} />
            <button onClick={() => { actions.claimShelter(claimToken); setClaimToken('') }} className="egi-tap" style={css("flex:none;padding:10px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelters.claim')}</button>
          </div>
          {v.shelterClaimMsg && (
            <div style={{ ...css("margin-top:8px;font:500 12.5px 'IBM Plex Sans';"), color: v.shelterClaimMsg.ok ? '#15683A' : '#B7242A' }}>
              {v.shelterClaimMsg.ok ? t('shelters.claimOk', { name: v.shelterClaimMsg.name }) : t('shelters.claimFail')}
            </div>
          )}
        </div>
      )}

      <div style={css('margin-top:16px;padding:14px;border:1px dashed #D8D2C9;border-radius:15px;text-align:center;')}>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#2A2520;")}>{t('shelters.areYou')}</div>
        <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin:4px 0 11px;")}>{t('shelters.publish')}</div>
        <button onClick={() => actions.openReport('safe')} className="egi-tap" style={css("padding:10px 18px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelters.register')}</button>
      </div>
    </div>
  )
}

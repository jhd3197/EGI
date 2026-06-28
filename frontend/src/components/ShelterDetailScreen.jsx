import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { openTurnByTurn, getCurrentLocation, distanceMeters, walkingMinutes, cacheRoute } from '../lib/directions.js'
import ShelterAnimalPanel from './ShelterAnimalPanel.jsx'

// Shelter detail card (plan-20 §4–§8): full info, directions, capacity, an
// official update feed, check-in, and an inline operator panel. All fields are
// optional and sourced from the shelter record; missing ones are simply hidden.
function Chip({ label, bg = '#F2EFEA', fg = '#5A534C' }) {
  return <span style={{ ...css("padding:5px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';"), background: bg, color: fg }}>{label}</span>
}

function Section({ title, children }) {
  return (
    <div style={css('margin-top:18px;')}>
      <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:9px;text-transform:uppercase;")}>{title}</div>
      {children}
    </div>
  )
}

export default function ShelterDetailScreen({ view, actions }) {
  const { t } = useI18n()
  const s = view.shelterDetail
  const [note, setNote] = useState('')
  const [origin, setOrigin] = useState(null)
  const [dirMsg, setDirMsg] = useState('')
  const [opMsg, setOpMsg] = useState('')
  if (!s) return null

  const fmtDist = (m) => (m == null ? '' : m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`)

  const handleDirections = async () => {
    // Two modes: from-my-location (default) launches turn-by-turn + estimates a
    // straight-line distance; "from another place" reuses the entered origin.
    let from = origin
    if (!from) { from = await getCurrentLocation(); setOrigin(from) }
    if (s.lat != null && s.lon != null) {
      if (from) {
        const m = distanceMeters(from, { lat: s.lat, lon: s.lon })
        setDirMsg(t('shelterDetail.routeEst', { dist: fmtDist(m), min: walkingMinutes(m) }))
        cacheRoute({ from, to: { lat: s.lat, lon: s.lon }, name: s.name, at: new Date().toISOString() })
      } else {
        setDirMsg(t('shelterDetail.noLocation'))
      }
      openTurnByTurn(s.lat, s.lon, s.name)
    } else {
      setDirMsg(t('shelterDetail.noCoords'))
    }
  }

  const submitCheckin = () => { actions.shelterCheckin(s.id, note); setNote('') }
  const reportWrong = () => {
    actions.postShelterUpdate(s.id, t('shelterDetail.wrongPrefix'), {})
    setOpMsg(t('shelterDetail.thanks'))
    setTimeout(() => setOpMsg(''), 3000)
  }

  const contacts = [
    s.phone && { label: t('shelterDetail.call'), href: `tel:${s.phone}`, bg: '#1A1714', fg: '#fff' },
    s.whatsapp && { label: 'WhatsApp', href: `https://wa.me/${String(s.whatsapp).replace(/[^\d]/g, '')}`, bg: '#E9F4ED', fg: '#15683A' },
    s.email && { label: 'Email', href: `mailto:${s.email}`, bg: '#F2EFEA', fg: '#5A534C' },
  ].filter(Boolean)

  return (
    <div style={css('padding:0 0 28px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;padding:8px 16px 4px;')}>
        <button onClick={actions.closeShelter} className="egi-tap" aria-label={t('common.back')} style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{s.tag}</span>
      </div>

      <div style={css('padding:0 18px;')}>
        <div style={css('display:flex;align-items:flex-start;gap:10px;margin-top:6px;')}>
          <div style={css('flex:1;min-width:0;')}>
            <h1 style={css("margin:0 0 4px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{s.name}</h1>
            <div style={css("font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{s.address || s.loc}{s.hours ? ' · ' + s.hours : ''}</div>
          </div>
          <Chip label={s.trustLabel} bg={s.trustBg} fg={s.trustFg} />
        </div>

        {/* Capacity bar (plan-20 §4) */}
        {s.occPct != null && (
          <div style={css('margin-top:14px;')}>
            <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;')}>
              <span style={css("font:600 12.5px 'IBM Plex Sans';color:#2A2520;")}>{s.capLabel}</span>
              <Chip label={s.acceptingLabel} bg={s.acceptingBg} fg={s.acceptingFg} />
            </div>
            <div style={css('height:9px;background:#EEEAE3;border-radius:6px;overflow:hidden;')}>
              <div style={{ ...css('height:100%;border-radius:6px;'), width: `${s.occPct}%`, background: s.barColor }} />
            </div>
          </div>
        )}

        {/* Contact + directions buttons */}
        <div style={css('display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;')}>
          <button onClick={handleDirections} className="egi-tap" style={css("flex:1;min-width:140px;padding:13px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('shelterDetail.directions')}</button>
          {contacts.map((c, idx) => (
            <a key={idx} href={c.href} target="_blank" rel="noopener noreferrer" className="egi-tap" style={{ ...css("flex:none;padding:13px 15px;border-radius:13px;text-decoration:none;font:600 13px 'IBM Plex Sans';display:flex;align-items:center;border:1px solid #E6E2DC;"), background: c.bg, color: c.fg }}>{c.label}</a>
          ))}
        </div>
        {dirMsg && <div style={css("margin-top:8px;font:400 12px 'IBM Plex Sans';color:#5A534C;")}>{dirMsg}</div>}
        {s.lat != null && s.lon != null && (
          <button onClick={() => actions.openDirections({ lat: s.lat, lon: s.lon, name: s.name })} className="egi-tap"
            style={css("margin-top:8px;border:none;background:transparent;cursor:pointer;font:600 12px 'IBM Plex Sans';color:#C2272D;padding:0;")}>
            {t('directions.planRoute')}
          </button>
        )}
        {/* From-another-place mode */}
        <details style={css('margin-top:8px;')}>
          <summary style={css("font:500 12px 'IBM Plex Sans';color:#8A837A;cursor:pointer;")}>{t('shelterDetail.fromAnother')}</summary>
          <div style={css('display:flex;gap:8px;margin-top:8px;')}>
            <input
              placeholder={t('shelterDetail.originPlaceholder')}
              onChange={(e) => {
                const m = e.target.value.match(/(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)/)
                setOrigin(m ? { lat: parseFloat(m[1]), lon: parseFloat(m[2]) } : null)
              }}
              style={css("flex:1;min-width:0;padding:10px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")}
            />
            <button onClick={handleDirections} className="egi-tap" style={css("flex:none;padding:10px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterDetail.route')}</button>
          </div>
        </details>

        {/* Tabs: Info | Updates | Animals */}
        <div style={css('display:flex;gap:8px;margin-top:18px;border-bottom:1px solid #EDE9E3;')}>
          {[['info', t('shelterDetail.tabInfo')], ['updates', t('shelterDetail.tabUpdates')], ['animals', t('shelterAnimals.tab')]].map(([key, label]) => {
            const on = view.shelterTab === key
            return (
              <button key={key} onClick={() => actions.setShelterTab(key)} className="egi-tap" style={{ ...css("padding:9px 4px;border:none;background:transparent;cursor:pointer;font:600 13px 'IBM Plex Sans';margin-bottom:-1px;"), color: on ? '#1A1714' : '#9A938A', borderBottom: on ? '2px solid #E5343B' : '2px solid transparent' }}>{label}</button>
            )
          })}
        </div>

        {view.shelterTab === 'info' && (
          <>
            {s.services.length > 0 && (
              <Section title={t('shelterDetail.services')}>
                <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                  {s.services.map((c) => <Chip key={c} label={t('shelterDetail.svc.' + c)} bg="#E3F2E7" fg="#1B7A45" />)}
                </div>
              </Section>
            )}
            {s.supplyNeeds.length > 0 && (
              <Section title={t('shelterDetail.needs')}>
                <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                  {s.supplyNeeds.map((c) => <Chip key={c} label={t('shelterDetail.supply.' + c)} bg="#FCEDEC" fg="#B7242A" />)}
                </div>
              </Section>
            )}
            {s.targetPopulations.length > 0 && (
              <Section title={t('shelterDetail.populations')}>
                <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                  {s.targetPopulations.map((c) => <Chip key={c} label={t('shelterDetail.pop.' + c)} bg="#FBEEDA" fg="#9A6400" />)}
                </div>
              </Section>
            )}
            {s.notes && <p style={css("margin:16px 0 0;font:400 13.5px 'IBM Plex Sans';color:#4A443D;line-height:1.5;")}>{s.notes}</p>}

            {/* Check-in + feedback (plan-20 §5/§8) */}
            <Section title={t('shelterDetail.imHere')}>
              <div style={css('display:flex;gap:8px;')}>
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('shelterDetail.notePlaceholder')} style={css("flex:1;min-width:0;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")} />
                <button onClick={submitCheckin} className="egi-tap" style={css("flex:none;padding:11px 16px;background:#1B7A45;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterDetail.checkin')}</button>
              </div>
              <button onClick={reportWrong} className="egi-tap" style={css("margin-top:8px;padding:9px 14px;background:#fff;border:1px solid #E6E2DC;border-radius:11px;color:#8A837A;font:500 12px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterDetail.wrong')}</button>
              {view.shelterCheckedIn && <div style={css("margin-top:8px;font:500 12.5px 'IBM Plex Sans';color:#15683A;")}>{t('shelterDetail.checkedIn', { name: view.shelterCheckedIn.name })}</div>}
              {opMsg && <div style={css("margin-top:8px;font:500 12.5px 'IBM Plex Sans';color:#15683A;")}>{opMsg}</div>}
            </Section>

            {/* Operator capacity panel (plan-20 §4/§7) */}
            {view.operator && <OperatorPanel view={view} actions={actions} s={s} />}
          </>
        )}

        {view.shelterTab === 'updates' && (
          <div style={css('margin-top:16px;')}>
            {view.operator && (
              <div style={css('display:flex;gap:8px;margin-bottom:14px;')}>
                <input id="egi-shelter-update" placeholder={t('shelterDetail.updatePlaceholder')} style={css("flex:1;min-width:0;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")} onKeyDown={(e) => { if (e.key === 'Enter' && e.target.value.trim()) { actions.postShelterUpdate(s.id, e.target.value); e.target.value = '' } }} />
                <button onClick={() => { const el = document.getElementById('egi-shelter-update'); if (el && el.value.trim()) { actions.postShelterUpdate(s.id, el.value); el.value = '' } }} className="egi-tap" style={css("flex:none;padding:11px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterDetail.post')}</button>
              </div>
            )}
            {view.shelterUpdates.length === 0 && !view.shelterUpdatesLoading && (
              <div style={css("padding:24px 0;text-align:center;font:400 13px 'IBM Plex Sans';color:#A9A299;")}>{t('shelterDetail.noUpdates')}</div>
            )}
            <div style={css('display:flex;flex-direction:column;gap:11px;')}>
              {view.shelterUpdates.map((u) => (
                <div key={u.id} style={{ ...css('padding:13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;'), opacity: u._optimistic ? 0.6 : 1 }}>
                  <div style={css('display:flex;align-items:center;gap:8px;margin-bottom:6px;')}>
                    <Chip label={u.roleLabel} bg={u.roleBg} fg={u.roleFg} />
                    <span style={css("font:400 11px 'IBM Plex Mono';color:#A9A299;")}>{u.when}</span>
                  </div>
                  <div style={css("font:500 13px 'IBM Plex Sans';color:#2A2520;line-height:1.4;")}>{u.message}</div>
                  <div style={css("font:400 11px 'IBM Plex Mono';color:#A9A299;margin-top:4px;")}>{u.author}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {view.shelterTab === 'animals' && <ShelterAnimalPanel view={view} actions={actions} />}
      </div>
    </div>
  )
}

// Inline operator panel: verified staff adjust availability + accepting flag in
// real time (plan-20 §4/§7). Sends a capacity PATCH.
function OperatorPanel({ actions, s, view }) {
  const { t } = useI18n()
  const [avail, setAvail] = useState(s.avail != null ? String(s.avail) : '')
  return (
    <Section title={t('shelterDetail.operatorPanel')}>
      <div style={css('padding:13px;background:#F6F3EF;border-radius:13px;')}>
        <div style={css('display:flex;gap:8px;align-items:center;')}>
          <input type="number" value={avail} onChange={(e) => setAvail(e.target.value)} placeholder={t('shelterDetail.available')} style={css("flex:1;min-width:0;padding:10px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")} />
          <button onClick={() => actions.updateShelterCapacity(s.id, { capacity_available: avail === '' ? null : parseInt(avail, 10) })} className="egi-tap" style={css("flex:none;padding:10px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterDetail.save')}</button>
        </div>
        <button onClick={() => actions.updateShelterCapacity(s.id, { accepting_new: s.accepting ? 0 : 1 })} className="egi-tap" style={css("margin-top:8px;padding:9px 14px;width:100%;background:#fff;border:1px solid #E6E2DC;border-radius:11px;color:#2A2520;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{s.accepting ? t('shelterDetail.markFull') : t('shelterDetail.markOpen')}</button>
      </div>
    </Section>
  )
}

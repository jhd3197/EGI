import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import SectorCard from './SectorCard.jsx'
import FieldReportSheet from './FieldReportSheet.jsx'

// SAR operation detail board: status + controls, linked persons, sectors grid,
// task checklist, checked-in volunteers, and recent field reports. Volunteers
// join (public) to unlock sector claim/check-in; operators get create-task,
// status changes, and confirm/dismiss for pending found/needs_help reports.
function Section({ title, children, action }) {
  return (
    <div style={css('margin-top:18px;')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;')}>
        <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;text-transform:uppercase;")}>{title}</div>
        {action}
      </div>
      {children}
    </div>
  )
}

export default function OperationDetailScreen({ view, actions }) {
  const { t } = useI18n()
  const op = view.operationDetail
  const [sheetOpen, setSheetOpen] = useState(false)
  const [taskTitle, setTaskTitle] = useState('')
  const [claimMsg, setClaimMsg] = useState('')
  if (!op) return null

  const opId = op.id
  const stats = op.stats || {}

  const handleClaim = async (sectorId) => {
    const res = await actions.claimSector(sectorId, opId)
    if (res && res.taken) {
      setClaimMsg(t('operations.sectorTaken'))
      setTimeout(() => setClaimMsg(''), 3500)
    }
  }

  const addTask = () => {
    const ttl = taskTitle.trim()
    if (!ttl) return
    actions.addTask(opId, { title: ttl })
    setTaskTitle('')
  }

  const tasks = op.tasks || []
  const volunteers = (op.volunteers || []).filter((vol) => vol.status === 'active')
  const fieldReports = op.field_reports || []

  return (
    <div style={css('padding:0 0 28px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;padding:8px 16px 4px;')}>
        <button onClick={actions.closeOperation} className="egi-tap" aria-label={t('common.back')} style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{t('operations.eyebrow')}</span>
      </div>

      <div style={css('padding:0 18px;')}>
        <div style={css('display:flex;align-items:flex-start;gap:10px;margin-top:6px;')}>
          <div style={css('flex:1;min-width:0;')}>
            <h1 style={css("margin:0 0 4px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{op.name}</h1>
            {op.description && <div style={css("font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{op.description}</div>}
          </div>
          <span style={{ ...css("padding:4px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';flex:none;"), background: op.statusBg, color: op.statusColor }}>{op.statusLabel}</span>
        </div>

        {/* Summary counters */}
        <div style={css('display:flex;gap:9px;margin-top:14px;flex-wrap:wrap;')}>
          <Counter value={stats.sectors_total ?? (op.sectors || []).length} label={t('operations.sectors')} />
          <Counter value={stats.volunteers_active ?? volunteers.length} label={t('operations.volunteersActive')} color="#1F5E96" />
          <Counter value={stats.persons_total ?? (op.persons || []).length} label={t('operations.persons')} />
        </div>

        {/* Join / checkout + file report */}
        <div style={css('display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;')}>
          {!op.joined ? (
            <button onClick={() => actions.joinOperation(opId, {})} className="egi-tap" style={css("flex:1;min-width:140px;padding:13px;background:#1B7A45;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.join')}</button>
          ) : (
            <button onClick={() => actions.checkoutVolunteer(opId)} className="egi-tap" style={css("flex:none;padding:13px 16px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;color:#8A837A;font:600 13px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.checkout')}</button>
          )}
          <button onClick={() => setSheetOpen(true)} className="egi-tap" style={css("flex:1;min-width:140px;padding:13px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('operations.fieldReport')}</button>
        </div>
        {op.joined && <div style={css("margin-top:7px;font:500 11.5px 'IBM Plex Sans';color:#15683A;")}>{t('operations.joined')}</div>}
        {claimMsg && <div style={css("margin-top:7px;font:500 12px 'IBM Plex Sans';color:#B7242A;")}>{claimMsg}</div>}

        {/* Operator: status controls */}
        {view.operator && (
          <div style={css('display:flex;gap:7px;margin-top:12px;flex-wrap:wrap;')}>
            {['active', 'paused', 'closed'].map((st) => (
              <button key={st} onClick={() => actions.setOperationStatus(opId, st)} className="egi-tap" aria-pressed={op.status === st} style={{ ...css("padding:7px 12px;border-radius:10px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: op.status === st ? '#1A1714' : '#fff', color: op.status === st ? '#fff' : '#5A534C', border: `1px solid ${op.status === st ? '#1A1714' : '#E2DED8'}` }}>{t('operations.status.' + st)}</button>
            ))}
          </div>
        )}

        {/* Linked persons */}
        {op.persons && op.persons.length > 0 && (
          <Section title={t('operations.linkedPersons')}>
            <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
              {op.persons.map((p) => (
                <span key={p.id} style={{ ...css("display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';"), background: p.statusBg, color: p.statusFg }}>
                  {p.name || p.id}
                  <span style={css("font:600 10px 'IBM Plex Mono';opacity:.85;")}>{p.statusLabel}</span>
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Sectors grid */}
        <Section title={t('operations.sectorsTitle')}>
          {op.sectors && op.sectors.length > 0 ? (
            <div style={css('display:flex;flex-direction:column;gap:9px;')}>
              {op.sectors.map((s) => (
                <SectorCard
                  key={s.id}
                  sector={s}
                  joined={op.joined}
                  onClaim={() => handleClaim(s.id)}
                  onRelease={() => actions.releaseSector(s.id, opId)}
                  onCheckin={() => actions.checkinSector(s.id, opId)}
                  onClear={() => actions.setSectorStatus(s.id, opId, 'cleared')}
                  onRecheck={() => actions.setSectorStatus(s.id, opId, 'needs_recheck')}
                />
              ))}
            </div>
          ) : (
            <div style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('operations.noSectors')}</div>
          )}
        </Section>

        {/* Task checklist */}
        <Section title={t('operations.tasks')}>
          <div style={css('display:flex;flex-direction:column;gap:8px;')}>
            {tasks.map((task) => (
              <label key={task.id} style={css('display:flex;align-items:center;gap:10px;padding:11px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:12px;cursor:pointer;')}>
                <input type="checkbox" checked={!!task.done} onChange={(e) => actions.toggleTask(task.id, opId, e.target.checked)} style={css('width:18px;height:18px;flex:none;accent-color:#1B7A45;cursor:pointer;')} />
                <span style={{ ...css("flex:1;font:500 13px 'IBM Plex Sans';"), color: task.done ? '#A9A299' : '#2A2520', textDecoration: task.done ? 'line-through' : 'none' }}>{task.title}</span>
                <span style={css("font:600 9.5px 'IBM Plex Mono';color:#A9A299;flex:none;")}>{t('operations.kind.' + task.kind, {})}</span>
              </label>
            ))}
            {tasks.length === 0 && <div style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('operations.noTasks')}</div>}
          </div>
          <div style={css('display:flex;gap:8px;margin-top:10px;')}>
            <input value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') addTask() }} placeholder={t('operations.taskPlaceholder')} style={css("flex:1;min-width:0;padding:10px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';background:#fff;outline:none;")} />
            <button onClick={addTask} className="egi-tap" style={css("flex:none;padding:10px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.addTask')}</button>
          </div>
        </Section>

        {/* Volunteers checked in */}
        <Section title={t('operations.volunteersTitle')}>
          {volunteers.length > 0 ? (
            <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
              {volunteers.map((vol) => (
                <span key={vol.id} style={css("padding:5px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';background:#E4EEF6;color:#1F5E96;")}>{vol.alias || t('operations.anonVolunteer')}</span>
              ))}
            </div>
          ) : (
            <div style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('operations.noVolunteers')}</div>
          )}
        </Section>

        {/* Recent field reports */}
        <Section title={t('operations.recentReports')}>
          {fieldReports.length > 0 ? (
            <div style={css('display:flex;flex-direction:column;gap:9px;')}>
              {fieldReports.slice(0, 12).map((r) => (
                <div key={r.id} style={css('padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;')}>
                  <div style={css('display:flex;align-items:center;gap:8px;margin-bottom:5px;')}>
                    <span style={css("padding:3px 9px;border-radius:7px;font:600 10.5px 'IBM Plex Sans';background:#F2EFEA;color:#5A534C;")}>{t('operations.frType.' + r.type, {})}</span>
                    {r.applied ? <span style={css("font:600 10px 'IBM Plex Mono';color:#15683A;")}>{t('operations.frApplied')}</span> : (r.reviewed ? null : <span style={css("font:600 10px 'IBM Plex Mono';color:#9A6400;")}>{t('operations.frPending')}</span>)}
                    <span style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-left:auto;")}>{String(r.created_at || '').replace('T', ' ').slice(0, 16)}</span>
                  </div>
                  {r.note && <div style={css("font:500 12.5px 'IBM Plex Sans';color:#2A2520;line-height:1.4;")}>{r.note}</div>}
                  {r.reporter_alias && <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;margin-top:4px;")}>{r.reporter_alias}</div>}

                  {/* Operator: confirm/dismiss pending found/needs_help reports */}
                  {view.operator && !r.reviewed && (r.type === 'found' || r.type === 'needs_help') && (
                    <div style={css('display:flex;gap:8px;margin-top:9px;')}>
                      <button onClick={() => actions.resolveFieldReport(r.id, opId, { confirmed: true, person_status: r.type === 'found' ? 'found' : null })} className="egi-tap" style={css("padding:8px 13px;background:#1B7A45;border:none;border-radius:10px;color:#fff;font:600 11.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.confirm')}</button>
                      <button onClick={() => actions.resolveFieldReport(r.id, opId, { confirmed: false })} className="egi-tap" style={css("padding:8px 13px;background:#fff;border:1px solid #E6E2DC;border-radius:10px;color:#8A837A;font:600 11.5px 'IBM Plex Sans';cursor:pointer;")}>{t('operations.dismiss')}</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('operations.noReports')}</div>
          )}
        </Section>
      </div>

      {sheetOpen && <FieldReportSheet view={view} op={op} actions={actions} onClose={() => setSheetOpen(false)} />}
    </div>
  )
}

function Counter({ value, label, color }) {
  return (
    <div style={css('flex:1;min-width:90px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;padding:12px;text-align:center;')}>
      <div style={{ ...css("font:700 21px 'IBM Plex Sans';"), color: color || '#1A1714' }}>{value ?? 0}</div>
      <div style={css("font:600 9.5px 'IBM Plex Mono';color:#8A837A;letter-spacing:.03em;margin-top:3px;")}>{label}</div>
    </div>
  )
}

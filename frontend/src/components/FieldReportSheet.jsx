import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Bottom-sheet form to file a SAR field report (sighting / cleared / needs_help
// / found / building inspection). Mirrors ReportSheet's sheet chrome. Optional
// sector + linked person. Submits via actions.fileFieldReport (offline-queue
// aware) then closes.
const TYPES = ['sighting', 'cleared', 'needs_help', 'found', 'building_inspection']

// Building-inspection checklist (plan-27.5 Phase 5). Boolean checks plus a
// three-way safety level. An unsafe / occupied / blocked / follow-up result
// flags the sector for re-check server-side.
const INSPECT_CHECKS = [
  'visually_searched', 'occupants_present', 'structural_damage',
  'access_blocked', 'utilities_water', 'utilities_power', 'utilities_gas',
  'needs_followup',
]
const SAFETY_LEVELS = ['safe', 'unsafe', 'unknown']

export default function FieldReportSheet({ view, op, actions, onClose }) {
  const v = view
  const { t } = useI18n()
  const [type, setType] = useState('sighting')
  const [sectorId, setSectorId] = useState('')
  const [personId, setPersonId] = useState('')
  const [note, setNote] = useState('')
  const [checks, setChecks] = useState({})
  const [safety, setSafety] = useState('unknown')

  const sectors = (op && op.sectors) || []
  const persons = (op && op.persons) || []
  const isInspection = type === 'building_inspection'

  const toggleCheck = (k) => setChecks((c) => ({ ...c, [k]: !c[k] }))

  const submit = () => {
    const checklist = isInspection
      ? { ...checks, safety_level: safety }
      : null
    actions.fileFieldReport(op.id, {
      type,
      sector_id: sectorId || null,
      person_id: personId || null,
      note,
      checklist,
    })
    onClose()
  }

  const selectStyle = css("width:100%;margin-top:6px;padding:11px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13.5px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")
  const labelStyle = css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")

  return (
    <div style={{ ...css('position:absolute;inset:0;z-index:50;background:rgba(20,14,8,.38);backdrop-filter:blur(2px);display:flex;flex-direction:column;align-items:center;'), justifyContent: v.sheetJustify, padding: v.sheetPad }}>
      <div role="dialog" aria-modal="true" aria-label={t('operations.fieldReport')} style={{ ...css('background:#FBFAF8;width:100%;display:flex;flex-direction:column;animation:egiUp .3s cubic-bezier(.2,.85,.25,1);overflow:hidden;box-shadow:0 30px 70px -20px rgba(20,14,8,.5);'), borderRadius: v.sheetRadius, maxWidth: v.sheetMaxW, maxHeight: v.sheetMaxH }}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;padding:16px 18px 12px;border-bottom:1px solid #EDE9E3;')}>
          <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;")}>{t('operations.fieldReport')}</div>
          <button onClick={onClose} className="egi-tap" aria-label={t('common.close')} style={css('width:32px;height:32px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;position:relative;flex:none;')}>
            <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(45deg);')} />
            <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(-45deg);')} />
          </button>
        </div>

        <div className="egi-scroll" style={css('flex:1;overflow-y:auto;padding:16px 18px 8px;display:flex;flex-direction:column;gap:14px;')}>
          <div>
            <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:9px;")}>{t('operations.reportType')}</div>
            <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
              {TYPES.map((k) => {
                const on = type === k
                return (
                  <button key={k} onClick={() => setType(k)} className="egi-tap" aria-pressed={on} style={{ ...css("padding:8px 13px;border-radius:18px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: on ? '#1A1714' : '#fff', color: on ? '#fff' : '#5A534C', border: `1px solid ${on ? '#1A1714' : '#E2DED8'}` }}>{t('operations.frType.' + k)}</button>
                )
              })}
            </div>
          </div>

          {sectors.length > 0 && (
            <div>
              <label style={labelStyle}>{t('operations.sectorOptional')}</label>
              <select value={sectorId} onChange={(e) => setSectorId(e.target.value)} style={selectStyle}>
                <option value="">{t('operations.noSector')}</option>
                {sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}

          {persons.length > 0 && (
            <div>
              <label style={labelStyle}>{t('operations.personOptional')}</label>
              <select value={personId} onChange={(e) => setPersonId(e.target.value)} style={selectStyle}>
                <option value="">{t('operations.noPerson')}</option>
                {persons.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
              </select>
            </div>
          )}

          {isInspection && (
            <div>
              <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:9px;")}>{t('inspect.checklist')}</div>
              <div style={css('display:flex;flex-direction:column;gap:7px;')}>
                {INSPECT_CHECKS.map((k) => (
                  <label key={k} style={css('display:flex;align-items:center;gap:10px;padding:9px 11px;background:#fff;border:1px solid #EDE9E3;border-radius:10px;cursor:pointer;')}>
                    <input type="checkbox" checked={!!checks[k]} onChange={() => toggleCheck(k)} style={css('width:17px;height:17px;flex:none;accent-color:#1F5E96;cursor:pointer;')} />
                    <span style={css("flex:1;font:500 12.5px 'IBM Plex Sans';color:#2A2520;")}>{t('inspect.check.' + k)}</span>
                  </label>
                ))}
              </div>
              <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin:11px 0 7px;")}>{t('inspect.safety')}</div>
              <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                {SAFETY_LEVELS.map((lv) => {
                  const on = safety === lv
                  const color = lv === 'safe' ? '#1B7A45' : lv === 'unsafe' ? '#C2272D' : '#9A6400'
                  return (
                    <button key={lv} onClick={() => setSafety(lv)} className="egi-tap" aria-pressed={on} style={{ ...css("padding:8px 14px;border-radius:18px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: on ? color : '#fff', color: on ? '#fff' : color, border: `1px solid ${on ? color : '#E2DED8'}` }}>{t('inspect.safety.' + lv)}</button>
                  )
                })}
              </div>
            </div>
          )}

          <div>
            <label style={labelStyle}>{t('operations.note')}</label>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('operations.notePlaceholder')} rows={3} style={css("width:100%;margin-top:6px;padding:12px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13.5px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;resize:none;")} />
          </div>
        </div>

        <div style={css('flex:none;display:flex;gap:10px;padding:12px 18px 22px;border-top:1px solid #EDE9E3;')}>
          <button onClick={onClose} className="egi-tap" style={css("flex:none;padding:14px 20px;background:#fff;border:1px solid #E2DED8;border-radius:13px;color:#1A1714;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>{t('common.cancel')}</button>
          <button onClick={submit} className="egi-tap" style={css("flex:1;padding:14px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('operations.sendReport')}</button>
        </div>
      </div>
    </div>
  )
}

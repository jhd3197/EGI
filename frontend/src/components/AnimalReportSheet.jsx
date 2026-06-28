import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Animal report sheet (plan-28): a single-screen form modeled on ReportSheet so
// a missing-dog report files in well under a minute. Form state is local; on
// submit it hands the draft to the store's submitAnimalReport (public POST,
// offline-queue aware) and shows a confirmation. Mounted by AppShell while
// view.animalReportOpen is true.
const inputStyle = css("width:100%;margin-top:6px;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 14px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")
const labelStyle = css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")

function Field({ label, value, onChange, placeholder, flex, type }) {
  return (
    <div style={flex ? { flex } : undefined}>
      <label style={labelStyle}>{label}</label>
      <input type={type || 'text'} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={label} style={inputStyle} />
    </div>
  )
}

const SPECIES = ['dog', 'cat', 'bird', 'rabbit', 'other']
const SPECIES_EMOJI = { dog: '🐕', cat: '🐈', bird: '🐦', rabbit: '🐇', other: '🐾' }
const STATUSES = ['missing', 'seen', 'found']

export default function AnimalReportSheet({ view, actions }) {
  const v = view
  const { t } = useI18n()
  const [d, setD] = useState({ species: 'dog', status: 'missing' })
  const [done, setDone] = useState(false)
  const set = (field) => (value) => setD((prev) => ({ ...prev, [field]: value }))

  const submit = async () => {
    await actions.submitAnimalReport(d)
    setDone(true)
  }
  const close = () => { setDone(false); setD({ species: 'dog', status: 'missing' }); actions.closeAnimalReport() }

  return (
    <div style={{ ...css('position:absolute;inset:0;z-index:50;background:rgba(20,14,8,.38);backdrop-filter:blur(2px);display:flex;flex-direction:column;align-items:center;'), justifyContent: v.sheetJustify, padding: v.sheetPad }}>
      <div role="dialog" aria-modal="true" aria-label={t('report.animal.title')} style={{ ...css('background:#FBFAF8;width:100%;display:flex;flex-direction:column;animation:egiUp .3s cubic-bezier(.2,.85,.25,1);overflow:hidden;box-shadow:0 30px 70px -20px rgba(20,14,8,.5);'), borderRadius: v.sheetRadius, maxWidth: v.sheetMaxW, maxHeight: v.sheetMaxH }}>

        {done ? (
          <div role="status" style={css('padding:34px 24px 30px;display:flex;flex-direction:column;align-items:center;text-align:center;animation:egiFade .35s ease;')}>
            <div aria-hidden="true" style={css('width:66px;height:66px;border-radius:50%;background:#E9F4ED;display:flex;align-items:center;justify-content:center;margin-bottom:18px;font-size:32px;')}>{SPECIES_EMOJI[d.species] || '🐾'}</div>
            <h2 style={css("margin:0 0 6px;font:700 20px 'IBM Plex Sans';color:#1A1714;")}>{t('report.animal.savedTitle')}</h2>
            <p style={css("margin:0 0 20px;font:400 13.5px 'IBM Plex Sans';color:#6A645C;line-height:1.5;max-width:280px;")}>{t('report.animal.savedBody')}</p>
            <button onClick={close} className="egi-tap" style={css("width:100%;padding:14px;background:#1A1714;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>{t('common.done')}</button>
          </div>
        ) : (
          <>
            <div style={css('display:flex;align-items:center;justify-content:space-between;padding:16px 18px 12px;border-bottom:1px solid #EDE9E3;')}>
              <div>
                <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;")}>{t('report.animal.title')}</div>
                <div style={css("font:400 11px 'IBM Plex Sans';color:#A9A299;margin-top:2px;")}>{t('report.animal.subtitle')}</div>
              </div>
              <button onClick={close} className="egi-tap" aria-label={t('common.close')} style={css('width:32px;height:32px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;position:relative;flex:none;')}>
                <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(45deg);')} />
                <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(-45deg);')} />
              </button>
            </div>

            <div className="egi-scroll" style={css('flex:1;overflow-y:auto;padding:16px 18px 8px;display:flex;flex-direction:column;gap:14px;')}>
              {/* Status */}
              <div>
                <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:7px;")}>{t('report.animal.status')}</div>
                <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                  {STATUSES.map((s) => {
                    const on = d.status === s
                    return (
                      <button key={s} onClick={() => set('status')(s)} className="egi-tap" style={{ ...css("padding:8px 14px;border-radius:18px;font:600 12px 'IBM Plex Sans';cursor:pointer;"), background: on ? '#1A1714' : '#fff', color: on ? '#fff' : '#5A534C', border: `1px solid ${on ? '#1A1714' : '#E2DED8'}` }}>{t('animals.status.' + s)}</button>
                    )
                  })}
                </div>
              </div>

              {/* Species */}
              <div>
                <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:7px;")}>{t('report.animal.species')}</div>
                <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
                  {SPECIES.map((s) => {
                    const on = d.species === s
                    return (
                      <button key={s} onClick={() => set('species')(s)} className="egi-tap" style={{ ...css("display:flex;align-items:center;gap:6px;padding:8px 13px;border-radius:18px;font:600 12px 'IBM Plex Sans';cursor:pointer;"), background: on ? '#FFF4F3' : '#fff', color: on ? '#B7242A' : '#5A534C', border: `1.5px solid ${on ? '#E5343B' : '#E2DED8'}` }}>
                        <span aria-hidden="true">{SPECIES_EMOJI[s]}</span>{t('animals.species.' + s)}
                      </button>
                    )
                  })}
                </div>
              </div>

              <Field label={t('report.animal.name')} value={d.name || ''} onChange={set('name')} placeholder={t('report.animal.namePh')} />
              <div style={css('display:flex;gap:10px;')}>
                <Field label={t('report.animal.breed')} value={d.breed || ''} onChange={set('breed')} placeholder={t('report.animal.breedPh')} flex="1.3" />
                <Field label={t('report.animal.sex')} value={d.sex || ''} onChange={set('sex')} placeholder={t('report.animal.sexPh')} flex="1" />
              </div>
              <div style={css('display:flex;gap:10px;')}>
                <Field label={t('report.animal.size')} value={d.size || ''} onChange={set('size')} placeholder={t('report.animal.sizePh')} flex="1" />
                <Field label={t('report.animal.color')} value={d.color || ''} onChange={set('color')} placeholder={t('report.animal.colorPh')} flex="1.3" />
              </div>
              <Field label={t('report.animal.marks')} value={d.distinguishingMarks || ''} onChange={set('distinguishingMarks')} placeholder={t('report.animal.marksPh')} />
              <div style={css('display:flex;gap:10px;')}>
                <Field label={t('report.animal.lastSeenLocation')} value={d.lastSeenLocation || ''} onChange={set('lastSeenLocation')} placeholder={t('report.animal.lastSeenLocationPh')} flex="1.4" />
                <Field label={t('report.animal.lastSeenAt')} value={d.lastSeenAt || ''} onChange={set('lastSeenAt')} placeholder={t('report.animal.lastSeenAtPh')} flex="1" />
              </div>
              <Field label={t('report.animal.microchip')} value={d.microchip || ''} onChange={set('microchip')} placeholder={t('report.animal.microchipPh')} />
              <Field label={t('report.animal.photoUrl')} value={d.photoUrl || ''} onChange={set('photoUrl')} placeholder={t('report.animal.photoUrlPh')} />
              <div style={css('display:flex;gap:10px;')}>
                <Field label={t('report.animal.ownerName')} value={d.ownerName || ''} onChange={set('ownerName')} placeholder={t('report.animal.ownerNamePh')} flex="1" />
                <Field label={t('report.animal.ownerContact')} value={d.ownerContact || ''} onChange={set('ownerContact')} placeholder={t('report.animal.ownerContactPh')} flex="1" />
              </div>
              <div>
                <label style={labelStyle}>{t('report.animal.notes')}</label>
                <textarea value={d.notes || ''} onChange={(e) => set('notes')(e.target.value)} placeholder={t('report.animal.notesPh')} aria-label={t('report.animal.notes')} rows={2} style={css("width:100%;margin-top:6px;padding:11px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13.5px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;resize:none;")} />
              </div>
            </div>

            <div style={css('flex:none;display:flex;gap:10px;padding:12px 18px 22px;border-top:1px solid #EDE9E3;')}>
              <button onClick={submit} className="egi-tap" style={css("flex:1;padding:14px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('report.animal.submit')}</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

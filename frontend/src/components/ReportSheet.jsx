import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import ImageSlot from './ImageSlot.jsx'

const inputStyle = css("width:100%;margin-top:6px;padding:12px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 14px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")
const labelStyle = css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")

function Field({ label, field, value, actions, placeholder, flex }) {
  return (
    <div style={flex ? { flex } : undefined}>
      <label style={labelStyle}>{label}</label>
      <input value={value || ''} onChange={(e) => actions.updateDraft(field, e.target.value)} placeholder={placeholder} aria-label={label} style={inputStyle} />
    </div>
  )
}

function TextArea({ label, field, value, actions, placeholder }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <textarea value={value || ''} onChange={(e) => actions.updateDraft(field, e.target.value)} placeholder={placeholder} aria-label={label} rows={3} style={css("width:100%;margin-top:6px;padding:12px 13px;border:1px solid #E2DED8;border-radius:11px;font:400 13.5px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;resize:none;")} />
    </div>
  )
}

export default function ReportSheet({ view, actions }) {
  const v = view
  const d = v.reportDraft
  const { t } = useI18n()
  return (
    <div style={{ ...css('position:absolute;inset:0;z-index:50;background:rgba(20,14,8,.38);backdrop-filter:blur(2px);display:flex;flex-direction:column;align-items:center;'), justifyContent: v.sheetJustify, padding: v.sheetPad }}>
      <div role="dialog" aria-modal="true" aria-label={t('nav.report')} style={{ ...css('background:#FBFAF8;width:100%;display:flex;flex-direction:column;animation:egiUp .3s cubic-bezier(.2,.85,.25,1);overflow:hidden;box-shadow:0 30px 70px -20px rgba(20,14,8,.5);'), borderRadius: v.sheetRadius, maxWidth: v.sheetMaxW, maxHeight: v.sheetMaxH }}>

        {v.reportDone ? (
          <div role="status" style={css('padding:34px 24px 30px;display:flex;flex-direction:column;align-items:center;text-align:center;animation:egiFade .35s ease;')}>
            <div aria-hidden="true" style={css('width:66px;height:66px;border-radius:50%;background:#E9F4ED;display:flex;align-items:center;justify-content:center;margin-bottom:18px;')}>
              <span style={css('width:30px;height:30px;position:relative;')}>
                <span style={css('position:absolute;left:3px;top:16px;width:9px;height:3.4px;background:#1B7A45;border-radius:2px;transform:rotate(45deg);transform-origin:left;')} />
                <span style={css('position:absolute;left:9px;top:21px;width:18px;height:3.4px;background:#1B7A45;border-radius:2px;transform:rotate(-52deg);transform-origin:left;')} />
              </span>
            </div>
            <h2 style={css("margin:0 0 6px;font:700 20px 'IBM Plex Sans';color:#1A1714;")}>{t('report.savedTitle')}</h2>
            <p style={css("margin:0 0 6px;font:400 13.5px 'IBM Plex Sans';color:#6A645C;line-height:1.5;max-width:280px;")}>{t('report.savedBody')}</p>
            <p style={css("margin:0 0 18px;font:400 11px 'IBM Plex Mono';color:#A9A299;")}>{t('report.savedSub')}</p>
            <div style={css("padding:9px 16px;background:#F2EFEA;border-radius:10px;font:600 13px 'IBM Plex Mono';color:#5A534C;margin-bottom:20px;")}>{t('report.casePrefix')} {v.savedCase}</div>
            <button onClick={actions.closeReport} className="egi-tap" style={css("width:100%;padding:14px;background:#1A1714;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>{t('common.done')}</button>
          </div>
        ) : (
          <>
            <div style={css('display:flex;align-items:center;justify-content:space-between;padding:16px 18px 12px;border-bottom:1px solid #EDE9E3;')}>
              <div>
                <div style={css("font:600 15px 'IBM Plex Sans';color:#1A1714;")}>{v.stepTitle}</div>
                <div style={css("font:500 10px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{t('report.stepCount', { n: v.stepNum })}</div>
              </div>
              <button onClick={actions.closeReport} className="egi-tap" aria-label={t('common.close')} style={css('width:32px;height:32px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;position:relative;flex:none;')}>
                <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(45deg);')} />
                <span aria-hidden="true" style={css('position:absolute;left:50%;top:50%;width:13px;height:2px;background:#6A645C;transform:translate(-50%,-50%) rotate(-45deg);')} />
              </button>
            </div>

            <div style={css('display:flex;gap:5px;padding:12px 18px 4px;')}>
              {v.stepBars.map((b, idx) => (
                <span key={idx} style={{ ...css('flex:1;height:4px;border-radius:2px;'), background: b.bg }} />
              ))}
            </div>

            <div className="egi-scroll" style={css('flex:1;overflow-y:auto;padding:16px 18px 8px;min-height:240px;')}>
              {v.isStep0 && (
                <div style={css('animation:egiFade .25s ease;')}>
                  <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:9px;")}>{t('report.typeSectionTitle')}</div>
                  <div style={css('display:flex;flex-direction:column;gap:8px;margin-bottom:18px;')}>
                    {v.typeOptions.map((t) => (
                      <button key={t.key} onClick={t.onClick} className="egi-tap" style={{ ...css('display:flex;align-items:center;gap:11px;padding:13px;border-radius:13px;cursor:pointer;text-align:left;'), background: t.bg, border: `1.5px solid ${t.border}` }}>
                        <span aria-hidden="true" style={{ ...css('width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex:none;'), border: `2px solid ${t.ring}` }}>
                          <span style={{ ...css('width:10px;height:10px;border-radius:50%;'), background: t.dot }} />
                        </span>
                        <div>
                          <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t.es}</div>
                          <div style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;")}>{t.en}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:9px;")}>{t('report.photoSectionTitle')}</div>
                  <ImageSlot height={180} radius={16} placeholder={t('report.photoPlaceholder')} />
                </div>
              )}

              {v.isStep1 && (
                <div style={css('display:flex;flex-direction:column;gap:14px;animation:egiFade .25s ease;')}>
                  <Field label={t('report.f.name')} field="name" value={d.name} actions={actions} placeholder={t('report.f.namePh')} />
                  <Field label={t('report.f.cedula')} field="cedula" value={d.cedula} actions={actions} placeholder={t('report.f.cedulaPh')} />
                  <div style={css('display:flex;gap:10px;')}>
                    <Field label={t('report.f.age')} field="age" value={d.age} actions={actions} placeholder={t('report.f.agePh')} flex="1" />
                    <Field label={t('report.f.gender')} field="gender" value={d.gender} actions={actions} placeholder={t('report.f.genderPh')} flex="1.4" />
                  </div>
                  <TextArea label={t('report.f.clothes')} field="clothes" value={d.clothes} actions={actions} placeholder={t('report.f.clothesPh')} />
                </div>
              )}

              {v.isStep2 && (
                <div style={css('display:flex;flex-direction:column;gap:14px;animation:egiFade .25s ease;')}>
                  <Field label={t('report.f.location')} field="location" value={d.location} actions={actions} placeholder={t('report.f.locationPh')} />
                  <Field label={t('report.f.date')} field="lastSeenDate" value={d.lastSeenDate} actions={actions} placeholder={t('report.f.datePh')} />
                  <TextArea label={t('report.f.notes')} field="notes" value={d.notes} actions={actions} placeholder={t('report.f.notesPh')} />
                </div>
              )}

              {v.isStep3 && (
                <div style={css('display:flex;flex-direction:column;gap:14px;animation:egiFade .25s ease;')}>
                  <div style={css('display:flex;align-items:center;gap:8px;padding:11px 13px;background:#F6F3EF;border-radius:11px;')}>
                    <span style={css('width:7px;height:7px;border-radius:50%;background:#1F5E96;flex:none;')} />
                    <span style={css("font:500 11px 'IBM Plex Sans';color:#5A534C;")}>{t('report.contactNote')}</span>
                  </div>
                  <div style={css('display:flex;gap:10px;')}>
                    <Field label={t('report.f.reporterName')} field="reporterName" value={d.reporterName} actions={actions} placeholder={t('report.f.reporterNamePh')} flex="1.3" />
                    <Field label={t('report.f.relation')} field="relation" value={d.relation} actions={actions} placeholder={t('report.f.relationPh')} flex="1" />
                  </div>
                  <Field label={t('report.f.contact')} field="contact" value={d.contact} actions={actions} placeholder={t('report.f.contactPh')} />
                  <Field label={t('report.f.country')} field="country" value={d.country} actions={actions} placeholder={t('report.f.countryPh')} />
                </div>
              )}

              {v.isStep4 && (
                <div style={css('animation:egiFade .25s ease;')}>
                  <div style={css('display:flex;gap:13px;align-items:center;padding:13px;background:#fff;border:1px solid #EDE9E3;border-radius:13px;margin-bottom:13px;')}>
                    <span style={css('width:50px;height:50px;border-radius:11px;flex:none;background-image:repeating-linear-gradient(45deg,#EFEDE9,#EFEDE9 5px,#E4E1DB 5px,#E4E1DB 10px);')} />
                    <div>
                      <div style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;")}>{v.reviewName}</div>
                      <div style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{v.reviewAgeLocation}</div>
                    </div>
                  </div>
                  <div style={css('display:flex;flex-direction:column;gap:1px;background:#EDE9E3;border-radius:13px;overflow:hidden;border:1px solid #EDE9E3;')}>
                    <div style={css('display:flex;justify-content:space-between;padding:11px 13px;background:#fff;')}><span style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;")}>{t('report.review.type')}</span><span style={css("font:500 12px 'IBM Plex Sans';color:#1A1714;")}>{v.reportTypeLabel}</span></div>
                    <div style={css('display:flex;justify-content:space-between;padding:11px 13px;background:#fff;')}><span style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;")}>{t('report.review.lastSeen')}</span><span style={css("font:500 12px 'IBM Plex Sans';color:#1A1714;")}>{v.reviewLastSeen}</span></div>
                    <div style={css('display:flex;justify-content:space-between;padding:11px 13px;background:#fff;')}><span style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;")}>{t('report.review.reporter')}</span><span style={css("font:500 12px 'IBM Plex Sans';color:#1A1714;")}>{v.reviewReporter}</span></div>
                  </div>
                  <div style={css('display:flex;align-items:center;gap:9px;margin-top:13px;padding:12px 13px;background:#FCEDEC;border-radius:12px;')}>
                    <span aria-hidden="true" style={css('width:7px;height:7px;border-radius:50%;background:#C2272D;flex:none;')} />
                    <span style={css("font:500 11.5px 'IBM Plex Sans';color:#B7242A;line-height:1.35;")}>{t('report.review.offlineNote')}</span>
                  </div>
                </div>
              )}
            </div>

            <div style={css('flex:none;display:flex;gap:10px;padding:12px 18px 22px;border-top:1px solid #EDE9E3;')}>
              {v.showBack && (
                <button onClick={actions.prevStep} className="egi-tap" style={css("flex:none;padding:14px 20px;background:#fff;border:1px solid #E2DED8;border-radius:13px;color:#1A1714;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>{t('common.back')}</button>
              )}
              {v.showNext && (
                <button onClick={actions.nextStep} className="egi-tap" style={css("flex:1;padding:14px;background:#1A1714;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;")}>{t('common.continue')}</button>
              )}
              {v.showSubmit && (
                <button onClick={actions.submitReport} className="egi-tap" style={css("flex:1;padding:14px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 14px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('report.save')}</button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

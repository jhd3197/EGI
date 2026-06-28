import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Shelter animal board (plan-28 Phase 4): the animals a shelter is holding,
// rendered inside the shelter detail "Animales" tab. Cards reuse the species
// emoji/status-chip styling from the missing-animals list and tap through to
// AnimalDetailScreen (actions.openAnimal). When the current user is the
// shelter's verified operator / an operator+, an inline mini-form adds an
// intake. All copy is i18n; missing fields are simply hidden.
const inputStyle = css("width:100%;margin-top:6px;padding:10px 12px;border:1px solid #E2DED8;border-radius:11px;font:400 13px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")
const labelStyle = css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;")

const SPECIES = ['dog', 'cat', 'bird', 'rabbit', 'other']
const SPECIES_EMOJI = { dog: '🐕', cat: '🐈', bird: '🐦', rabbit: '🐇', other: '🐾' }

function Field({ label, value, onChange, placeholder, flex }) {
  return (
    <div style={flex ? { flex } : undefined}>
      <label style={labelStyle}>{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={label} style={inputStyle} />
    </div>
  )
}

function AddForm({ shelterId, actions }) {
  const { t } = useI18n()
  const [d, setD] = useState({ species: 'dog' })
  const set = (field) => (value) => setD((prev) => ({ ...prev, [field]: value }))

  const submit = async () => {
    await actions.addShelterAnimal(shelterId, d)
    setD({ species: 'dog' })
  }

  return (
    <div style={css('margin-top:14px;padding:13px;background:#F6F3EF;border-radius:13px;display:flex;flex-direction:column;gap:11px;')}>
      <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;text-transform:uppercase;")}>{t('shelterAnimals.addTitle')}</div>

      {/* Species */}
      <div>
        <div style={css("font:500 11.5px 'IBM Plex Sans';color:#6A645C;margin-bottom:7px;")}>{t('report.animal.species')}</div>
        <div style={css('display:flex;gap:7px;flex-wrap:wrap;')}>
          {SPECIES.map((s) => {
            const on = d.species === s
            return (
              <button key={s} onClick={() => set('species')(s)} className="egi-tap" style={{ ...css("display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:18px;font:600 12px 'IBM Plex Sans';cursor:pointer;"), background: on ? '#FFF4F3' : '#fff', color: on ? '#B7242A' : '#5A534C', border: `1.5px solid ${on ? '#E5343B' : '#E2DED8'}` }}>
                <span aria-hidden="true">{SPECIES_EMOJI[s]}</span>{t('animals.species.' + s)}
              </button>
            )
          })}
        </div>
      </div>

      <div style={css('display:flex;gap:10px;')}>
        <Field label={t('report.animal.name')} value={d.name || ''} onChange={set('name')} placeholder={t('report.animal.namePh')} flex="1" />
        <Field label={t('report.animal.color')} value={d.color || ''} onChange={set('color')} placeholder={t('report.animal.colorPh')} flex="1" />
      </div>
      <Field label={t('shelterAnimals.conditionNote')} value={d.conditionNote || ''} onChange={set('conditionNote')} placeholder={t('shelterAnimals.conditionNotePh')} />
      <Field label={t('report.animal.ownerContact')} value={d.ownerContact || ''} onChange={set('ownerContact')} placeholder={t('report.animal.ownerContactPh')} />

      <button onClick={submit} className="egi-tap" style={css("padding:11px 14px;background:#1A1714;border:none;border-radius:11px;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}>{t('shelterAnimals.add')}</button>
    </div>
  )
}

export default function ShelterAnimalPanel({ view, actions }) {
  const { t } = useI18n()
  const s = view.shelterDetail
  if (!s) return null
  const animals = view.shelterAnimals || []

  return (
    <div style={css('margin-top:16px;')}>
      <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:9px;text-transform:uppercase;")}>{t('shelterAnimals.title')}</div>

      {/* Owner hint: route a pet-searcher to contact the shelter. */}
      <div style={css("margin-bottom:12px;padding:10px 12px;background:#F6F3EF;border:1px solid #EDE9E3;border-radius:11px;color:#5A534C;font:500 12px 'IBM Plex Sans';line-height:1.4;")}>{t('shelterAnimals.ownerHint')}</div>

      <div style={css('display:flex;flex-direction:column;gap:11px;')}>
        {animals.map((a) => {
          const intake = String(a.intake_at || '').slice(0, 10)
          return (
            <button key={a.id} onClick={a.open} className="egi-tap" style={css('text-align:left;width:100%;padding:14px;background:#fff;border:1px solid #EDE9E3;border-radius:15px;cursor:pointer;')}>
              <div style={css('display:flex;align-items:center;gap:11px;')}>
                {a.photo
                  ? <img src={a.photo} alt="" style={css('width:46px;height:46px;border-radius:12px;object-fit:cover;flex:none;background:#F2EFEA;')} />
                  : <span aria-hidden="true" style={css('width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex:none;background:#F2EFEA;font-size:24px;')}>{a.emoji}</span>}
                <div style={css('flex:1;min-width:0;')}>
                  <div style={css('display:flex;align-items:center;gap:7px;')}>
                    <span style={css("font:600 14.5px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{a.displayName}</span>
                    <span style={{ ...css("padding:3px 9px;border-radius:7px;font:600 10px 'IBM Plex Sans';flex:none;"), background: a.statusBg, color: a.statusFg }}>{a.statusLabel}</span>
                  </div>
                  <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin-top:3px;")}>
                    {[a.speciesLabel, a.breed, a.color].filter(Boolean).join(' · ')}
                  </div>
                  {a.condition_note && <div style={css("font:400 11.5px 'IBM Plex Sans';color:#5A534C;margin-top:2px;")}>{a.condition_note}</div>}
                  {intake && <div style={css("font:400 11.5px 'IBM Plex Sans';color:#A9A299;margin-top:2px;")}>{t('shelterAnimals.intakeAt', { date: intake })}</div>}
                </div>
              </div>
            </button>
          )
        })}
        {animals.length === 0 && !view.shelterAnimalsLoading && (
          <div style={css("padding:24px 0;text-align:center;font:400 13px 'IBM Plex Sans';color:#A9A299;")}>{t('shelterAnimals.empty')}</div>
        )}
      </div>

      {/* Operator/shelter-staff intake form (same gate as the operator panel). */}
      {view.operator && <AddForm shelterId={s.id} actions={actions} />}
    </div>
  )
}

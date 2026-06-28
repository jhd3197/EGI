import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import FlagModal from './FlagModal.jsx'

// Animal-specific flag reasons (plan-28 Phase 6). Codes are sent as `flag_reason`
// to POST /flags; labels come from animal-scoped i18n keys.
const ANIMAL_FLAG_REASONS = [
  { code: 'not_real', labelKey: 'animals.flag.notReal' },
  { code: 'already_found', labelKey: 'animals.flag.alreadyFound' },
  { code: 'wrong_location', labelKey: 'animals.flag.wrongLocation' },
  { code: 'other', labelKey: 'animals.flag.other' },
]

// Build the tap-to-contact chip (email vs phone) from a raw contact string.
function contactChip(value, t) {
  if (!value) return null
  return /@/.test(value)
    ? { label: t('animalDetail.email'), href: `mailto:${value}`, bg: '#F2EFEA', fg: '#5A534C' }
    : { label: t('animalDetail.call'), href: `tel:${String(value).replace(/[^\d+]/g, '')}`, bg: '#1A1714', fg: '#fff' }
}

// Animal detail card (plan-28): species + name header, status badge, photo,
// info rows and an owner-contact section, plus two public status nudges —
// "I saw this animal" (→ seen) and "I found this animal" (→ found). All fields
// are optional and sourced from the record; missing ones are simply hidden.
function Row({ label, value }) {
  if (!value) return null
  return (
    <div style={css('display:flex;justify-content:space-between;gap:12px;padding:11px 13px;background:#fff;')}>
      <span style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;flex:none;")}>{label}</span>
      <span style={css("font:500 12px 'IBM Plex Sans';color:#1A1714;text-align:right;")}>{value}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={css('margin-top:18px;')}>
      <div style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:9px;text-transform:uppercase;")}>{title}</div>
      {children}
    </div>
  )
}

export default function AnimalDetailScreen({ view, actions }) {
  const { t } = useI18n()
  const a = view.animalDetail
  const [msg, setMsg] = useState('')
  const [flagOpen, setFlagOpen] = useState(false)
  if (!a) return null

  const nudge = (status) => {
    actions.setAnimalStatus(a.id, status)
    setMsg(t('animalDetail.statusUpdated'))
    setTimeout(() => setMsg(''), 3000)
  }

  // Owner contact is revealed on demand (anti-scraping): `revealedContact` is set
  // by revealAnimalContact once the user taps "Mostrar contacto". The owner name
  // may come from the public record or from the reveal payload.
  const revealed = a.revealedContact
  const ownerName = (revealed && revealed.owner_name) || a.owner_name || ''
  const contacts = revealed ? [contactChip(revealed.owner_contact, t)].filter(Boolean) : []

  return (
    <div style={css('padding:0 0 28px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;padding:8px 16px 4px;')}>
        <button onClick={actions.closeAnimal} className="egi-tap" aria-label={t('common.back')} style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{a.speciesLabel}</span>
      </div>

      <div style={css('padding:0 18px;')}>
        <div style={css('display:flex;align-items:flex-start;gap:12px;margin-top:6px;')}>
          {a.photo
            ? <img src={a.photo} alt="" style={css('width:64px;height:64px;border-radius:14px;object-fit:cover;flex:none;background:#F2EFEA;')} />
            : <span aria-hidden="true" style={css('width:64px;height:64px;border-radius:14px;display:flex;align-items:center;justify-content:center;flex:none;background:#F2EFEA;font-size:34px;')}>{a.emoji}</span>}
          <div style={css('flex:1;min-width:0;')}>
            <h1 style={css("margin:0 0 6px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{a.displayName}</h1>
            <div style={css('display:flex;align-items:center;gap:6px;flex-wrap:wrap;')}>
              <span style={{ ...css("padding:4px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';"), background: a.statusBg, color: a.statusFg }}>{a.statusLabel}</span>
              {a.verified && (
                <span title={t('animalDetail.verified')} style={{ ...css("padding:4px 11px;border-radius:8px;font:600 11.5px 'IBM Plex Sans';"), background: '#E3F2E7', color: '#15683A' }}>✓ {t('animalDetail.verified')}</span>
              )}
            </div>
          </div>
        </div>

        {/* Info */}
        <Section title={t('animalDetail.info')}>
          <div style={css('display:flex;flex-direction:column;gap:1px;background:#EDE9E3;border-radius:13px;overflow:hidden;border:1px solid #EDE9E3;')}>
            <Row label={t('animalDetail.species')} value={a.speciesLabel} />
            <Row label={t('animalDetail.breed')} value={a.breed} />
            <Row label={t('animalDetail.sex')} value={a.sex} />
            <Row label={t('animalDetail.size')} value={a.size} />
            <Row label={t('animalDetail.color')} value={a.color} />
            <Row label={t('animalDetail.marks')} value={a.distinguishing_marks} />
            <Row label={t('animalDetail.microchip')} value={a.microchip} />
            <Row label={t('animalDetail.lastSeenLocation')} value={a.last_seen_location} />
            <Row label={t('animalDetail.lastSeenAt')} value={a.last_seen_at} />
          </div>
          {a.notes && <p style={css("margin:13px 0 0;font:400 13.5px 'IBM Plex Sans';color:#4A443D;line-height:1.5;")}>{a.notes}</p>}
        </Section>

        {/* Owner contact — revealed on demand (anti-scraping) */}
        {(ownerName || a.has_owner_contact) && (
          <Section title={t('animalDetail.owner')}>
            {ownerName && <div style={css("font:600 13.5px 'IBM Plex Sans';color:#2A2520;margin-bottom:9px;")}>{ownerName}</div>}
            {revealed ? (
              <div style={css('display:flex;gap:8px;flex-wrap:wrap;')}>
                {contacts.map((c, idx) => (
                  <a key={idx} href={c.href} className="egi-tap" style={{ ...css("flex:none;padding:12px 16px;border-radius:13px;text-decoration:none;font:600 13px 'IBM Plex Sans';display:flex;align-items:center;border:1px solid #E6E2DC;"), background: c.bg, color: c.fg }}>{c.label}</a>
                ))}
              </div>
            ) : a.has_owner_contact ? (
              <button onClick={() => actions.revealAnimalContact(a.id)} className="egi-tap" style={css("padding:12px 16px;background:#1A1714;border:none;border-radius:13px;color:#fff;font:600 13px 'IBM Plex Sans';cursor:pointer;")}>{t('animalDetail.revealContact')}</button>
            ) : null}
          </Section>
        )}

        {/* Public status nudges */}
        <Section title={t('animalDetail.helpTitle')}>
          <div style={css('display:flex;gap:8px;flex-wrap:wrap;')}>
            <button onClick={() => nudge('seen')} className="egi-tap" style={css("flex:1;min-width:140px;padding:13px;background:#9A6400;border:none;border-radius:13px;color:#fff;font:600 13px 'IBM Plex Sans';cursor:pointer;")}>{t('animalDetail.sawThis')}</button>
            <button onClick={() => nudge('found')} className="egi-tap" style={css("flex:1;min-width:140px;padding:13px;background:#1B7A45;border:none;border-radius:13px;color:#fff;font:600 13px 'IBM Plex Sans';cursor:pointer;")}>{t('animalDetail.foundThis')}</button>
          </div>
          {msg && <div style={css("margin-top:9px;font:500 12.5px 'IBM Plex Sans';color:#15683A;")}>{msg}</div>}
        </Section>

        {/* Report this record (plan-28 Phase 6) */}
        <div style={css('display:flex;justify-content:center;margin-top:18px;')}>
          <button
            onClick={() => setFlagOpen(true)}
            className="egi-tap"
            style={css("background:transparent;border:none;cursor:pointer;font:500 12px 'IBM Plex Sans';color:#A9A299;text-decoration:underline;padding:4px;")}
          >
            {t('animalDetail.flag')}
          </button>
        </div>
      </div>

      <FlagModal
        open={flagOpen}
        recordType="animal"
        recordId={a.id}
        reasons={ANIMAL_FLAG_REASONS}
        onClose={() => setFlagOpen(false)}
        actions={actions}
      />
    </div>
  )
}

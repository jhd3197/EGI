import { useEffect } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Missing-animals list (plan-28): a parallel track to people. Each row taps
// through to the detail card and shows a species emoji, name, status chip and
// last-seen line. Species + status quick filters sit above the list, and a FAB
// opens the animal report sheet. A small note links people-searchers to the
// people form (the `animals.notPersonNote` key is relied on by a later phase).
export default function AnimalsScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()

  // Refresh animals from the server when the screen mounts (offline → cache).
  useEffect(() => { actions.fetchAnimals() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={css('padding:16px 18px 24px;')}>
      <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('animals.title')}</h1>
      <p style={css("margin:0 0 12px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>{t('animals.subtitle')}</p>

      {/* "Looking for a person?" hint → people form */}
      <button onClick={() => actions.setScreen('search')} className="egi-tap" style={css("display:block;width:100%;text-align:left;margin-bottom:14px;padding:10px 12px;background:#F6F3EF;border:1px solid #EDE9E3;border-radius:11px;color:#5A534C;font:500 12px 'IBM Plex Sans';cursor:pointer;")}>{t('animals.notPersonNote')}</button>

      {/* Species filters */}
      <div style={css('display:flex;gap:7px;margin-bottom:8px;flex-wrap:wrap;')}>
        {v.animalFilters.species.map((f) => (
          <button key={f.key} onClick={f.onClick} aria-pressed={f.active} className="egi-tap" style={{ ...css("padding:7px 13px;border-radius:18px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: f.chipBg, color: f.chipFg, border: `1px solid ${f.chipBorder}` }}>{f.label}</button>
        ))}
      </div>
      {/* Status filters */}
      <div style={css('display:flex;gap:7px;margin-bottom:14px;flex-wrap:wrap;')}>
        {v.animalFilters.status.map((f) => (
          <button key={f.key} onClick={f.onClick} aria-pressed={f.active} className="egi-tap" style={{ ...css("padding:7px 13px;border-radius:18px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: f.chipBg, color: f.chipFg, border: `1px solid ${f.chipBorder}` }}>{f.label}</button>
        ))}
      </div>

      <div style={css('display:flex;flex-direction:column;gap:11px;')}>
        {v.visibleAnimals.map((a) => (
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
                {a.lastSeenText && <div style={css("font:400 11.5px 'IBM Plex Sans';color:#A9A299;margin-top:2px;")}>{t('animals.lastSeenAt', { where: a.lastSeenText })}</div>}
              </div>
            </div>
          </button>
        ))}
        {v.visibleAnimals.length === 0 && (
          <div style={css("padding:24px 0;text-align:center;font:400 13px 'IBM Plex Sans';color:#A9A299;")}>{t('animals.empty')}</div>
        )}
      </div>

      {/* Report a missing/found animal */}
      <button onClick={actions.openAnimalReport} className="egi-tap" style={css("margin-top:18px;width:100%;padding:13px;background:#E5343B;border:none;border-radius:13px;color:#fff;font:600 13.5px 'IBM Plex Sans';cursor:pointer;box-shadow:0 8px 16px -8px rgba(229,52,59,.6);")}>{t('animals.report')}</button>
    </div>
  )
}

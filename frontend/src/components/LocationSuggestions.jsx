import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Location-aware suggestion panel (plan-27.5 Phase 6). Renders proximity prompts
// ("you're near operation X", "near hospital Y") from view.locationSuggest.
// Opt-in: a "hide" toggle disables it. Nothing renders when there are no nearby
// targets, when disabled, or before a position fix — so it never nags.
export default function LocationSuggestions({ view, actions }) {
  const { t } = useI18n()
  const ls = view.locationSuggest
  if (!ls || !ls.enabled || !ls.items || ls.items.length === 0) return null

  const open = (item) => {
    if (item.kind === 'operation') actions.openOperation(item.id)
    else if (item.kind === 'facility') actions.openShelter(item.id)
  }

  return (
    <div style={css('margin:14px 0;padding:13px 14px;background:#EEF4F9;border:1px solid #D3E2EF;border-radius:14px;')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;')}>
        <span style={css("font:600 12px 'IBM Plex Mono';color:#1F5E96;letter-spacing:.04em;text-transform:uppercase;")}>{t('suggest.title')}</span>
        <button onClick={actions.toggleLocationSuggest} className="egi-tap" style={css("background:none;border:none;cursor:pointer;font:600 11px 'IBM Plex Sans';color:#5A7892;")}>{t('suggest.hide')}</button>
      </div>
      <div style={css('display:flex;flex-direction:column;gap:8px;')}>
        {ls.items.map((it) => (
          <button key={it.kind + it.id} onClick={() => open(it)} className="egi-tap" style={css('width:100%;display:flex;align-items:center;gap:11px;padding:11px 12px;background:#fff;border:1px solid #D9E5F0;border-radius:11px;cursor:pointer;text-align:left;')}>
            <span aria-hidden="true" style={{ ...css('width:30px;height:30px;border-radius:9px;flex:none;display:flex;align-items:center;justify-content:center;'), background: it.kind === 'facility' ? '#F6ECDD' : '#E4EEF6' }}>
              <span style={{ ...css('width:11px;height:11px;border-radius:50%;'), background: it.kind === 'facility' ? '#9A5B14' : '#1F5E96' }} />
            </span>
            <div style={css('flex:1;min-width:0;')}>
              <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{it.name}</div>
              <div style={css("font:400 10.5px 'IBM Plex Mono';color:#8B8278;margin-top:2px;")}>
                {t(it.kind === 'facility' ? 'suggest.nearFacility' : 'suggest.nearOperation')} · {it.distanceM} m
              </div>
            </div>
            <span aria-hidden="true" style={css('width:8px;height:8px;border-top:2.2px solid #9FB6CC;border-right:2.2px solid #9FB6CC;transform:rotate(45deg);flex:none;')} />
          </button>
        ))}
      </div>
    </div>
  )
}

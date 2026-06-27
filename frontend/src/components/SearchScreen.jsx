import { useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// One person card, shared by the cédula results and the main list. When
// `quickActions` is set it also renders one-tap "open" + "mark safe" buttons.
function PersonCard({ p, t, quickActions, onOpen, onMarkSafe, marked }) {
  return (
    <div style={css('display:flex;flex-direction:column;background:#fff;border:1px solid #EDE9E3;border-radius:15px;')}>
      <button onClick={p.open} className="egi-tap" style={css('display:flex;gap:13px;align-items:center;padding:11px;background:transparent;border:none;border-radius:15px;cursor:pointer;text-align:left;')}>
        <span style={css("width:54px;height:54px;border-radius:12px;flex:none;background-image:repeating-linear-gradient(45deg,#EFEDE9,#EFEDE9 6px,#E4E1DB 6px,#E4E1DB 12px);display:flex;align-items:center;justify-content:center;font:600 16px 'IBM Plex Mono';color:#A89F94;")}>{p.initials}</span>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css('display:flex;align-items:center;gap:7px;')}>
            <span style={css("font:600 14.5px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{p.name}</span>
          </div>
          <div style={css("font:400 12px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{p.meta}</div>
          <div style={css('display:flex;align-items:center;gap:6px;margin-top:7px;')}>
            <span style={{ ...css("padding:3px 8px;border-radius:6px;font:600 10px 'IBM Plex Sans';"), background: p.badgeBg, color: p.badgeFg }}>{p.statusLabel}</span>
            <span style={css("font:400 10.5px 'IBM Plex Mono';color:#A9A299;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{p.cedula || p.place}</span>
          </div>
        </div>
      </button>
      {quickActions && (
        <div style={css('display:flex;gap:8px;padding:0 11px 11px;')}>
          <button onClick={onOpen} className="egi-tap" style={css("flex:1;padding:8px;border-radius:10px;border:1px solid #E2DED8;background:#fff;color:#1A1714;font:600 12px 'IBM Plex Sans';cursor:pointer;")}>{t('search.open')}</button>
          <button onClick={onMarkSafe} disabled={marked} className="egi-tap" style={{ ...css("flex:1;padding:8px;border-radius:10px;border:1px solid #CCE6D6;font:600 12px 'IBM Plex Sans';cursor:pointer;"), background: marked ? '#E9F4ED' : '#1B7A45', color: marked ? '#15683A' : '#fff', opacity: marked ? 0.9 : 1 }}>{marked ? t('search.marked') : t('search.markSafe')}</button>
        </div>
      )}
    </div>
  )
}

export default function SearchScreen({ view, actions }) {
  const v = view
  const { t } = useI18n()
  const [scanHint, setScanHint] = useState(false)
  const [marked, setMarked] = useState({})

  const markSafe = (id) => {
    // Simplest persistent path: queue a witness "safe" note for this person.
    actions.addPersonReport(id, t('search.safeNote'), 'witness')
    setMarked((m) => ({ ...m, [id]: true }))
  }

  return (
    <div style={css('padding:16px 18px 24px;')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px;')}>
        <h1 style={css("margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('search.title')}</h1>
        <span style={css("font:500 11px 'IBM Plex Mono';color:#A9A299;")}>{t('search.count', { n: v.visibleCount })}</span>
      </div>

      {/* Phase 6 — dedicated cédula search */}
      <div style={css('background:#fff;border:1px solid #E6E2DC;border-radius:13px;padding:12px 14px;margin-bottom:13px;')}>
        <div style={css("font:600 12px 'IBM Plex Sans';color:#5A534C;margin-bottom:8px;")}>{t('search.cedulaTitle')}</div>
        <form
          onSubmit={(e) => { e.preventDefault(); actions.searchCedula(v.cedulaQuery) }}
          style={css('display:flex;align-items:center;gap:8px;')}
        >
          <input
            value={v.cedulaQuery}
            onChange={(e) => actions.setCedulaQuery(e.target.value)}
            inputMode="numeric"
            aria-label={t('search.cedulaSearchAria')}
            placeholder={t('search.cedulaPlaceholder')}
            style={css("flex:1;min-width:0;padding:9px 11px;border:1px solid #E6E2DC;border-radius:10px;outline:none;background:#FAF8F5;font:400 13px 'IBM Plex Mono';color:#1A1714;")}
          />
          {/* Camera scan — OCR is future work; show a "coming soon" hint only. */}
          <button
            type="button"
            onClick={() => setScanHint((s) => !s)}
            aria-label={t('search.scanAria')}
            title={t('search.scanSoon')}
            className="egi-tap"
            style={css('flex:none;width:38px;height:38px;border-radius:10px;border:1px dashed #CFC9C0;background:#F6F4F0;cursor:pointer;display:flex;align-items:center;justify-content:center;position:relative;')}
          >
            <span aria-hidden="true" style={css('width:18px;height:14px;border:2px solid #9A938A;border-radius:4px;position:relative;display:block;')}>
              <span style={css('position:absolute;top:-5px;left:4px;width:8px;height:4px;border:2px solid #9A938A;border-bottom:none;border-radius:3px 3px 0 0;')} />
              <span style={css('position:absolute;top:2px;left:5px;width:6px;height:6px;border:2px solid #9A938A;border-radius:50%;')} />
            </span>
          </button>
          <button
            type="submit"
            className="egi-tap"
            style={css("flex:none;padding:9px 14px;border-radius:10px;border:none;background:#1A1714;color:#fff;font:600 12.5px 'IBM Plex Sans';cursor:pointer;")}
          >{t('search.cedulaButton')}</button>
        </form>
        {scanHint && (
          <div style={css("margin-top:8px;font:500 11.5px 'IBM Plex Sans';color:#8A837A;")}>{t('search.scanSoon')}</div>
        )}
      </div>

      {v.cedulaActive ? (
        /* Cédula results view */
        <div>
          <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;')}>
            <span style={css("font:600 12px 'IBM Plex Mono';color:#A9A299;")}>{t('search.cedulaResults', { n: v.cedulaCount })}</span>
            <button onClick={actions.clearCedula} className="egi-tap" style={css("padding:5px 10px;border-radius:8px;border:1px solid #E2DED8;background:#fff;color:#5A534C;font:500 11.5px 'IBM Plex Sans';cursor:pointer;")}>{t('search.clear')}</button>
          </div>
          {v.cedulaCount === 0 ? (
            <div style={css("padding:18px;text-align:center;font:400 13px 'IBM Plex Sans';color:#8A837A;background:#fff;border:1px solid #EDE9E3;border-radius:15px;")}>{t('search.cedulaEmpty')}</div>
          ) : (
            <div style={css('display:flex;flex-direction:column;gap:10px;')}>
              {v.cedulaResults.map((p) => (
                <PersonCard
                  key={p.id} p={p} t={t} quickActions
                  onOpen={() => actions.openPerson(p.id)}
                  onMarkSafe={() => markSafe(p.id)}
                  marked={!!marked[p.id]}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Normal free-text + status filter list */
        <div>
          <div style={css('display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fff;border:1px solid #E6E2DC;border-radius:13px;margin-bottom:13px;')}>
            <span aria-hidden="true" style={css('width:16px;height:16px;border:2px solid #B3ABA1;border-radius:50%;position:relative;flex:none;')}>
              <span style={css('position:absolute;width:6px;height:2px;background:#B3ABA1;border-radius:1px;transform:rotate(45deg);right:-4px;bottom:-1px;')} />
            </span>
            <input
              value={v.search}
              onChange={(e) => actions.setSearch(e.target.value)}
              aria-label={t('search.inputAria')}
              placeholder={t('search.placeholder')}
              style={css("flex:1;min-width:0;border:none;outline:none;background:transparent;font:400 13px 'IBM Plex Sans';color:#1A1714;")}
            />
          </div>
          <div className="egi-scroll" style={css('display:flex;gap:8px;overflow-x:auto;padding-bottom:13px;margin:0 -18px;padding-left:18px;padding-right:18px;')}>
            {v.chips.map((c) => (
              <button key={c.key} onClick={c.onClick} className="egi-tap" style={{ ...css("flex:none;padding:7px 14px;border-radius:20px;font:500 12.5px 'IBM Plex Sans';cursor:pointer;"), background: c.chipBg, color: c.chipFg, border: `1px solid ${c.chipBorder}` }}>{c.label}</button>
            ))}
          </div>
          <div style={css('display:flex;flex-direction:column;gap:10px;')}>
            {v.visiblePeople.map((p) => (
              <PersonCard key={p.id} p={p} t={t} />
            ))}
          </div>
          {v.searchHasMore && !v.searchLoading && (
            <button
              onClick={actions.loadMore}
              className="egi-tap"
              style={css("width:100%;margin-top:13px;padding:12px;border-radius:12px;border:1px solid #E2DED8;background:#fff;color:#1A1714;font:600 13px 'IBM Plex Sans';cursor:pointer;")}
            >{t('search.loadMore')}</button>
          )}
          {v.searchLoading && (
            <div style={css("margin-top:13px;text-align:center;font:500 12px 'IBM Plex Sans';color:#8A837A;")}>{t('common.loading')}</div>
          )}
        </div>
      )}
    </div>
  )
}

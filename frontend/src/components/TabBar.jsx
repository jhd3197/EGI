import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { HomeIcon, SearchIcon, SheltersIcon, MineIcon, SettingsIcon, OperationsIcon } from './Icons.jsx'

function Tab({ onClick, color, icon, label, current }) {
  return (
    <button onClick={onClick} className="egi-tap" aria-current={current ? 'page' : undefined} style={{ ...css('flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;border:none;background:transparent;cursor:pointer;'), color }}>
      <span aria-hidden="true" style={css('display:flex;')}>{icon}</span>
      <span style={css("font:500 9.5px 'IBM Plex Sans';")}>{label}</span>
    </button>
  )
}

// Mobile-only bottom tab bar with the central report button.
export default function TabBar({ view, actions }) {
  const v = view
  const { t } = useI18n()
  return (
    <nav aria-label={t('nav.primaryAria')} style={{ ...css('flex:none;align-items:flex-start;justify-content:space-around;padding:9px 8px 22px;background:rgba(251,250,248,.94);backdrop-filter:blur(12px);border-top:1px solid #EDE9E3;position:relative;z-index:20;'), display: v.tabBarDisplay }}>
      <Tab onClick={() => actions.setScreen('home')} color={v.tabHome} icon={<HomeIcon size={22} />} label={t('nav.home')} current={v.isHome} />
      <Tab onClick={() => actions.setScreen('search')} color={v.tabSearch} icon={<SearchIcon size={22} />} label={t('nav.search')} current={v.isSearch} />
      <button onClick={() => actions.openReport('missing')} className="egi-tap" aria-label={t('nav.report')} style={css('flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;border:none;background:transparent;cursor:pointer;color:#E5343B;')}>
        <span aria-hidden="true" style={css('width:40px;height:40px;border-radius:14px;background:#E5343B;display:flex;align-items:center;justify-content:center;margin-top:-2px;box-shadow:0 8px 16px -6px rgba(229,52,59,.55);position:relative;')}>
          <span style={css('position:absolute;width:16px;height:3px;background:#fff;border-radius:2px;')} />
          <span style={css('position:absolute;width:3px;height:16px;background:#fff;border-radius:2px;')} />
        </span>
      </button>
      {/* When the user hides the shelters category, its tab is replaced by a
          Settings entry so the bar keeps its five balanced slots (plan-24 §3). */}
      {v.showSheltersTab ? (
        <Tab onClick={() => actions.setScreen('shelters')} color={v.tabShelters} icon={<SheltersIcon size={22} />} label={t('nav.shelters')} current={v.isShelters} />
      ) : (
        <Tab onClick={() => actions.setScreen('settings')} color={v.isSettings ? '#E5343B' : '#9A938A'} icon={<SettingsIcon size={22} />} label={t('nav.settings')} current={v.isSettings} />
      )}
      {v.showOperationsTab && (
        <Tab onClick={() => actions.setScreen('operations')} color={v.isOperations || v.isOperationDetail ? '#E5343B' : '#9A938A'} icon={<OperationsIcon size={22} />} label={t('nav.operations')} current={v.isOperations || v.isOperationDetail} />
      )}
      <Tab onClick={() => actions.setScreen('mine')} color={v.tabMine} icon={<MineIcon size={22} />} label={t('nav.mine')} current={v.isMine} />
    </nav>
  )
}

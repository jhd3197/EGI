import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { HomeIcon, SearchIcon, SheltersIcon, MineIcon, SettingsIcon, OperationsIcon, PawIcon, MapIcon, RouteIcon } from './Icons.jsx'

// Icon for the dynamic contextual right-slot, keyed by view.contextualTab.key.
const CONTEXTUAL_ICONS = {
  shelters: SheltersIcon,
  operations: OperationsIcon,
  animals: PawIcon,
  directions: RouteIcon,
}

function Tab({ onClick, color, icon, label, current }) {
  return (
    <button onClick={onClick} className="egi-tap" aria-current={current ? 'page' : undefined} style={{ ...css('flex:1;min-width:0;min-height:48px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;border:none;background:transparent;cursor:pointer;padding:4px 2px;'), color }}>
      <span aria-hidden="true" style={css('display:flex;')}>{icon}</span>
      <span style={css("font:500 10px 'IBM Plex Sans';white-space:nowrap;")}>{label}</span>
    </button>
  )
}

// Mobile-only bottom tab bar: three fixed tabs, the central report button, then
// three more — a symmetrical 3 + + + 3 layout (plan-31). The sixth slot is
// contextual (shelters / operations / animals / directions) per view.js.
export default function TabBar({ view, actions }) {
  const v = view
  const { t } = useI18n()
  const ct = v.contextualTab
  const CtIcon = CONTEXTUAL_ICONS[ct.key] || RouteIcon
  const onContextual = ct.key === 'directions'
    ? () => actions.openDirections()
    : () => actions.setScreen(ct.screen)
  const group = css('flex:1;display:flex;align-items:stretch;justify-content:space-around;min-width:0;')
  return (
    <nav aria-label={t('nav.primaryAria')} style={{ ...css('flex:none;align-items:stretch;gap:4px;padding:6px 6px calc(8px + env(safe-area-inset-bottom));background:rgba(251,250,248,.94);backdrop-filter:blur(12px);border-top:1px solid #EDE9E3;position:relative;z-index:20;'), display: v.tabBarDisplay }}>
      <div style={group}>
        <Tab onClick={() => actions.setScreen('home')} color={v.tabHome} icon={<HomeIcon size={22} />} label={t('nav.home')} current={v.isHome} />
        <Tab onClick={() => actions.setScreen('search')} color={v.tabSearch} icon={<SearchIcon size={22} />} label={t('nav.search')} current={v.isSearch} />
        <Tab onClick={() => actions.setScreen('map')} color={v.tabMap} icon={<MapIcon size={22} />} label={t('nav.map')} current={v.isMap} />
      </div>
      <button onClick={() => actions.openReport('missing')} className="egi-tap" aria-label={t('nav.report')} style={css('flex:none;width:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:none;background:transparent;cursor:pointer;')}>
        <span aria-hidden="true" style={css('width:46px;height:46px;border-radius:16px;background:#E5343B;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 16px -6px rgba(229,52,59,.55);position:relative;')}>
          <span style={css('position:absolute;width:18px;height:3px;background:#fff;border-radius:2px;')} />
          <span style={css('position:absolute;width:3px;height:18px;background:#fff;border-radius:2px;')} />
        </span>
      </button>
      <div style={group}>
        <Tab onClick={() => actions.setScreen('mine')} color={v.tabMine} icon={<MineIcon size={22} />} label={t('nav.mine')} current={v.isMine} />
        <Tab onClick={onContextual} color={ct.color} icon={<CtIcon size={22} />} label={t(ct.labelKey)} current={ct.active} />
        <Tab onClick={() => actions.setScreen('settings')} color={v.isSettings ? '#E5343B' : '#9A938A'} icon={<SettingsIcon size={22} />} label={t('nav.settings')} current={v.isSettings} />
      </div>
    </nav>
  )
}

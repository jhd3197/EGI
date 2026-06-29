// Regression tests for the plan-31 mobile UX fixes so they cannot silently
// regress:
//   §1 the bottom tab bar is a balanced 3 + report + 3 (7 controls, report 4th).
//   §2 Directions defaults to a place-name field; raw coords stay hidden until
//      the user switches to "Coordenadas".
//   §3 the home screen drops the intent picker and the header simple-mode toggle.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement as h } from 'react'
import TabBar from '../src/components/TabBar.jsx'
import DirectionsScreen from '../src/components/DirectionsScreen.jsx'
import HomeScreen from '../src/components/HomeScreen.jsx'
import { translate, getLang } from '../src/i18n/index.js'

const T = (k, vars) => translate(getLang(), k, vars)
const parse = (html) => new DOMParser().parseFromString(`<div id="root">${html}</div>`, 'text/html')
const noop = () => {}

describe('§1 TabBar — balanced 3 + report + 3', () => {
  const view = {
    tabBarDisplay: 'flex',
    isHome: true, isSearch: false, isMap: false, isMine: false, isSettings: false,
    tabHome: '#E5343B', tabSearch: '#9A938A', tabMap: '#9A938A', tabMine: '#9A938A',
    contextualTab: { key: 'directions', screen: 'directions', labelKey: 'nav.directions', active: false, color: '#9A938A' },
  }
  const actions = { setScreen: noop, openReport: noop, openDirections: noop }
  const doc = parse(renderToStaticMarkup(h(TabBar, { view, actions })))
  const buttons = [...doc.querySelectorAll('button')]

  it('renders exactly six tabs plus the centred report button', () => {
    expect(buttons.length).toBe(7)
  })

  it('places the report button in the centre (4th of 7)', () => {
    const reportButtons = buttons.filter((b) => b.getAttribute('aria-label') === T('nav.report'))
    expect(reportButtons.length).toBe(1)
    expect(buttons[3].getAttribute('aria-label')).toBe(T('nav.report'))
  })

  it('shows the three left and three right tab labels', () => {
    const html = doc.body.innerHTML
    for (const k of ['nav.home', 'nav.search', 'nav.map', 'nav.mine', 'nav.directions', 'nav.settings']) {
      expect(html).toContain(T(k))
    }
  })
})

describe('§2 DirectionsScreen — place-name default, coords advanced', () => {
  const view = {
    directionsTarget: null,
    directionsDestinations: { shelters: [], people: [] },
    sharedRoutes: [], hazards: [], routePolyline: null,
  }
  const actions = {
    fetchSharedRoutes: noop, fetchCorridors: noop, setRoutePolyline: noop,
    shareRoute: noop, openDirections: noop,
  }
  const doc = parse(renderToStaticMarkup(h(DirectionsScreen, { view, actions })))

  it('shows a destination place-name input by default', () => {
    expect(doc.querySelector('[data-testid="dir-dest-place"]')).not.toBeNull()
  })

  it('does not show the raw coordinates input until the user switches mode', () => {
    expect(doc.querySelector('[data-testid="dir-dest-coords"]')).toBeNull()
  })
})

describe('§3 HomeScreen — no intent picker, no header simple-mode toggle', () => {
  const view = {
    categoryFilterNote: null,
    disasterName: 'Demo', disasterMeta: 'meta',
    checkedInSafe: false, activity: [], simpleMode: false,
    locationSuggest: { enabled: true, hasPos: false, items: [] },
  }
  const actions = { checkInSelf: noop, setScreen: noop, openReport: noop }
  const html = renderToStaticMarkup(h(HomeScreen, { view, actions }))

  it('does not render the intent picker', () => {
    expect(html).not.toContain(T('home.intentTitle'))
  })

  it('does not render the simple-mode toggle in the home header', () => {
    expect(html).not.toContain(T('simple.toggle'))
  })

  it('keeps the primary actions (check-in, search, report)', () => {
    expect(html).toContain(T('home.imOk'))
    expect(html).toContain(T('home.searchTitle'))
    expect(html).toContain(T('report.typeLabel.missing'))
  })
})

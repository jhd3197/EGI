// Regression tests for the plan-29 UX fixes so they cannot silently come back:
//   §3.1 the wordmark renders at one uniform size (no oversized "E").
//   §3.2 the app background uses the neutral token, not the old warm beige.
//   §3.3 the shelter origin lets you pick a location; raw coordinates are demoted.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement as h } from 'react'
import Wordmark from '../src/components/Wordmark.jsx'
import ShelterDetailScreen from '../src/components/ShelterDetailScreen.jsx'
import { color } from '../src/styles/tokens.js'
import { parseCoords } from '../src/lib/directions.js'

describe('§3.1 Wordmark uniform size', () => {
  it('renders "EGI" as one run of text', () => {
    const html = renderToStaticMarkup(h(Wordmark, { size: 30 }))
    expect(html).toContain('EGI')
    // The old split rendered separate <span>E</span><span>GI</span>. Guard
    // against any inner element that would re-introduce two sizes.
    expect(html).not.toContain('>E</span>')
    expect(html).not.toContain('>GI</span>')
  })
  it('does not emit two different font-size values', () => {
    const html = renderToStaticMarkup(h(Wordmark, { size: 30 }))
    const sizes = (html.match(/font-size:\s*\d+px/g) || [])
    // One size at most — never an E/GI split.
    expect(new Set(sizes).size).toBeLessThanOrEqual(1)
  })
})

describe('§3.2 background token', () => {
  it('is a clean cool neutral, not the old warm beige', () => {
    expect(color.bg.toUpperCase()).toBe('#F8F9FA')
    expect(color.bg.toUpperCase()).not.toBe('#F4EFE7')
  })
})

describe('§3.3 shelter origin location options', () => {
  const view = {
    shelterDetail: {
      id: 's1', name: 'Refugio Demo', tag: 'DEMO', lat: 10.6, lon: -66.9,
      services: [], supplyNeeds: [], targetPopulations: [], trustLabel: 'Oficial',
      trustBg: '#fff', trustFg: '#000',
    },
    shelterTab: 'info', operator: false, shelterUpdates: [], shelterUpdatesLoading: false,
    shelterCheckedIn: null,
  }
  const actions = { openDirections() {}, closeShelter() {}, setShelterTab() {} }
  const html = renderToStaticMarkup(h(ShelterDetailScreen, { view, actions }))

  it('offers a "use my location" option', () => {
    expect(html).toContain('shelter-use-location')
  })

  it('demotes the raw coordinates input below the friendly options', () => {
    const coordsIdx = html.indexOf('shelter-origin-coords')
    const useLocIdx = html.indexOf('shelter-use-location')
    const advancedIdx = html.indexOf('shelter-advanced-coords')
    expect(useLocIdx).toBeGreaterThan(-1)
    expect(advancedIdx).toBeGreaterThan(-1)
    expect(coordsIdx).toBeGreaterThan(-1)
    // The coordinates field is not the primary/default control: it sits after
    // "use my location" and behind the "advanced" disclosure.
    expect(coordsIdx).toBeGreaterThan(useLocIdx)
    expect(coordsIdx).toBeGreaterThan(advancedIdx)
  })
})

describe('parseCoords helper', () => {
  it('parses "lat, lon"', () => {
    expect(parseCoords('10.5, -66.9')).toEqual({ lat: 10.5, lon: -66.9 })
  })
  it('rejects out-of-range and garbage', () => {
    expect(parseCoords('not a place')).toBeNull()
    expect(parseCoords('200, 0')).toBeNull()
  })
})

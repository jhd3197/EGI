// Automated accessibility checks (plan-29 §2) — the check CI gates on. No extra
// deps: it renders real screens and enforces two high-value axe-style rules over
// the output using jsdom (already the test environment):
//   * button-name — every <button> has an accessible name (text or aria-label).
//   * label       — every text <input> has a name (label / aria-label / placeholder).
// Icon-only buttons (back arrows, mesh/settings toggles) are the usual offenders,
// so this guards them at the component level on every PR.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement as h } from 'react'
import ShelterDetailScreen from '../src/components/ShelterDetailScreen.jsx'

// Parse rendered HTML into a queryable document (jsdom global from vitest env).
function parse(html) {
  return new DOMParser().parseFromString(`<div id="root">${html}</div>`, 'text/html')
}

function unlabeledButtons(doc) {
  return [...doc.querySelectorAll('button')].filter((b) => {
    const text = (b.textContent || '').trim()
    const aria = b.getAttribute('aria-label') || b.getAttribute('aria-labelledby')
    const title = b.getAttribute('title')
    return !text && !aria && !title
  })
}

function unlabeledInputs(doc) {
  return [...doc.querySelectorAll('input')].filter((i) => {
    const type = (i.getAttribute('type') || 'text').toLowerCase()
    if (['hidden', 'submit', 'button', 'checkbox', 'radio'].includes(type)) return false
    const aria = i.getAttribute('aria-label') || i.getAttribute('aria-labelledby')
    const placeholder = i.getAttribute('placeholder')
    const id = i.getAttribute('id')
    const hasLabel = id && doc.querySelector(`label[for="${id}"]`)
    return !aria && !placeholder && !hasLabel
  })
}

const shelterView = {
  shelterDetail: {
    id: 's1', name: 'Refugio Demo', tag: 'DEMO', lat: 10.6, lon: -66.9,
    services: ['beds'], supplyNeeds: [], targetPopulations: [], trustLabel: 'Oficial',
    trustBg: '#fff', trustFg: '#000', phone: '+58000', occPct: 40, capLabel: 'x',
    acceptingLabel: 'Acepta', acceptingBg: '#fff', acceptingFg: '#000', barColor: '#1B7A45',
  },
  shelterTab: 'info', operator: false, shelterUpdates: [], shelterUpdatesLoading: false,
  shelterCheckedIn: null,
}
const noop = () => {}
const shelterActions = {
  openDirections: noop, closeShelter: noop, setShelterTab: noop, shelterCheckin: noop,
  postShelterUpdate: noop, updateShelterCapacity: noop,
}

describe('a11y: ShelterDetailScreen', () => {
  const doc = parse(renderToStaticMarkup(h(ShelterDetailScreen, { view: shelterView, actions: shelterActions })))

  it('every button has an accessible name', () => {
    const bad = unlabeledButtons(doc).map((b) => b.outerHTML.slice(0, 80))
    expect(bad, `unlabeled buttons:\n${bad.join('\n')}`).toEqual([])
  })

  it('every text input has a name', () => {
    const bad = unlabeledInputs(doc).map((i) => i.outerHTML.slice(0, 80))
    expect(bad, `unlabeled inputs:\n${bad.join('\n')}`).toEqual([])
  })
})

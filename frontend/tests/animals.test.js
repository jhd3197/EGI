// Animal view-derivation + preference-gating tests (plan-28 Phases 3/6/7).
// buildView() must decorate animal records (species/status/verified/contact
// protection) and respect the unified plan-24 "animals" category: when the
// display toggle is off, the Animals tab hides and no animal records leak into
// the view.
import { describe, expect, it, vi } from 'vitest'
import { buildView } from '../src/lib/view.js'
import { defaultPreferences } from '../src/lib/preferences.js'

const baseState = (over = {}) => ({
  authed: true, selectedDisasterId: 'd1', screen: 'animals',
  overrides: {}, people: [], filter: 'all', search: '', customDisasters: [], disasters: [],
  reportDraft: {}, reportType: 'missing', reportStep: 0,
  preferences: defaultPreferences(),
  animalFilters: { species: 'all', status: 'all' },
  animals: [
    { id: 'animal-1', disaster_id: 'd1', species: 'dog', name: 'Toby', status: 'missing',
      color: 'golden', last_seen_location: 'La Guaira', source: 'web', reviewed: 0,
      has_owner_contact: true },
    { id: 'animal-2', disaster_id: 'd1', species: 'cat', name: 'Michi', status: 'found',
      source: 'shelter', reviewed: 1, has_owner_contact: false },
  ],
  ...over,
})

const actions = { openAnimal: vi.fn(), setAnimalFilter: vi.fn(), openAnimalReport: vi.fn() }
const t = (k) => k

describe('animal view derivation', () => {
  it('decorates animals with species/status/verified + contact protection', () => {
    const v = buildView(baseState(), actions, t)
    expect(v.visibleAnimals).toHaveLength(2)
    const toby = v.visibleAnimals.find((a) => a.id === 'animal-1')
    expect(toby.emoji).toBe('🐕')
    expect(toby.displayName).toBe('Toby')
    expect(toby.verified).toBe(false) // web + reviewed 0
    expect(toby.has_owner_contact).toBe(true)
    expect(toby).not.toHaveProperty('owner_contact') // never returned by the API
    const michi = v.visibleAnimals.find((a) => a.id === 'animal-2')
    expect(michi.verified).toBe(true) // shelter-held / approved
    expect(typeof toby.open).toBe('function')
  })

  it('hides the Animals tab and all animal records when the display pref is off', () => {
    const prefs = defaultPreferences()
    prefs.categories.animals.display = false
    const v = buildView(baseState({ preferences: prefs }), actions, t)
    expect(v.showAnimalsTab).toBe(false)
    expect(v.visibleAnimals).toHaveLength(0)
  })

  it('shows the Animals tab by default (display on)', () => {
    const v = buildView(baseState(), actions, t)
    expect(v.showAnimalsTab).toBe(true)
  })

  it('filters the animal list by search across name/breed/color/location', () => {
    const v = buildView(baseState({ search: 'michi' }), actions, t)
    expect(v.visibleAnimals).toHaveLength(1)
    expect(v.visibleAnimals[0].id).toBe('animal-2')
  })
})

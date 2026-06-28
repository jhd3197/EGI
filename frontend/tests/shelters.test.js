// Shelter view-derivation tests (plan-20). buildView() must turn raw shelter
// records into display-ready capacity bars, accepting/full + trust badges,
// service/supply/population chip lists, and a working filter chip set.
import { describe, expect, it, vi } from 'vitest'
import { buildView } from '../src/lib/view.js'

const baseState = (over = {}) => ({
  authed: true, selectedDisasterId: 'd1', screen: 'shelters',
  overrides: {}, people: [], filter: 'all', search: '', customDisasters: [], disasters: [],
  reportDraft: {}, reportType: 'missing', reportStep: 0,
  shelterFilters: { hasSpace: false, pets: false, medical: false, supplies: false },
  shelterUpdates: [],
  institutions: [
    { id: 's1', disaster_id: 'd1', name: 'Refugio Uno', kind: 'refugio',
      capacity_total: 100, capacity_available: 30, accepting_new: true, trust: 'official',
      services: ['beds', 'pets'], supply_needs: ['water'], target_populations: ['minors'] },
  ],
  ...over,
})

const actions = { openShelter: vi.fn(), setShelterFilter: vi.fn(), setShelterTab: vi.fn() }

describe('shelter list derivation', () => {
  it('computes occupancy percent and a capacity label', () => {
    const v = buildView(baseState(), actions, (k, vars) => (vars ? `${k}:${JSON.stringify(vars)}` : k))
    const s = v.institutions[0]
    expect(s.occ).toBe(70) // 100 total - 30 available
    expect(s.occPct).toBe(70)
    expect(s.accepting).toBe(true)
    expect(s.services).toEqual(['beds', 'pets'])
    expect(s.supplyNeeds).toEqual(['water'])
    expect(typeof s.open).toBe('function')
  })

  it('flags a full shelter as not accepting with a red bar', () => {
    const v = buildView(
      baseState({ institutions: [{ id: 'x', disaster_id: 'd1', name: 'Lleno', kind: 'refugio',
        capacity_total: 50, capacity_available: 0, accepting_new: false, trust: 'crowd' }] }),
      actions, (k) => k,
    )
    const s = v.institutions[0]
    expect(s.occPct).toBe(100)
    expect(s.accepting).toBe(false)
    expect(s.barColor).toBe('#C2272D')
  })

  it('exposes four toggleable filter chips wired to setShelterFilter', () => {
    const v = buildView(baseState({ shelterFilters: { hasSpace: true, pets: false, medical: false, supplies: false } }), actions, (k) => k)
    expect(v.shelterFilters.map((f) => f.key)).toEqual(['hasSpace', 'pets', 'medical', 'supplies'])
    expect(v.shelterFilters[0].active).toBe(true)
    v.shelterFilters[1].onClick()
    expect(actions.setShelterFilter).toHaveBeenCalledWith('pets')
  })

  it('builds the open shelter detail from shelterDetailId', () => {
    const v = buildView(baseState({ screen: 'shelterDetail', shelterDetailId: 's1' }), actions, (k) => k)
    expect(v.isShelterDetail).toBe(true)
    expect(v.shelterDetail.name).toBe('Refugio Uno')
    expect(v.shelterDetail.targetPopulations).toEqual(['minors'])
  })

  it('decorates update feed entries with role badges', () => {
    const state = baseState({
      shelterUpdates: [{ id: 'u1', message: 'hola', author_role: 'official', author_name: 'Staff', created_at: '2026-06-01T10:00:00Z' }],
    })
    const v = buildView(state, actions, (k) => k)
    expect(v.shelterUpdates[0].roleLabel).toBe('shelterDetail.role.official')
    expect(v.shelterUpdates[0].when).toBe('2026-06-01 10:00')
    expect(v.shelterUpdates[0].author).toBe('Staff')
  })
})

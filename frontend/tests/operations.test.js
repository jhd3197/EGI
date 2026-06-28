// SAR operations view-derivation tests. buildView() must gate the operations
// screen, decorate the operations list (status chips, sort active-first, open
// handler) and the open operation detail (per-sector status helpers + the
// sectorsNeedingAttention / recentFound dashboard helpers).
import { describe, expect, it, vi } from 'vitest'
import { buildView } from '../src/lib/view.js'

const baseState = (over = {}) => ({
  authed: true, selectedDisasterId: 'd1', screen: 'operations',
  overrides: {}, people: [], filter: 'all', search: '', customDisasters: [], disasters: [],
  reportDraft: {}, reportType: 'missing', reportStep: 0,
  shelterFilters: { hasSpace: false, pets: false, medical: false, supplies: false },
  shelterUpdates: [], institutions: [],
  myVolunteer: {},
  operations: [
    { id: 'op2', disaster_id: 'd1', name: 'Cerrada', status: 'closed', sector_count: 1, volunteer_count: 0, person_count: 0 },
    { id: 'op1', disaster_id: 'd1', name: 'Río', status: 'active', sector_count: 3, volunteer_count: 2, person_count: 5 },
  ],
  operationDetail: null,
  ...over,
})

const actions = { openOperation: vi.fn() }
const t = (k) => k

describe('SAR operations view derivation', () => {
  it('gates the operations screen', () => {
    const v = buildView(baseState(), actions, t)
    expect(v.isOperations).toBe(true)
    expect(v.isOperationDetail).toBe(false)
  })

  it('decorates operations with a status label + open handler and sorts active first', () => {
    const v = buildView(baseState(), actions, t)
    expect(v.operations.map((o) => o.id)).toEqual(['op1', 'op2']) // active before closed
    const first = v.operations[0]
    expect(first.statusLabel).toBe('operations.status.active')
    expect(typeof first.open).toBe('function')
    first.open()
    expect(actions.openOperation).toHaveBeenCalledWith('op1')
  })

  it('filters operations to the active disaster', () => {
    const v = buildView(baseState({
      operations: [{ id: 'x', disaster_id: 'other', name: 'Otra', status: 'active' }],
    }), actions, t)
    expect(v.operations).toHaveLength(0)
  })

  it('decorates the open operation detail with per-sector status helpers', () => {
    const v = buildView(baseState({
      screen: 'operationDetail', selectedOperationId: 'op1',
      operationDetail: {
        id: 'op1', name: 'Río', status: 'active',
        sectors: [
          { id: 's1', name: 'A', status: 'cleared' },
          { id: 's2', name: 'B', status: 'needs_recheck' },
        ],
        persons: [{ id: 'p1', name: 'Ana', status: 'missing' }],
        field_reports: [{ id: 'f1', type: 'found' }, { id: 'f2', type: 'sighting' }],
      },
    }), actions, t)
    expect(v.isOperationDetail).toBe(true)
    const od = v.operationDetail
    expect(od.sectors[0].statusColor).toBe('#1B7A45')
    expect(od.sectors[0].statusLabel).toBe('operations.sector.cleared')
    expect(od.sectors[1].statusColor).toBe('#C2272D')
    expect(od.sectorsNeedingAttention.map((s) => s.id)).toEqual(['s2'])
    expect(od.recentFound.map((r) => r.id)).toEqual(['f1'])
    expect(od.persons[0].statusLabel).toBe('operations.pstatus.missing')
    expect(od.joined).toBe(false)
  })

  it('marks the detail joined when a volunteer id is held for the operation', () => {
    const v = buildView(baseState({
      screen: 'operationDetail',
      myVolunteer: { op1: 'vol-1' },
      operationDetail: { id: 'op1', name: 'Río', status: 'active', sectors: [] },
    }), actions, t)
    expect(v.operationDetail.joined).toBe(true)
    expect(v.operationDetail.myVolunteerId).toBe('vol-1')
  })
})

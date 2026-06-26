// Offline cache/queue contract tests (the plan's "IndexedDB read/write/delete").
// The real store.js persists to localStorage (not IndexedDB); these exercise the
// pure helpers in src/lib/offlineQueue.js against jsdom's localStorage.
import { beforeEach, describe, expect, it } from 'vitest'
import { queuePending, readPending, clearPending } from '../src/lib/offlineQueue.js'

const KEY = 'egi.pendingRecords'

// TEST DATA — NOT REAL
const sampleRecord = {
  id: 'EGI-TEST',
  disaster_id: 'd000000',
  name: 'Juan Pérez de prueba',
  cedula: 'V-00000000',
  status: 'missing',
  source: 'web',
}

describe('offlineQueue (egi.pendingRecords contract)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('reads an empty queue as []', () => {
    expect(readPending(KEY)).toEqual([])
  })

  it('writes a record and reads it back', () => {
    const len = queuePending(KEY, sampleRecord)
    expect(len).toBe(1)
    expect(readPending(KEY)).toEqual([sampleRecord])
    // Persisted as a JSON array under the expected key.
    expect(JSON.parse(localStorage.getItem(KEY))).toHaveLength(1)
  })

  it('appends multiple records in order', () => {
    queuePending(KEY, sampleRecord)
    // TEST DATA — NOT REAL
    const second = { ...sampleRecord, id: 'EGI-TEST2', status: 'safe' }
    const len = queuePending(KEY, second)
    expect(len).toBe(2)
    const stored = readPending(KEY)
    expect(stored[0].id).toBe('EGI-TEST')
    expect(stored[1].id).toBe('EGI-TEST2')
  })

  it('clears the queue', () => {
    queuePending(KEY, sampleRecord)
    clearPending(KEY)
    expect(localStorage.getItem(KEY)).toBeNull()
    expect(readPending(KEY)).toEqual([])
  })

  it('returns [] for corrupt JSON', () => {
    localStorage.setItem(KEY, '{not valid json')
    expect(readPending(KEY)).toEqual([])
  })
})

// IndexedDB offline-cache tests for the real helpers in src/lib/db.js.
// Uses fake-indexeddb to provide a spec-compliant indexedDB under jsdom/node.
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  metaGet, metaSet, getAllPeople, putPeople,
  queuePendingRecord, readPendingRecords, clearPendingRecords, countPendingRecords,
  getCachedData, setCachedData, migrateFromLocalStorage,
} from '../src/lib/db.js'

// TEST DATA — NOT REAL
const sampleRecord = {
  id: 'EGI-TEST',
  disaster_id: 'd000000',
  name: 'Juan Pérez de prueba',
  cedula: 'V-00000000',
  status: 'missing',
  source: 'web',
}

// db.js memoizes the open promise per module load; deleting the DB between tests
// keeps state clean (fake-indexeddb honors deleteDatabase). The cached handle
// still points at the same DB name, which gets re-created lazily on next access.
beforeEach(async () => {
  await new Promise((resolve) => {
    const req = indexedDB.deleteDatabase('egi')
    req.onsuccess = req.onerror = req.onblocked = () => resolve()
  })
  localStorage.clear()
})

describe('db.js — people', () => {
  it('reads an empty people store as []', async () => {
    expect(await getAllPeople()).toEqual([])
  })

  it('bulk puts and reads people back', async () => {
    await putPeople([sampleRecord, { ...sampleRecord, id: 'EGI-TEST2', status: 'safe' }])
    const all = await getAllPeople()
    expect(all).toHaveLength(2)
    expect(all.map((p) => p.id).sort()).toEqual(['EGI-TEST', 'EGI-TEST2'])
  })
})

describe('db.js — pendingRecords', () => {
  it('queues, reads, counts and clears', async () => {
    expect(await readPendingRecords()).toEqual([])
    const count = await queuePendingRecord(sampleRecord)
    expect(count).toBe(1)
    expect(await countPendingRecords()).toBe(1)
    expect(await readPendingRecords()).toEqual([sampleRecord])
    await clearPendingRecords()
    expect(await readPendingRecords()).toEqual([])
    expect(await countPendingRecords()).toBe(0)
  })
})

describe('db.js — meta', () => {
  it('roundtrips a value', async () => {
    expect(await metaGet('lastSync')).toBeUndefined()
    await metaSet('lastSync', '2026-06-26T00:00:00Z')
    expect(await metaGet('lastSync')).toBe('2026-06-26T00:00:00Z')
  })

  it('merges cached data per disaster', async () => {
    await setCachedData('d000000', { people: [sampleRecord] })
    await setCachedData('d000000', { activity: [{ x: 1 }] })
    const cached = await getCachedData('d000000')
    expect(cached.people).toHaveLength(1)
    expect(cached.activity).toHaveLength(1)
    expect(cached.ts).toBeTruthy()
  })
})

describe('db.js — migrateFromLocalStorage', () => {
  it('moves old localStorage keys into IndexedDB and removes them', async () => {
    localStorage.setItem('egi.pendingRecords', JSON.stringify([sampleRecord]))
    localStorage.setItem('egi.myReports', JSON.stringify([{ name: 'Yo' }]))
    localStorage.setItem('egi.lastSync', '2026-01-01T00:00:00Z')
    localStorage.setItem('egi.data.global', JSON.stringify({ people: [sampleRecord] }))
    localStorage.setItem('egi_api_url', 'https://example.test') // must be preserved

    await migrateFromLocalStorage()

    expect(await readPendingRecords()).toEqual([sampleRecord])
    expect(await metaGet('myReports')).toEqual([{ name: 'Yo' }])
    expect(await metaGet('lastSync')).toBe('2026-01-01T00:00:00Z')
    expect((await getCachedData('global')).people).toHaveLength(1)

    // Old keys removed, api url kept, flag set.
    expect(localStorage.getItem('egi.pendingRecords')).toBeNull()
    expect(localStorage.getItem('egi.data.global')).toBeNull()
    expect(localStorage.getItem('egi_api_url')).toBe('https://example.test')
    expect(await metaGet('migrated')).toBe(true)
  })

  it('is a no-op on the second run', async () => {
    await metaSet('migrated', true)
    localStorage.setItem('egi.pendingRecords', JSON.stringify([sampleRecord]))
    await migrateFromLocalStorage()
    // Not migrated because the flag was already set.
    expect(await readPendingRecords()).toEqual([])
    expect(localStorage.getItem('egi.pendingRecords')).not.toBeNull()
  })
})

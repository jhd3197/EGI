// IndexedDB-backed offline cache for useEgi (src/store.js).
// A tiny dependency-free promise wrapper. DB `egi`, version 1, with stores:
//   people          (keyPath id)      — cached registry rows
//   reports         (keyPath id)      — reserved for cached person reports
//   pendingRecords  (keyPath id)      — queued person records for POST /sync
//   pendingReports  (autoIncrement)   — queued {personId, report} notes
//   meta            (keyPath key)     — lastSync, session, myReports, data.<id>
// Every helper resolves to a sensible default instead of throwing, mirroring the
// try/catch style of the old localStorage code, so the app degrades gracefully.

const DB_NAME = 'egi'
const DB_VERSION = 1
const STORES = ['people', 'reports', 'pendingRecords', 'pendingReports', 'meta']

const nowIso = () => new Date().toISOString()
const hasIDB = () => typeof indexedDB !== 'undefined'

let dbPromise = null

function openDb() {
  if (!hasIDB()) return Promise.resolve(null)
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains('people')) db.createObjectStore('people', { keyPath: 'id' })
        if (!db.objectStoreNames.contains('reports')) db.createObjectStore('reports', { keyPath: 'id' })
        if (!db.objectStoreNames.contains('pendingRecords')) db.createObjectStore('pendingRecords', { keyPath: 'id' })
        if (!db.objectStoreNames.contains('pendingReports')) db.createObjectStore('pendingReports', { autoIncrement: true })
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' })
      }
      req.onsuccess = () => {
        const db = req.result
        // Close (and let the cache reopen) if another connection deletes/upgrades
        // the DB, so deleteDatabase isn't blocked by our long-lived handle.
        db.onversionchange = () => { db.close(); dbPromise = null }
        resolve(db)
      }
      req.onerror = () => { console.error('[EGI] indexedDB open failed', req.error); resolve(null) }
    } catch (e) {
      console.error('[EGI] indexedDB open threw', e)
      resolve(null)
    }
  })
  return dbPromise
}

// Run `fn(store)` inside a transaction and resolve to `fallback` on any error.
// `fn` may return an IDBRequest (its result is resolved) or a plain value.
function withStore(name, mode, fn, fallback) {
  return openDb().then((db) => {
    if (!db) return fallback
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(name, mode)
        const store = tx.objectStore(name)
        let result = fallback
        const ret = fn(store, (v) => { result = v })
        if (ret && typeof ret.onsuccess !== 'undefined') {
          ret.onsuccess = () => { result = ret.result }
          ret.onerror = () => { console.error('[EGI] idb request failed', ret.error) }
        }
        tx.oncomplete = () => resolve(result)
        tx.onerror = () => { console.error('[EGI] idb tx failed', tx.error); resolve(fallback) }
        tx.onabort = () => { console.error('[EGI] idb tx aborted', tx.error); resolve(fallback) }
      } catch (e) {
        console.error('[EGI] idb tx threw', e)
        resolve(fallback)
      }
    })
  }).catch((e) => { console.error(e); return fallback })
}

// ---------- meta (key/value) ----------
export function metaGet(key) {
  return withStore('meta', 'readonly', (store, set) => {
    const req = store.get(key)
    req.onsuccess = () => set(req.result ? req.result.value : undefined)
    return null
  }, undefined)
}

export function metaSet(key, value) {
  return withStore('meta', 'readwrite', (store) => {
    store.put({ key, value })
    return null
  }, undefined)
}

// ---------- people ----------
export function getAllPeople() {
  return withStore('people', 'readonly', (store, set) => {
    const req = store.getAll()
    req.onsuccess = () => set(req.result || [])
    return null
  }, [])
}

export function putPeople(records) {
  return withStore('people', 'readwrite', (store) => {
    for (const r of records || []) { if (r && r.id != null) store.put(r) }
    return null
  }, undefined)
}

// ---------- per-disaster cached data (stored in meta as data.<id|global>) ----------
const dataKey = (disasterId) => 'data.' + (disasterId || 'global')

export function getCachedData(disasterId) {
  return metaGet(dataKey(disasterId)).then((v) => v || null)
}

// Merge a patch into the cached blob like the old code ({...cur, ...patch, ts}).
export function setCachedData(disasterId, patch) {
  const key = dataKey(disasterId)
  return metaGet(key).then((cur) =>
    metaSet(key, { ...(cur || {}), ...patch, ts: nowIso() })
  )
}

// ---------- pending records (POST /sync queue) ----------
export function queuePendingRecord(record) {
  return withStore('pendingRecords', 'readwrite', (store, set) => {
    if (record && record.id != null) store.put(record)
    const req = store.count()
    req.onsuccess = () => set(req.result)
    return null
  }, 0)
}

export function readPendingRecords() {
  return withStore('pendingRecords', 'readonly', (store, set) => {
    const req = store.getAll()
    req.onsuccess = () => set(req.result || [])
    return null
  }, [])
}

export function clearPendingRecords() {
  return withStore('pendingRecords', 'readwrite', (store) => {
    store.clear()
    return null
  }, undefined)
}

export function countPendingRecords() {
  return withStore('pendingRecords', 'readonly', (store, set) => {
    const req = store.count()
    req.onsuccess = () => set(req.result)
    return null
  }, 0)
}

// ---------- pending per-person reports (notes) ----------
// item = { personId, report }. Read returns [{ key, personId, report }].
export function queuePendingReport(item) {
  return withStore('pendingReports', 'readwrite', (store) => {
    store.add(item)
    return null
  }, undefined)
}

export function readPendingReports() {
  return withStore('pendingReports', 'readonly', (store, set) => {
    const req = store.openCursor()
    const out = []
    req.onsuccess = () => {
      const cur = req.result
      if (cur) { out.push({ key: cur.key, personId: cur.value.personId, report: cur.value.report }); cur.continue() }
      else set(out)
    }
    return null
  }, [])
}

// Replace the whole queue with `list` (array of { personId, report }).
export function setPendingReports(list) {
  return withStore('pendingReports', 'readwrite', (store) => {
    store.clear()
    for (const item of list || []) store.add({ personId: item.personId, report: item.report })
    return null
  }, undefined)
}

export function clearPendingReports() {
  return withStore('pendingReports', 'readwrite', (store) => {
    store.clear()
    return null
  }, undefined)
}

// ---------- one-time migration from the old localStorage contract ----------
const safeParse = (raw, fallback) => {
  if (!raw) return fallback
  try { return JSON.parse(raw) } catch (e) { return fallback }
}

export async function migrateFromLocalStorage() {
  if (!hasIDB() || typeof localStorage === 'undefined') return
  const already = await metaGet('migrated')
  if (already) return

  try {
    // pendingRecords array → individual records
    const pendingRecords = safeParse(localStorage.getItem('egi.pendingRecords'), [])
    if (Array.isArray(pendingRecords)) {
      for (const r of pendingRecords) { if (r && r.id != null) await queuePendingRecord(r) }
    }

    // pendingReports array → individual entries
    const pendingReports = safeParse(localStorage.getItem('egi.pendingReports'), [])
    if (Array.isArray(pendingReports)) {
      for (const item of pendingReports) await queuePendingReport({ personId: item.personId, report: item.report })
    }

    // egi.data.* → meta data.*
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.indexOf('egi.data.') === 0) {
        const blob = safeParse(localStorage.getItem(k), null)
        if (blob) await metaSet('data.' + k.slice('egi.data.'.length), blob)
      }
    }

    // myReports / lastSync / session → meta
    const myReports = safeParse(localStorage.getItem('egi.myReports'), null)
    if (myReports != null) await metaSet('myReports', myReports)
    const lastSync = localStorage.getItem('egi.lastSync')
    if (lastSync) await metaSet('lastSync', lastSync)
    const session = safeParse(localStorage.getItem('egi.session'), null)
    if (session != null) await metaSet('session', session)

    // Remove migrated keys (keep egi_api_url).
    const toRemove = ['egi.pendingRecords', 'egi.pendingReports', 'egi.myReports', 'egi.lastSync', 'egi.session']
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i)
      if (k && (k.indexOf('egi.data.') === 0 || toRemove.includes(k))) localStorage.removeItem(k)
    }
  } catch (e) {
    console.error('[EGI] migrateFromLocalStorage failed', e)
  }

  await metaSet('migrated', true)
}

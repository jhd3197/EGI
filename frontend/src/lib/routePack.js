// Offline routing-pack cache + road-route computation (plan-21, Phase 2).
//
// A routing pack is a small cached road-network graph (see modules/routing.py).
// We keep downloaded packs in a SEPARATE IndexedDB database (`egi-routing`) —
// the same pattern as src/lib/tileCache.js — so bulky graph blobs never bloat or
// version-churn the main `egi` data cache. Every helper resolves to a safe
// default instead of throwing, so routing degrades to the straight-line fallback
// when IndexedDB or the worker is unavailable.
import { packCovers } from './routeGraph.js'
import { makeBlockedEdge } from './hazards.js'

const DB_NAME = 'egi-routing'
const DB_VERSION = 1
const STORE = 'packs'

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
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id' })
      }
      req.onsuccess = () => {
        const db = req.result
        db.onversionchange = () => { db.close(); dbPromise = null }
        resolve(db)
      }
      req.onerror = () => { console.error('[EGI] routing idb open failed', req.error); resolve(null) }
    } catch (e) {
      console.error('[EGI] routing idb open threw', e)
      resolve(null)
    }
  })
  return dbPromise
}

function withStore(mode, fn, fallback) {
  return openDb().then((db) => {
    if (!db) return fallback
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(STORE, mode)
        const store = tx.objectStore(STORE)
        let result = fallback
        fn(store, (v) => { result = v })
        tx.oncomplete = () => resolve(result)
        tx.onerror = () => { console.error('[EGI] routing tx failed', tx.error); resolve(fallback) }
        tx.onabort = () => { console.error('[EGI] routing tx aborted', tx.error); resolve(fallback) }
      } catch (e) {
        console.error('[EGI] routing tx threw', e)
        resolve(fallback)
      }
    })
  }).catch((e) => { console.error(e); return fallback })
}

// ---- local pack store --------------------------------------------------------

// Lightweight metadata for every locally-cached pack (no graph payload).
export function listLocalPacks() {
  return withStore('readonly', (store, set) => {
    const req = store.getAll()
    req.onsuccess = () => set((req.result || []).map((r) => ({
      id: r.id, region: r.graph && r.graph.region, bbox: r.graph && r.graph.bbox,
      version: r.graph && r.graph.version, savedAt: r.savedAt,
    })))
  }, [])
}

// The full graph JSON for a cached pack, or null when absent.
export function getLocalPack(id) {
  return withStore('readonly', (store, set) => {
    const req = store.get(id)
    req.onsuccess = () => set(req.result ? req.result.graph : null)
  }, null)
}

export function savePack(id, graphJson) {
  return withStore('readwrite', (store) => {
    store.put({ id, graph: graphJson, savedAt: new Date().toISOString() })
  }, undefined)
}

export function clearPacks() {
  return withStore('readwrite', (store) => { store.clear() }, undefined)
}

// ---- server fetch ------------------------------------------------------------

// GET the pack index (metadata) from the server, optionally filtered by region.
// Returns an array of metadata records, or [] on any failure (offline-safe).
export async function fetchPackIndex(apiBase, region) {
  try {
    const qs = region ? '?region=' + encodeURIComponent(region) : ''
    const res = await fetch((apiBase || '') + '/routing/packs' + qs)
    if (!res.ok) return []
    const data = await res.json()
    return data.records || []
  } catch (e) {
    console.error('[EGI] fetchPackIndex failed', e)
    return []
  }
}

// GET the full graph for a pack, store it locally, and return the graph (or
// null on failure). Idempotent: re-downloading just refreshes the cached copy.
export async function fetchAndCachePack(apiBase, packId) {
  try {
    const res = await fetch((apiBase || '') + '/routing/packs/' + encodeURIComponent(packId))
    if (!res.ok) return null
    const graph = await res.json()
    await savePack(packId, graph)
    return graph
  } catch (e) {
    console.error('[EGI] fetchAndCachePack failed', e)
    return null
  }
}

// ---- road-route computation (worker) -----------------------------------------

// Re-export so callers can do the coverage test without importing routeGraph.
export { packCovers }

// Find the first locally-cached pack whose bbox covers BOTH points, returning
// its full graph, or null. Used to decide whether an offline road route is
// possible before spinning up the worker.
export async function findCoveringLocalPack(from, to) {
  const local = await listLocalPacks()
  for (const meta of local) {
    if (packCovers({ bbox: meta.bbox }, from) && packCovers({ bbox: meta.bbox }, to)) {
      const graph = await getLocalPack(meta.id)
      if (graph) return graph
    }
  }
  return null
}

// Compute a road-following route in a Web Worker, with a timeout fallback so a
// runaway search can never hang the UI. Resolves to the worker result
// ({ ok, polyline, meters, nodes } | { ok:false, reason }). The worker is always
// terminated afterwards. When workers are unavailable (e.g. test/SSR), it falls
// back to running the pure core inline.
//
// `hazards` (optional, plan-21 Phase 4) is a list of hazard records; when given,
// the route avoids edges that fall inside an ACTIVE hazard. Omit it (or pass
// null) for the original hazard-free behaviour.
export function computeRoadRoute(graph, from, to, hazards = null, timeoutMs = 4000) {
  return new Promise((resolve) => {
    let settled = false
    const done = (v) => { if (!settled) { settled = true; resolve(v) } }
    const inline = ({ aStar }) =>
      done(aStar(graph, from, to, { blockedEdge: makeBlockedEdge(hazards) }))

    if (typeof Worker === 'undefined') {
      // No worker support: run the pure core inline so routing still works.
      import('./routeGraph.js').then(inline).catch(() => done({ ok: false, reason: 'no_worker' }))
      return
    }

    let worker
    try {
      worker = new Worker(new URL('../workers/routeWorker.js', import.meta.url), { type: 'module' })
    } catch (e) {
      console.error('[EGI] worker spawn failed', e)
      import('./routeGraph.js').then(inline).catch(() => done({ ok: false, reason: 'no_worker' }))
      return
    }

    const cleanup = () => { try { worker.terminate() } catch { /* ignore */ } }
    const timer = setTimeout(() => { done({ ok: false, reason: 'timeout' }); cleanup() }, timeoutMs)

    worker.onmessage = (e) => { clearTimeout(timer); done(e.data); cleanup() }
    worker.onerror = (e) => {
      clearTimeout(timer)
      console.error('[EGI] route worker error', e)
      done({ ok: false, reason: 'worker_error' })
      cleanup()
    }
    worker.postMessage({ graph, from, to, hazards })
  })
}

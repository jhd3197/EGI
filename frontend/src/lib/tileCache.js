// Offline map-tile cache (plan-10). A small, dependency-free IndexedDB store of
// OpenStreetMap raster tiles so a pre-downloaded region keeps rendering with no
// connectivity — the same offline-first principle as src/lib/db.js, kept in a
// SEPARATE database (`egi-tiles`) so bulk binary tiles never bloat or version-
// churn the main `egi` data cache.
//
// Tiles are keyed `z/x/y`. Each record is { k, blob }. Every helper resolves to
// a safe default instead of throwing, so the map degrades gracefully when
// IndexedDB is unavailable (private mode, quota, etc.).

const DB_NAME = 'egi-tiles'
const DB_VERSION = 1
const STORE = 'tiles'

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
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'k' })
      }
      req.onsuccess = () => {
        const db = req.result
        db.onversionchange = () => { db.close(); dbPromise = null }
        resolve(db)
      }
      req.onerror = () => { console.error('[EGI] tile idb open failed', req.error); resolve(null) }
    } catch (e) {
      console.error('[EGI] tile idb open threw', e)
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
        tx.onerror = () => { console.error('[EGI] tile tx failed', tx.error); resolve(fallback) }
        tx.onabort = () => { console.error('[EGI] tile tx aborted', tx.error); resolve(fallback) }
      } catch (e) {
        console.error('[EGI] tile tx threw', e)
        resolve(fallback)
      }
    })
  }).catch((e) => { console.error(e); return fallback })
}

export const tileKey = (z, x, y) => `${z}/${x}/${y}`

// Return a cached tile Blob for `key`, or null when absent.
export function getTile(key) {
  return withStore('readonly', (store, set) => {
    const req = store.get(key)
    req.onsuccess = () => set(req.result ? req.result.blob : null)
  }, null)
}

export function putTile(key, blob) {
  return withStore('readwrite', (store) => { store.put({ k: key, blob }) }, undefined)
}

export function countTiles() {
  return withStore('readonly', (store, set) => {
    const req = store.count()
    req.onsuccess = () => set(req.result)
  }, 0)
}

export function clearTiles() {
  return withStore('readwrite', (store) => { store.clear() }, undefined)
}

// ---- region prefetch ----------------------------------------------------
// Slippy-map math: convert lat/lon to tile x/y at a given zoom.
// https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
function lonToTileX(lon, z) {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, z))
}
function latToTileY(lat, z) {
  const rad = (lat * Math.PI) / 180
  return Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * Math.pow(2, z)
  )
}

// Enumerate the tile coords covering `bounds` (Leaflet LatLngBounds-like with
// getWest/East/North/South) across [minZoom, maxZoom], capped at `maxTiles` so a
// careless download can't try to fetch a whole continent. Returns an array of
// { z, x, y }.
export function tilesForBounds(bounds, minZoom, maxZoom, maxTiles = 1500) {
  const out = []
  const west = bounds.getWest(), east = bounds.getEast()
  const north = bounds.getNorth(), south = bounds.getSouth()
  for (let z = minZoom; z <= maxZoom; z++) {
    const x0 = lonToTileX(west, z), x1 = lonToTileX(east, z)
    const y0 = latToTileY(north, z), y1 = latToTileY(south, z)
    for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) {
      for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) {
        out.push({ z, x, y })
        if (out.length >= maxTiles) return out
      }
    }
  }
  return out
}

// Fetch and store every tile covering `bounds`. `urlFor({z,x,y})` builds the tile
// URL. Calls `onProgress(done, total)` as it goes. Skips already-cached tiles and
// swallows individual failures (best-effort). Returns { saved, total }.
export async function prefetchRegion(bounds, minZoom, maxZoom, urlFor, onProgress) {
  const coords = tilesForBounds(bounds, minZoom, maxZoom)
  const total = coords.length
  let saved = 0
  for (let i = 0; i < coords.length; i++) {
    const c = coords[i]
    const key = tileKey(c.z, c.x, c.y)
    try {
      const existing = await getTile(key)
      if (!existing) {
        const res = await fetch(urlFor(c))
        if (res.ok) { await putTile(key, await res.blob()); saved++ }
      }
    } catch (e) { /* best-effort: skip this tile */ }
    if (onProgress) onProgress(i + 1, total)
  }
  return { saved, total }
}

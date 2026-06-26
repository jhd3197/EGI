// meshBridge — thin, framework-agnostic wrapper over the native Android host.
// When the PWA runs inside the EGI Android app, the native side injects a
// `window.EgiNative` @JavascriptInterface and calls `window.EgiMesh.onEvent`.
// In a plain browser none of this exists, so every export degrades to a no-op.
// Nothing here ever throws.

const hasNative = () => typeof window !== 'undefined' && !!window.EgiNative

export const isMeshAvailable = () =>
  hasNative() && (() => { try { return window.EgiNative.isAvailable() } catch { return false } })()

export function getDeviceId() {
  try { return hasNative() ? window.EgiNative.getDeviceId() : null }
  catch { return null }
}

export function startMesh() {
  if (!isMeshAvailable()) { console.debug('[mesh] startMesh: native unavailable, no-op'); return }
  try { window.EgiNative.startMesh() } catch (e) { console.debug('[mesh] startMesh failed', e) }
}

export function stopMesh() {
  if (!isMeshAvailable()) { console.debug('[mesh] stopMesh: native unavailable, no-op'); return }
  try { window.EgiNative.stopMesh() } catch (e) { console.debug('[mesh] stopMesh failed', e) }
}

export function syncMesh() {
  if (!isMeshAvailable()) { console.debug('[mesh] syncMesh: native unavailable, no-op'); return }
  try { window.EgiNative.syncMesh() } catch (e) { console.debug('[mesh] syncMesh failed', e) }
}

// Parsed `{running,peers,queued,lastSync,deviceId}` or null when unavailable/bad.
export function getMeshStatus() {
  if (!isMeshAvailable()) return null
  try {
    const raw = window.EgiNative.getStatus()
    return raw ? JSON.parse(raw) : null
  } catch (e) { console.debug('[mesh] getStatus failed', e); return null }
}

// Array of person payloads from the on-device Room DB; [] on any failure.
export function getLocalRecords() {
  if (!isMeshAvailable()) return []
  try {
    const raw = window.EgiNative.getLocalRecords()
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch (e) { console.debug('[mesh] getLocalRecords failed', e); return [] }
}

// Multiplexed event bus: native calls `window.EgiMesh.onEvent(jsonString)`.
// We install the dispatcher once and fan out to all subscribers.
const subscribers = new Set()
let installed = false

function installEventSink() {
  if (installed || typeof window === 'undefined') return
  installed = true
  const existing = window.EgiMesh
  window.EgiMesh = {
    ...(existing || {}),
    onEvent(jsonString) {
      let evt
      try { evt = typeof jsonString === 'string' ? JSON.parse(jsonString) : jsonString }
      catch (e) { console.debug('[mesh] bad event payload', e); return }
      for (const fn of subscribers) {
        try { fn(evt) } catch (e) { console.debug('[mesh] subscriber threw', e) }
      }
    },
  }
}

// Register `handler(event)`; returns an unsubscribe fn. Safe in any browser.
export function onMeshEvent(handler) {
  if (typeof handler !== 'function') return () => {}
  try {
    installEventSink()
    subscribers.add(handler)
  } catch (e) { console.debug('[mesh] onMeshEvent failed', e); return () => {} }
  return () => { try { subscribers.delete(handler) } catch { /* ignore */ } }
}

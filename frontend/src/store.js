// useEgi — central app state, offline cache/sync, and actions.
// This replaces the original `Component extends DCLogic` class. State lives in
// one object (mirroring the old this.state) with a setState-style merge helper.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  isMeshAvailable, onMeshEvent, syncMesh, getMeshStatus,
  startMesh, stopMesh, getMeshConsent, setMeshConsent,
  peerIdFromEvent, peerIdsFromStatus, mergeRecentPeer,
} from './lib/meshBridge'
import {
  metaGet, metaSet, getCachedData, setCachedData,
  queuePendingRecord, readPendingRecords, clearPendingRecords, countPendingRecords,
  queuePendingReport, readPendingReports, setPendingReports,
  migrateFromLocalStorage,
} from './lib/db'
import { normalizeCedula } from './lib/person'
import { buildSharePayload } from './lib/routeShare'
import {
  defaultPreferences, mergeServerPreferences, toServerPayload,
} from './lib/preferences'

// API base: same-origin by default (FastAPI serves the built app and the API
// together; the Vite dev server proxies these routes to the Python server).
// Override for a remote server with: localStorage.setItem('egi_api_url', 'https://…')
const API_URL =
  (typeof window !== 'undefined' && localStorage.getItem('egi_api_url')) || ''

// Operator (moderator) bearer token. SESSION-ONLY: held in this module-level
// variable, never written to localStorage / IndexedDB / metaSet, so a device
// leak (disk, backup) cannot expose it. It lives only for this page session.
let operatorToken = ''
// Lightweight pub/sub so the moderation UI can react to token changes (e.g. a
// 401 clearing the token) without threading the value through buildView().
const operatorTokenListeners = new Set()
const notifyOperatorToken = (payload) => {
  for (const cb of operatorTokenListeners) {
    try { cb(payload) } catch (e) { /* ignore listener errors */ }
  }
}

const initialState = {
  authed: false,
  user: null,
  selectedDisasterId: null,
  addOpen: false,
  customDisasters: [],
  authPromptOpen: false,
  pending: null,
  draftName: '',
  draftRegion: '',
  draftType: 'flood',
  screen: 'home',
  personId: 'p1',
  filter: 'all',
  search: '',
  // Dedicated cédula search (Phase 6)
  cedulaQuery: '',
  cedulaActive: false,
  cedulaSearching: false,
  cedulaResults: [],
  // Cursor pagination of the people list (Phase 7)
  searchCursor: null,
  searchHasMore: false,
  searchLoading: false,
  online: typeof navigator !== 'undefined' ? navigator.onLine : false,
  reportOpen: false,
  reportStep: 0,
  reportType: 'missing',
  reportDone: false,
  queue: 0,
  savedCase: 'EGI-3M9X1',
  overrides: {},
  vw: typeof window !== 'undefined' ? window.innerWidth : 1200,
  people: [],
  institutions: [],
  myReports: [],
  activity: [],
  disasters: [],
  loading: false,
  reportDraft: {},
  pendingReportCount: 0,
  dupClusters: [],
  dupLoading: false,
  meshAvailable: false,
  meshStatus: null,
  meshConsent: false,
  meshWarnOpen: false,
  // Recently-seen mesh device ids ({ id, lastSeen }), most-recent-first, capped.
  // Accumulated in-memory from native peer_synced/status events; not persisted.
  recentPeers: [],
  // Low-literacy / panic "Modo simple" — a local, device-only UI toggle
  // (plan-14, Phase 5). Persisted in IndexedDB like `operator`.
  simpleMode: false,
  // Moderator (operator) mode — a local, device-only toggle (Phase 9).
  operator: false,
  // Whether an operator bearer token is set THIS session (the token value
  // itself is never persisted — it lives in the module-level operatorToken).
  operatorTokenSet: false,
  modPending: [],
  modLoading: false,
  modStats: null,
  // Shelter & refugee information hub (plan-20).
  shelterDetailId: null,        // open shelter detail (null = list view)
  shelterTab: 'info',           // 'info' | 'updates'
  shelterUpdates: [],           // feed for the open shelter
  shelterUpdatesLoading: false,
  shelterFilters: { hasSpace: false, pets: false, medical: false, supplies: false },
  shelterCheckins: [],          // private check-in list (operator view)
  shelterCheckedIn: null,       // { shelterId, name } for the post-checkin toast
  shelterClaimMsg: null,        // result message after claiming a shelter
  pendingShelterCount: 0,       // queued offline check-ins/updates
  // Offline routing (plan-21). `directionsTarget` preselects a destination when
  // the screen is opened from a shelter/person ({ lat, lon, name }); null = let
  // the user pick. The route math + history live in lib/directions.js.
  directionsTarget: null,
  // Computed road-following polyline ([[lat,lon],...]) from the offline routing
  // worker (plan-21 Phase 2). Drawn on MapScreen; null = no road route to show.
  routePolyline: null,
  // Hazard zones for the active disaster (plan-21 Phase 4): flood/landslide/fire/
  // blocked_road/unsafe_zone areas used for routing avoidance + map overlays.
  // Fetched from GET /hazards, cached offline; new crowd reports POST /hazards.
  hazards: [],
  // Routes shared by nearby devices/responders (plan-21 Phase 5): a responder
  // shares a computed (verified-safe) route; others see them as suggestions on
  // the Directions screen + a map preview. Fetched from GET /routes/shared,
  // cached offline; new shares POST /routes/share (offline-queued).
  sharedRoutes: [],
  // Evacuation corridors for the active disaster (plan-21 Phase 6): named
  // open/congested/closed paths (drive/walk/transit) drawn as map overlays.
  // Fetched from GET /corridors, cached offline; read-only on the client.
  corridors: [],
  // User preferences (plan-24): per-category display/notify/relay toggles +
  // global settings (near-me radius, quiet hours). Local-first in IndexedDB
  // `meta.preferences`, synced to the server for logged-in users. Shapes live
  // in lib/preferences.js.
  preferences: defaultPreferences(),
  // Operation subscriptions (plan-24 Phase 6): [{operation_id, muted, ...}] for
  // the logged-in user. Drives the mute/subscribe controls; server-backed only
  // (a guest has no account to scope subscriptions to).
  subscriptions: [],
}

const nowIso = () => new Date().toISOString()

// Number of steps in the report flow, by report type. Missing keeps the full
// 5-step flow; sighting and safe are fast flows with fewer steps.
export const stepCountFor = (type) =>
  type === 'sighting' ? 3 : type === 'safe' ? 2 : 5

export function useEgi() {
  const [state, setStateRaw] = useState(initialState)
  // Keep a ref to the latest state so async callbacks read fresh values
  // without being re-created on every render.
  const stateRef = useRef(state)
  stateRef.current = state

  // setState(patch | updaterFn) — merges into state like React class setState.
  const setState = useCallback((patch) => {
    setStateRaw((prev) => {
      const next = typeof patch === 'function' ? patch(prev) : patch
      return { ...prev, ...next }
    })
  }, [])

  const get = () => stateRef.current

  // ---------- API helpers ----------
  const api = useCallback(async (path, options = {}) => {
    const res = await fetch(API_URL + path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  }, [])

  // Bearer header for operator-only calls. Empty object when no token is set,
  // so the `api` helper spreads nothing and public reads stay unauthenticated.
  const authHeaders = useCallback(
    () => (operatorToken ? { Authorization: 'Bearer ' + operatorToken } : {}),
    [],
  )

  // ---------- operator (moderator) token: session-only ----------
  const isOperatorTokenSet = useCallback(() => !!operatorToken, [])

  const setOperatorToken = useCallback((token) => {
    operatorToken = (token || '').trim()
    const set = !!operatorToken
    setState({ operatorTokenSet: set })
    notifyOperatorToken({ set, invalid: false })
  }, [setState])

  // invalid=true marks a 401-driven clear so the UI can show a "bad token" hint.
  const clearOperatorToken = useCallback((invalid = false) => {
    operatorToken = ''
    setState({ operatorTokenSet: false })
    notifyOperatorToken({ set: false, invalid: invalid === true })
  }, [setState])

  // Subscribe to token changes (returns an unsubscribe fn). Used by the
  // moderation screen to re-prompt when a 401 wipes the token.
  const subscribeOperatorToken = useCallback((cb) => {
    operatorTokenListeners.add(cb)
    return () => operatorTokenListeners.delete(cb)
  }, [])

  // Detect a 401 from an operator call: wipe the token so the UI re-prompts.
  const isAuthError = (e) => String(e).includes('401')
  const handleOperatorAuthError = useCallback(() => {
    clearOperatorToken(true)
  }, [clearOperatorToken])

  const saveCachedData = useCallback(async (patch) => {
    try {
      await setCachedData(get().selectedDisasterId, patch)
    } catch (e) { console.error(e) }
  }, [])

  const loadCachedData = useCallback(async () => {
    try {
      const cached = await getCachedData(get().selectedDisasterId)
      if (cached) {
        setState({
          people: cached.people || [],
          institutions: cached.institutions || [],
          activity: cached.activity || [],
          disasters: cached.disasters || [],
          hazards: cached.hazards || [],
          sharedRoutes: cached.sharedRoutes || [],
          corridors: cached.corridors || [],
        })
      }
      const mine = await metaGet('myReports')
      if (mine) setState({ myReports: mine })
      const count = await countPendingRecords()
      setState({ queue: count })
    } catch (e) { console.error(e) }
  }, [setState])

  const mergeRecords = useCallback((records) => {
    setState((s) => {
      const byId = {}
      for (const r of s.people) byId[r.id] = r
      for (const r of records) {
        if (!r.disaster_id || r.disaster_id === s.selectedDisasterId) byId[r.id] = r
      }
      return { people: Object.values(byId) }
    })
  }, [setState])

  const fetchAll = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    setState({ loading: true })
    const disasterId = get().selectedDisasterId
    const since = (await metaGet('lastSync')) || '1970-01-01T00:00:00Z'
    try {
      const sync = await api('/sync?since=' + encodeURIComponent(since))
      if (sync.records && sync.records.length) mergeRecords(sync.records)

      // Phase 7: request only the first page; walk further pages via loadMore().
      const qs = new URLSearchParams()
      qs.set('limit', '50')
      if (disasterId) qs.set('disaster_id', disasterId)
      const persons = await api('/persons?' + qs.toString())
      const records = persons.records || []
      console.log('[EGI] fetched', records.length, 'persons for disaster', disasterId)
      setState({
        people: records,
        searchCursor: persons.next_cursor || null,
        searchHasMore: !!persons.has_more,
      })
      await saveCachedData({ people: records })
      await metaSet('lastSync', nowIso())
    } catch (err) {
      console.error('[EGI] fetchAll failed', err) // offline or server error: keep cache
    } finally {
      setState({ loading: false })
    }
  }, [api, mergeRecords, saveCachedData, setState])

  // Fetch hazard zones for the active disaster (plan-21 Phase 4). Offline-safe
  // (keeps the cache); caches the full set per-disaster so the map overlays and
  // routing avoidance keep working offline. Defined here (before chooseDisaster)
  // so the disaster lifecycle can call it without a temporal-dead-zone hazard.
  const fetchHazards = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const S = get()
    try {
      const qs = new URLSearchParams()
      if (S.selectedDisasterId) qs.set('disaster_id', S.selectedDisasterId)
      const res = await api('/hazards?' + qs.toString())
      const records = res.records || []
      setState({ hazards: records })
      await saveCachedData({ hazards: records })
    } catch (err) {
      console.error('[EGI] fetchHazards failed', err) // keep cache
    }
  }, [api, saveCachedData, setState])

  // Fetch routes shared by nearby devices for the active disaster (plan-21
  // Phase 5). Offline-safe (keeps the cache on failure); caches per-disaster so
  // the Directions suggestions keep working offline. Mirrors fetchHazards.
  const fetchSharedRoutes = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const S = get()
    try {
      const qs = new URLSearchParams()
      if (S.selectedDisasterId) qs.set('disaster_id', S.selectedDisasterId)
      const res = await api('/routes/shared?' + qs.toString())
      const records = res.records || []
      setState({ sharedRoutes: records })
      await saveCachedData({ sharedRoutes: records })
    } catch (err) {
      console.error('[EGI] fetchSharedRoutes failed', err) // keep cache
    }
  }, [api, saveCachedData, setState])

  // Fetch evacuation corridors for the active disaster (plan-21 Phase 6).
  // Offline-safe (keeps the cache on failure); caches per-disaster so the map
  // overlays + directions hints keep working offline. Mirrors fetchHazards.
  const fetchCorridors = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const S = get()
    try {
      const qs = new URLSearchParams()
      if (S.selectedDisasterId) qs.set('disaster_id', S.selectedDisasterId)
      const res = await api('/corridors?' + qs.toString())
      const records = res.records || []
      setState({ corridors: records })
      await saveCachedData({ corridors: records })
    } catch (err) {
      console.error('[EGI] fetchCorridors failed', err) // keep cache
    }
  }, [api, saveCachedData, setState])

  const syncNow = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const pending = await readPendingRecords()
      if (pending.length) {
        await api('/sync', { method: 'POST', body: JSON.stringify({ records: pending }) })
        await clearPendingRecords()
        setState({ queue: 0 })
      }
      // Flush any queued per-person notes/updates to their endpoints.
      const pendingReports = await readPendingReports()
      if (pendingReports.length) {
        const stillPending = []
        for (const item of pendingReports) {
          try {
            await api('/persons/' + encodeURIComponent(item.personId) + '/reports', {
              method: 'POST',
              body: JSON.stringify(item.report),
            })
          } catch (e) {
            stillPending.push({ personId: item.personId, report: item.report }) // keep on failure
          }
        }
        await setPendingReports(stillPending)
        setState({ pendingReportCount: stillPending.length })
      }
      await fetchAll()
    } catch (err) {
      console.error('Sync failed', err)
    }
  }, [api, fetchAll, setState])

  const queueRecord = useCallback(async (record) => {
    try {
      const count = await queuePendingRecord(record)
      setState({ queue: count })
      if (navigator.onLine) syncNow()
    } catch (e) { console.error(e) }
  }, [setState, syncNow])

  // Trigger one native BLE-mesh exchange round (then cloud sync if online),
  // then refresh local state. No-op in a plain browser via the bridge guards.
  const meshSync = useCallback(() => {
    syncMesh()
    setTimeout(() => { setState({ meshStatus: getMeshStatus() }); fetchAll() }, 400)
  }, [fetchAll, setState])

  const refreshMeshStatus = useCallback(() => {
    setState({ meshStatus: getMeshStatus() })
  }, [setState])

  // Turn the mesh on. First use must clear the privacy warning: nearby strangers
  // can receive public registry data. Consent is persisted (native or local).
  const enableMesh = useCallback(() => {
    if (!getMeshConsent()) { setState({ meshWarnOpen: true }); return }
    startMesh()
    setTimeout(() => setState({ meshStatus: getMeshStatus() }), 300)
  }, [setState])

  const disableMesh = useCallback(() => {
    stopMesh()
    setTimeout(() => setState({ meshStatus: getMeshStatus() }), 300)
  }, [setState])

  const toggleMesh = useCallback(() => {
    const running = !!(get().meshStatus && get().meshStatus.running)
    if (running) disableMesh()
    else enableMesh()
  }, [enableMesh, disableMesh])

  // Privacy warning dialog outcome.
  const acceptMeshWarning = useCallback(() => {
    setMeshConsent(true)
    startMesh()
    setState({ meshConsent: true, meshWarnOpen: false })
    setTimeout(() => setState({ meshStatus: getMeshStatus() }), 300)
  }, [setState])

  const declineMeshWarning = useCallback(() => setState({ meshWarnOpen: false }), [setState])

  // ---------- user preferences (plan-24) ----------
  // Local-first: every change persists to IndexedDB `meta.preferences` and, for
  // a logged-in user (operator/user bearer token set this session), is pushed to
  // the server best-effort. On app open we pull the server copy and merge it with
  // last-write-wins so a change made on another device propagates here.
  const persistPreferences = useCallback(async (prefs) => {
    try { await metaSet('preferences', prefs) } catch (e) { /* ignore */ }
  }, [])

  // Push the full local snapshot to the server. Best-effort + auth-gated: with no
  // token (guest) the call 401s and we silently keep local-only behaviour.
  const pushPreferences = useCallback(async (prefs) => {
    if (!operatorToken) return
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const res = await api('/preferences', {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(toServerPayload(prefs)),
      })
      // The server echoes the merged result; fold it back so a concurrent change
      // from another device is reflected immediately.
      if (res && res.categories) {
        setState((s) => {
          const merged = mergeServerPreferences(s.preferences, res)
          persistPreferences(merged)
          return { preferences: merged }
        })
      }
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      /* offline / server error: local copy already persisted */
    }
  }, [api, authHeaders, handleOperatorAuthError, persistPreferences, setState])

  // Pull the server copy and merge (last-write-wins). Best-effort + auth-gated.
  const loadPreferencesFromServer = useCallback(async () => {
    if (!operatorToken) return
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const res = await api('/preferences', { headers: authHeaders() })
      if (res && res.categories) {
        setState((s) => {
          const merged = mergeServerPreferences(s.preferences, res)
          persistPreferences(merged)
          return { preferences: merged }
        })
      }
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      /* keep local copy */
    }
  }, [api, authHeaders, handleOperatorAuthError, persistPreferences, setState])

  // Send a test notification to this user's own devices (plan-24 Phase 4).
  // Requires a logged-in token; returns the server result or a {none:true}
  // marker when no auth/device is present so the UI can show a gentle hint.
  const sendNotifyTest = useCallback(async () => {
    if (!operatorToken) return { recipients: 0, none: true }
    try {
      return await api('/preferences/notify-test', { method: 'POST', headers: authHeaders() })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return { recipients: 0, none: true } }
      return { recipients: 0, error: true }
    }
  }, [api, authHeaders, handleOperatorAuthError])

  // ---------- operation subscriptions (plan-24 Phase 6) ----------
  // All server-backed + auth-gated: a guest has no account to scope to, so these
  // no-op without a token. Best-effort; a 401 wipes the token to re-prompt.
  const fetchSubscriptions = useCallback(async () => {
    if (!operatorToken) return
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const res = await api('/subscriptions', { headers: authHeaders() })
      setState({ subscriptions: res.records || [] })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
    }
  }, [api, authHeaders, handleOperatorAuthError, setState])

  const subscribeOperation = useCallback(async (opId) => {
    if (!operatorToken || !opId) return
    try {
      await api('/operations/' + encodeURIComponent(opId) + '/subscribe', { method: 'POST', headers: authHeaders() })
      fetchSubscriptions()
    } catch (e) { if (isAuthError(e)) handleOperatorAuthError() }
  }, [api, authHeaders, handleOperatorAuthError, fetchSubscriptions])

  const unsubscribeOperation = useCallback(async (opId) => {
    if (!operatorToken || !opId) return
    try {
      await api('/operations/' + encodeURIComponent(opId) + '/unsubscribe', { method: 'POST', headers: authHeaders() })
      fetchSubscriptions()
    } catch (e) { if (isAuthError(e)) handleOperatorAuthError() }
  }, [api, authHeaders, handleOperatorAuthError, fetchSubscriptions])

  const muteOperation = useCallback(async (opId, muted) => {
    if (!operatorToken || !opId) return
    try {
      await api('/operations/' + encodeURIComponent(opId) + '/mute?muted=' + (muted ? 'true' : 'false'), { method: 'POST', headers: authHeaders() })
      fetchSubscriptions()
    } catch (e) { if (isAuthError(e)) handleOperatorAuthError() }
  }, [api, authHeaders, handleOperatorAuthError, fetchSubscriptions])

  // Toggle one dimension (display|notify|relay) of one category.
  const setCategoryPref = useCallback((category, dimension, value) => {
    setState((s) => {
      const cur = s.preferences.categories[category] || {}
      const nextCat = { ...cur, [dimension]: value, updatedAt: nowIso() }
      const next = {
        ...s.preferences,
        categories: { ...s.preferences.categories, [category]: nextCat },
      }
      persistPreferences(next)
      pushPreferences(next)
      return { preferences: next }
    })
  }, [setState, persistPreferences, pushPreferences])

  // Patch a global setting (radius, quietStart, quietEnd, batch, home*).
  const setSetting = useCallback((key, value) => {
    setState((s) => {
      const next = {
        ...s.preferences,
        settings: { ...s.preferences.settings, [key]: value, updatedAt: nowIso() },
      }
      persistPreferences(next)
      pushPreferences(next)
      return { preferences: next }
    })
  }, [setState, persistPreferences, pushPreferences])

  // ---------- duplicates (moderator review) ----------
  const fetchDuplicates = useCallback(async () => {
    setState({ dupLoading: true })
    try {
      const res = await api('/duplicates/pending')
      setState({ dupClusters: res.clusters || [], dupLoading: false })
    } catch (e) {
      console.error('[EGI] fetchDuplicates failed', e)
      setState({ dupLoading: false })
    }
  }, [api, setState])

  const mergeDuplicate = useCallback(async (clusterId, canonicalId) => {
    try {
      await api('/duplicates/' + encodeURIComponent(clusterId) + '/merge', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ canonical_id: canonicalId }),
      })
      await fetchDuplicates()
      fetchAll()
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      console.error('[EGI] mergeDuplicate failed', e)
    }
  }, [api, authHeaders, handleOperatorAuthError, fetchDuplicates, fetchAll])

  const rejectDuplicate = useCallback(async (clusterId) => {
    try {
      await api('/duplicates/' + encodeURIComponent(clusterId) + '/reject', { method: 'POST', headers: authHeaders() })
      await fetchDuplicates()
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      console.error('[EGI] rejectDuplicate failed', e)
    }
  }, [api, authHeaders, handleOperatorAuthError, fetchDuplicates])

  // ---------- moderation queue (operator review, Phase 9) ----------
  // All of these need the server: moderation is never an offline operation.
  // When offline we surface an empty/gentle state rather than crashing.
  const fetchModerationPending = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      setState({ modPending: [], modLoading: false })
      return
    }
    setState({ modLoading: true })
    try {
      const res = await api('/moderation/pending')
      setState({ modPending: res.records || [], modLoading: false })
    } catch (e) {
      console.error('[EGI] fetchModerationPending failed', e)
      setState({ modLoading: false })
    }
  }, [api, setState])

  const fetchModerationStats = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const res = await api('/moderation/stats')
      setState({ modStats: res })
    } catch (e) {
      console.error('[EGI] fetchModerationStats failed', e)
    }
  }, [api, setState])

  // Operational-intelligence dashboard (plan-13): global totals + the selected
  // operation's situational stats. Both endpoints are viewer-gated server-side,
  // so the operator token is sent when set but is not required on a dev/open
  // server. Best-effort: a failure leaves the last snapshot in place.
  const fetchDashboard = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    setState({ dashLoading: true })
    try {
      const global = await api('/stats/global', { headers: authHeaders() })
      const opId = get().selectedDisasterId
      let operation = null
      if (opId) {
        try {
          operation = await api('/stats/operations/' + encodeURIComponent(opId), { headers: authHeaders() })
        } catch { /* operation may have no stats yet */ }
      }
      setState({ dashboard: { global, operation }, dashLoading: false })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); setState({ dashLoading: false }); return }
      console.error('[EGI] fetchDashboard failed', e)
      setState({ dashLoading: false })
    }
  }, [api, authHeaders, setState, handleOperatorAuthError])

  // Approve/reject a pending record, then refresh the queue, the stats, and the
  // main people list (so an approved row becomes visible in the registry).
  // NOTE on provenance: there is no server-side operator auth yet, so the client
  // cannot — and must not — fabricate a moderator identity. The server stamps
  // updated_at on approve/reject; that timestamp is the only honest provenance
  // we can record here. No analytics, no client-invented "reviewer" field.
  const approveRecord = useCallback(async (id) => {
    try {
      await api('/moderation/' + encodeURIComponent(id) + '/approve', { method: 'POST', headers: authHeaders() })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      console.error('[EGI] approveRecord failed', e)
    }
    await fetchModerationPending()
    fetchModerationStats()
    fetchAll()
  }, [api, authHeaders, handleOperatorAuthError, fetchModerationPending, fetchModerationStats, fetchAll])

  const rejectRecord = useCallback(async (id) => {
    try {
      await api('/moderation/' + encodeURIComponent(id) + '/reject', { method: 'POST', headers: authHeaders() })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      console.error('[EGI] rejectRecord failed', e)
    }
    await fetchModerationPending()
    fetchModerationStats()
    fetchAll()
  }, [api, authHeaders, handleOperatorAuthError, fetchModerationPending, fetchModerationStats, fetchAll])

  // Flip operator (moderator) mode. Persisted in IndexedDB `meta` so it survives
  // reloads on this device only — it is not a remote/auth flag.
  const toggleOperator = useCallback(() => {
    setState((s) => {
      const next = !s.operator
      metaSet('operator', next)
      // Leaving operator mode wipes the in-memory bearer token (it's never
      // persisted anyway) and returns home so the now-hidden screen isn't left
      // dangling.
      if (!next) {
        operatorToken = ''
        notifyOperatorToken({ set: false, invalid: false })
      }
      return {
        operator: next,
        operatorTokenSet: next ? s.operatorTokenSet : false,
        screen: (!next && s.screen === 'moderation') ? 'home' : s.screen,
      }
    })
  }, [setState])

  // Flip the low-literacy "Modo simple". Persisted in IndexedDB `meta` so it
  // survives reloads on this device only — it is not a remote/auth flag. Always
  // returns to the home screen so the simplified home is what the user sees.
  const toggleSimpleMode = useCallback(() => {
    setState((s) => {
      const next = !s.simpleMode
      metaSet('simpleMode', next)
      return { simpleMode: next, screen: 'home', reportOpen: false }
    })
  }, [setState])

  // ---------- session persistence ----------
  const persist = useCallback(async (patch) => {
    try {
      const cur = (await metaGet('session')) || {}
      const next = { ...cur, ...patch }
      await metaSet('session', next)
      document.cookie =
        'egi_session=' + encodeURIComponent((next.user && next.user.mode) || '') + ';path=/;max-age=2592000'
    } catch (e) { /* ignore */ }
  }, [])

  // Derive initials (max 2 chars) from a free-text alias.
  const initialsFor = (name) =>
    (name || '')
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join('') || 'IN'

  // Two honest sessions: a named alias (stored locally only) or an anonymous
  // guest. No remote auth — nothing leaves the device on sign-in.
  const userFor = (mode, alias) => {
    const name = (alias || '').trim()
    if (mode === 'alias' && name) {
      return { name, email: 'Alias en este dispositivo', initials: initialsFor(name), mode: 'alias' }
    }
    return { name: 'Invitado', email: 'Sesión en este dispositivo', initials: 'IN', mode: 'guest' }
  }

  // signIn handles any pending guarded action captured before auth.
  const signIn = useCallback((mode, alias) => {
    const user = userFor(mode, alias)
    persist({ user })
    const pending = get().pending
    setState({ authed: true, user, authPromptOpen: false, pending: null })
    if (pending && pending.kind === 'report') openReport(pending.type)
    else if (pending && pending.kind === 'markSafe') markSafe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persist, setState])

  const signOut = useCallback(() => {
    try {
      metaSet('session', {})
      document.cookie = 'egi_session=;path=/;max-age=0'
    } catch (e) { /* ignore */ }
    setState({ authed: false, user: null, selectedDisasterId: null, screen: 'home' })
  }, [setState])

  // ---------- disasters ----------
  const chooseDisaster = useCallback((id) => {
    persist({ disasterId: id })
    setState({ selectedDisasterId: id, screen: 'home', people: [], institutions: [], activity: [], hazards: [], sharedRoutes: [], corridors: [] })
    // load cache + refetch on the next tick once state has settled
    setTimeout(() => { loadCachedData(); fetchAll(); fetchHazards(); fetchSharedRoutes(); fetchCorridors() }, 0)
  }, [persist, setState, loadCachedData, fetchAll, fetchHazards, fetchSharedRoutes, fetchCorridors])

  const changeDisaster = useCallback(() => {
    persist({ disasterId: null })
    setState({ selectedDisasterId: null })
  }, [persist, setState])

  const addDisaster = useCallback(() => {
    const S = get()
    const name = (S.draftName || '').trim() || 'Nueva emergencia'
    const region = (S.draftRegion || '').trim() || 'Por definir'
    const tagMap = { flood: 'INUND', quake: 'SISMO', landslide: 'DESLA' }
    const id = 'd' + Date.now().toString().slice(-6)
    const d = { id, name, region, type: S.draftType, tag: tagMap[S.draftType] || 'EVENT', date: 'hoy', affected: '0', shelters: 0, status: 'Activa', custom: true }
    persist({ disasterId: id })
    setState((s) => ({
      customDisasters: [...s.customDisasters, d],
      addOpen: false,
      selectedDisasterId: id,
      screen: 'home',
      draftName: '',
      draftRegion: '',
      draftType: 'flood',
    }))
  }, [persist, setState])

  // ---------- report flow ----------
  const openReport = useCallback((t) => {
    setState({ reportOpen: true, reportStep: 0, reportType: t, reportDone: false })
  }, [setState])
  const closeReport = useCallback(() => setState({ reportOpen: false }), [setState])
  const nextStep = useCallback(() => setState((s) => ({ reportStep: Math.min(stepCountFor(s.reportType) - 1, s.reportStep + 1) })), [setState])
  const prevStep = useCallback(() => setState((s) => ({ reportStep: Math.max(0, s.reportStep - 1) })), [setState])
  const updateDraft = useCallback((field, value) => {
    setState((s) => ({ reportDraft: { ...s.reportDraft, [field]: value } }))
  }, [setState])

  const submitReport = useCallback(() => {
    const S = get()
    const draft = S.reportDraft || {}
    const caseId = 'EGI-' + Math.random().toString(36).slice(2, 6).toUpperCase()
    const record = {
      id: caseId,
      disaster_id: S.selectedDisasterId,
      name: draft.name || 'Sin nombre',
      cedula: draft.cedula || '',
      status: S.reportType === 'sighting' ? 'sighted' : S.reportType,
      gender: draft.gender || 'M',
      age: draft.age ? parseInt(draft.age, 10) : null,
      location: draft.location || '',
      last_seen_date: draft.lastSeenDate || '',
      clothes: draft.clothes || '',
      notes: draft.notes || '',
      reporter_name: draft.reporterName || (S.user && S.user.name) || 'Invitado',
      reporter_relation: draft.relation || '',
      reporter_country: draft.country || '',
      contact: draft.contact || '',
      source: 'web',
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    queueRecord(record)
    // Auto-subscribe a logged-in reporter to this operation (plan-24 Phase 6),
    // so they get its updates without opting in by hand. No-op for guests.
    if (S.selectedDisasterId) subscribeOperation(S.selectedDisasterId)
    const newMine = [{ name: record.name, sub: 'Esperando conexión · ahora', state: 'queued' }, ...S.myReports]
    setState({ reportDone: true, savedCase: caseId, myReports: newMine, reportDraft: {} })
    metaSet('myReports', newMine)
  }, [queueRecord, setState, subscribeOperation])

  const markSafe = useCallback(() => {
    setState((s) => ({ overrides: { ...s.overrides, [s.personId]: 'safe' } }))
  }, [setState])

  // One-tap self check-in: register the current user as 'safe' without the
  // full multi-step report flow.
  const checkInSelf = useCallback(() => {
    const S = get()
    const caseId = 'EGI-' + Math.random().toString(36).slice(2, 6).toUpperCase()
    const name = (S.user && S.user.name) || 'Yo'
    const record = {
      id: caseId,
      disaster_id: S.selectedDisasterId,
      name,
      status: 'safe',
      reporter_name: (S.user && S.user.name) || 'Invitado',
      source: 'web',
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    queueRecord(record)
    const newMine = [{ name: name + ' · Estoy bien', sub: 'A salvo · ahora', state: 'queued' }, ...S.myReports]
    setState({ reportDone: false, savedCase: caseId, myReports: newMine, checkedInSafe: true })
    metaSet('myReports', newMine)
    setTimeout(() => setState({ checkedInSafe: false }), 4000)
  }, [queueRecord, setState])

  // Add a note/update (PFIF-style report) to a person. Optimistically appends
  // to the local timeline; queues for retry if the endpoint is unavailable.
  const addPersonReport = useCallback((personId, text, confidence = 'witness') => {
    const note = (text || '').trim()
    if (!note) return
    const S = get()
    const report = {
      person_id: personId,
      note,
      author_name: (S.user && S.user.name) || 'Invitado',
      status: null,
      confidence,
      source: 'web',
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    // Optimistically append to the person's timeline in local state.
    setState((s) => ({
      people: s.people.map((p) => {
        if (p.id !== personId) return p
        const updates = p.updates ? [...p.updates] : []
        return { ...p, updates: [{ t: note, s: 'Ahora · ' + report.author_name, k: p.status || 'missing' }, ...updates] }
      }),
    }))
    const queueLocally = async () => {
      try {
        await queuePendingReport({ personId, report })
        const q = await readPendingReports()
        setState({ pendingReportCount: q.length })
      } catch (e) { console.error(e) }
    }
    if (typeof navigator !== 'undefined' && !navigator.onLine) { queueLocally(); return }
    api('/persons/' + encodeURIComponent(personId) + '/reports', {
      method: 'POST',
      body: JSON.stringify(report),
    }).catch(() => { queueLocally() }) // 404 / offline: fall back to the queue
  }, [api, setState])

  // Map a server report row (PFIF note) into a timeline `updates` entry.
  const reportToUpdate = useCallback((r) => {
    const who = r.author_name || 'Anónimo'
    const when = (r.created_at || r.createdAt || '').slice(0, 10)
    return { t: r.note || '(sin nota)', s: [when, who].filter(Boolean).join(' · '), k: r.status || 'missing' }
  }, [])

  // ---------- misc ui ----------
  const setScreen = useCallback((screen) => setState({ screen, reportOpen: false }), [setState])
  // Open a person and pull their reports (incl. notes that arrived via the mesh
  // and reached the cloud) so the timeline reflects every peer's contribution.
  const openPerson = useCallback((id) => {
    setState({ screen: 'detail', personId: id })
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    api('/persons/' + encodeURIComponent(id) + '/reports')
      .then((res) => {
        const rows = res.records || []
        if (!rows.length) return
        const updates = rows.map(reportToUpdate)
        setState((s) => ({
          people: s.people.map((p) => (p.id === id ? { ...p, updates } : p)),
        }))
      })
      .catch(() => { /* offline / no reports: keep optimistic timeline */ })
  }, [api, reportToUpdate, setState])
  const setFilter = useCallback((f) => setState({ filter: f }), [setState])
  const setSearch = useCallback((value) => setState({ search: value }), [setState])

  // ---------- pagination (Phase 7) ----------
  // Fetch the next page of people and append (deduped by id) to state.people,
  // preserving the active disaster, then persist the grown list to the cache.
  const loadMore = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const S = get()
    if (!S.searchHasMore || S.searchLoading || !S.searchCursor) return
    setState({ searchLoading: true })
    try {
      const qs = new URLSearchParams()
      qs.set('limit', '50')
      qs.set('cursor', S.searchCursor)
      if (S.selectedDisasterId) qs.set('disaster_id', S.selectedDisasterId)
      const res = await api('/persons?' + qs.toString())
      const records = res.records || []
      // Merge by id (same pattern as mergeRecords) so re-fetches don't dup.
      const disasterId = get().selectedDisasterId
      const byId = {}
      for (const r of get().people) byId[r.id] = r
      for (const r of records) {
        if (!r.disaster_id || r.disaster_id === disasterId) byId[r.id] = r
      }
      const grown = Object.values(byId)
      setState({
        people: grown,
        searchCursor: res.next_cursor || null,
        searchHasMore: !!res.has_more,
      })
      await saveCachedData({ people: grown })
    } catch (err) {
      console.error('[EGI] loadMore failed', err)
    } finally {
      setState({ searchLoading: false })
    }
  }, [api, saveCachedData, setState])

  // ---------- cédula search (Phase 6) ----------
  const setCedulaQuery = useCallback((value) => setState({ cedulaQuery: value }), [setState])
  const clearCedula = useCallback(
    () => setState({ cedulaQuery: '', cedulaActive: false, cedulaResults: [], cedulaSearching: false }),
    [setState],
  )

  // Search by cédula. Online: ask the server (soft-normalized match). Offline (or
  // on error): filter the locally-cached people by normalized cédula in JS.
  const searchCedula = useCallback(async (value) => {
    const raw = value !== undefined ? value : get().cedulaQuery
    const query = (raw || '').trim()
    setState({ cedulaQuery: query })
    if (!query) { setState({ cedulaActive: false, cedulaResults: [] }); return }
    const norm = normalizeCedula(query)
    const localMatch = () =>
      get().people.filter((p) => p.cedula && normalizeCedula(p.cedula) === norm)

    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      setState({ cedulaActive: true, cedulaResults: localMatch() })
      return
    }
    setState({ cedulaSearching: true })
    try {
      const qs = new URLSearchParams()
      qs.set('cedula', query)
      if (get().selectedDisasterId) qs.set('disaster_id', get().selectedDisasterId)
      const res = await api('/persons?' + qs.toString())
      setState({ cedulaActive: true, cedulaResults: res.records || [], cedulaSearching: false })
    } catch (err) {
      console.error('[EGI] searchCedula failed', err) // fall back to local cache
      setState({ cedulaActive: true, cedulaResults: localMatch(), cedulaSearching: false })
    }
  }, [api, setState])
  // ---------- map / geospatial (plan-10) ----------
  // Radius search around a point via GET /persons/nearby. Merges any returned
  // records into the people list so their markers appear, and returns the raw
  // response so the map can report a count. Offline: filter cached people in JS.
  const searchNearby = useCallback(async (lat, lon, radiusM) => {
    const haversine = (aLat, aLon, bLat, bLon) => {
      const R = 6371000, toRad = (d) => (d * Math.PI) / 180
      const dLat = toRad(bLat - aLat), dLon = toRad(bLon - aLon)
      const x = Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
      return 2 * R * Math.asin(Math.sqrt(x))
    }
    const localMatch = () => ({
      records: get().people.filter(
        (p) => typeof p.lat === 'number' && typeof p.lon === 'number' &&
          haversine(lat, lon, p.lat, p.lon) <= radiusM,
      ),
    })
    if (typeof navigator !== 'undefined' && !navigator.onLine) return localMatch()
    try {
      const qs = new URLSearchParams()
      qs.set('lat', lat); qs.set('lon', lon); qs.set('radius_m', Math.round(radiusM))
      const res = await api('/persons/nearby?' + qs.toString())
      if (res.records && res.records.length) mergeRecords(res.records)
      return res
    } catch (err) {
      console.error('[EGI] searchNearby failed', err)
      return localMatch()
    }
  }, [api, mergeRecords])

  // ---------- shelters (plan-20) ----------
  // Offline queue for shelter check-ins/updates lives in IndexedDB `meta`. We
  // keep it lightweight (an array per kind) and flush it on reconnect.
  const readShelterQueue = useCallback(async () => (await metaGet('shelterQueue')) || [], [])
  const writeShelterQueue = useCallback(async (list) => {
    await metaSet('shelterQueue', list)
    setState({ pendingShelterCount: list.length })
  }, [setState])
  const queueShelterOp = useCallback(async (op) => {
    const list = await readShelterQueue()
    list.push(op)
    await writeShelterQueue(list)
  }, [readShelterQueue, writeShelterQueue])

  // Fetch shelters for the active disaster, honoring the active filters. Falls
  // back to the cache offline. Server returns JSON arrays already decoded.
  const fetchShelters = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const S = get()
    const f = S.shelterFilters
    try {
      const qs = new URLSearchParams()
      if (S.selectedDisasterId) qs.set('disaster_id', S.selectedDisasterId)
      if (f.hasSpace) qs.set('has_space', 'true')
      if (f.pets) qs.set('accepts_pets', 'true')
      if (f.medical) qs.set('has_medical', 'true')
      if (f.supplies) qs.set('needs_supplies', 'true')
      const res = await api('/shelters?' + qs.toString())
      const records = res.records || []
      // Only overwrite the cached list when no filters are active, so an empty
      // filtered result never wipes the offline-usable full list.
      const anyFilter = f.hasSpace || f.pets || f.medical || f.supplies
      setState({ institutions: records })
      if (!anyFilter && records.length) await saveCachedData({ institutions: records })
    } catch (err) {
      console.error('[EGI] fetchShelters failed', err) // keep cache
    }
  }, [api, saveCachedData, setState])

  const setShelterFilter = useCallback((key) => {
    setState((s) => ({ shelterFilters: { ...s.shelterFilters, [key]: !s.shelterFilters[key] } }))
    setTimeout(fetchShelters, 0)
  }, [setState, fetchShelters])

  const fetchShelterUpdates = useCallback(async (shelterId) => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    setState({ shelterUpdatesLoading: true })
    try {
      const res = await api('/shelters/' + encodeURIComponent(shelterId) + '/updates')
      setState({ shelterUpdates: res.records || [], shelterUpdatesLoading: false })
    } catch (err) {
      console.error('[EGI] fetchShelterUpdates failed', err)
      setState({ shelterUpdatesLoading: false })
    }
  }, [api, setState])

  // Open the shelter detail card and load its feed.
  const openShelter = useCallback((id) => {
    setState({ screen: 'shelterDetail', shelterDetailId: id, shelterTab: 'info', shelterUpdates: [] })
    fetchShelterUpdates(id)
  }, [setState, fetchShelterUpdates])

  const closeShelter = useCallback(() => {
    setState({ screen: 'shelters', shelterDetailId: null })
  }, [setState])

  const setShelterTab = useCallback((tab) => setState({ shelterTab: tab }), [setState])

  // "I am here" check-in (plan-20 §5). Optimistic + offline-queue.
  const shelterCheckin = useCallback(async (shelterId, note = '') => {
    const S = get()
    const alias = (S.user && S.user.name) || 'Invitado'
    const payload = {
      id: 'chk-' + Math.random().toString(36).slice(2, 10),
      alias, note: (note || '').trim(), source: 'web',
      createdAt: nowIso(), updatedAt: nowIso(),
    }
    const shelter = (S.institutions || []).find((i) => i.id === shelterId)
    setState({ shelterCheckedIn: { shelterId, name: shelter ? shelter.name : '' } })
    setTimeout(() => setState({ shelterCheckedIn: null }), 4000)
    const path = '/shelters/' + encodeURIComponent(shelterId) + '/checkin'
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueShelterOp({ kind: 'checkin', path, body: payload })
      return
    }
    try {
      await api(path, { method: 'POST', body: JSON.stringify(payload) })
    } catch (e) {
      await queueShelterOp({ kind: 'checkin', path, body: payload })
    }
  }, [api, setState, queueShelterOp])

  // Post an official/staff update to a shelter feed (plan-20 §3/§6). Optimistic;
  // queues offline. Author role is decided server-side from the auth context.
  const postShelterUpdate = useCallback(async (shelterId, message, extra = {}) => {
    const text = (message || '').trim()
    if (!text && !extra.occupancy_delta && !extra.services_changed) return
    const S = get()
    const payload = {
      message: text, author_name: (S.user && S.user.name) || 'Refugio',
      source: 'web', createdAt: nowIso(), ...extra,
    }
    // Optimistic prepend to the open feed.
    setState((s) => ({
      shelterUpdates: [
        { id: 'tmp-' + Date.now(), shelter_id: shelterId, message: text,
          author_name: payload.author_name, author_role: 'official',
          created_at: nowIso(), _optimistic: true },
        ...s.shelterUpdates,
      ],
    }))
    const path = '/shelters/' + encodeURIComponent(shelterId) + '/updates'
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueShelterOp({ kind: 'update', path, body: payload })
      return
    }
    try {
      await api(path, { method: 'POST', headers: authHeaders(), body: JSON.stringify(payload) })
      fetchShelterUpdates(shelterId)
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      await queueShelterOp({ kind: 'update', path, body: payload })
    }
  }, [api, authHeaders, handleOperatorAuthError, setState, queueShelterOp, fetchShelterUpdates])

  // Real-time capacity/needs patch from a verified operator (plan-20 §4/§7).
  const updateShelterCapacity = useCallback(async (shelterId, patch) => {
    const path = '/shelters/' + encodeURIComponent(shelterId) + '/capacity'
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueShelterOp({ kind: 'capacity', path, body: patch, method: 'PATCH' })
      return
    }
    try {
      const res = await api(path, { method: 'PATCH', headers: authHeaders(), body: JSON.stringify(patch) })
      setState((s) => ({ institutions: s.institutions.map((i) => (i.id === shelterId ? { ...i, ...res } : i)) }))
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      await queueShelterOp({ kind: 'capacity', path, body: patch, method: 'PATCH' })
    }
  }, [api, authHeaders, handleOperatorAuthError, setState, queueShelterOp])

  // Flush queued shelter check-ins/updates/capacity patches when back online.
  const flushShelterQueue = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    const list = await readShelterQueue()
    if (!list.length) return
    const still = []
    for (const op of list) {
      try {
        await api(op.path, {
          method: op.method || 'POST',
          // checkin + routeShare are public endpoints; the rest may need auth.
          headers: (op.kind === 'checkin' || op.kind === 'routeShare') ? {} : authHeaders(),
          body: JSON.stringify(op.body),
        })
      } catch (e) { still.push(op) }
    }
    await writeShelterQueue(still)
  }, [api, authHeaders, readShelterQueue, writeShelterQueue])

  // Operator: load the private check-in roster for a shelter.
  const fetchShelterCheckins = useCallback(async (shelterId) => {
    try {
      const res = await api('/shelters/' + encodeURIComponent(shelterId) + '/checkins', { headers: authHeaders() })
      setState({ shelterCheckins: res.records || [] })
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      console.error('[EGI] fetchShelterCheckins failed', e)
    }
  }, [api, authHeaders, handleOperatorAuthError, setState])

  // Operator: claim a shelter with a one-time token (plan-20 §9).
  const claimShelter = useCallback(async (token) => {
    try {
      const res = await api('/shelters/claim', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ token: (token || '').trim() }),
      })
      setState({ shelterClaimMsg: { ok: true, name: res.name } })
      fetchShelters()
    } catch (e) {
      if (isAuthError(e)) { handleOperatorAuthError(); return }
      setState({ shelterClaimMsg: { ok: false } })
    }
  }, [api, authHeaders, handleOperatorAuthError, setState, fetchShelters])

  // ---------- hazards (plan-21 Phase 4) ----------
  // Report a hazard (blocked road / unsafe zone / flood…). Optimistic add to
  // state.hazards (so it shows + influences routing immediately), then POST
  // /hazards; offline → queue on the shared shelter-style queue and flush on
  // reconnect. Lands reviewed=0 (moderation) for non-operators server-side.
  const reportHazard = useCallback(async ({ type, geometry, note }) => {
    const S = get()
    const payload = {
      id: 'haz-' + Math.random().toString(36).slice(2, 10),
      disaster_id: S.selectedDisasterId,
      type,
      geometry,
      note: (note || '').trim(),
      reporter_name: (S.user && S.user.name) || 'Invitado',
      source: 'web',
      reviewed: 0,
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    setState((s) => ({ hazards: [payload, ...(s.hazards || [])] }))
    const path = '/hazards'
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueShelterOp({ kind: 'hazard', path, body: payload })
      return
    }
    try {
      await api(path, { method: 'POST', body: JSON.stringify(payload) })
      fetchHazards()
    } catch (e) {
      await queueShelterOp({ kind: 'hazard', path, body: payload })
    }
  }, [api, setState, queueShelterOp, fetchHazards])

  // ---------- shared routes (plan-21 Phase 5) ----------
  // Share a computed route to nearby devices. Optimistically prepends to
  // sharedRoutes (mapped to the server's snake_case read shape so the view +
  // map work immediately), then POSTs /routes/share; offline → reuse the shared
  // shelter-style queue (kind 'routeShare') and flush on reconnect. Never throws
  // back into the UI — a failure just lands in the offline queue.
  const shareRoute = useCallback(async ({ origin, dest, polyline = null, mode = 'walk', note = '' } = {}) => {
    if (!origin || !dest) return
    const S = get()
    const alias = (S.user && S.user.name) || 'Invitado'
    const payload = buildSharePayload({
      disasterId: S.selectedDisasterId, origin, dest, polyline, mode, note, alias,
    })
    const optimistic = {
      id: 'rt-' + Math.random().toString(36).slice(2, 10),
      disaster_id: payload.disaster_id,
      origin_lat: payload.origin_lat, origin_lon: payload.origin_lon,
      dest_lat: payload.dest_lat, dest_lon: payload.dest_lon,
      dest_name: payload.dest_name, polyline: payload.polyline, mode: payload.mode,
      author_alias: payload.author_alias, note: payload.note, source: 'web',
      created_at: payload.createdAt, updated_at: payload.updatedAt,
    }
    setState((s) => ({ sharedRoutes: [optimistic, ...(s.sharedRoutes || [])] }))
    const path = '/routes/share'
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueShelterOp({ kind: 'routeShare', path, body: payload })
      return
    }
    try {
      await api(path, { method: 'POST', body: JSON.stringify(payload) })
    } catch (e) {
      await queueShelterOp({ kind: 'routeShare', path, body: payload })
    }
  }, [api, setState, queueShelterOp])

  // ---------- offline routing (plan-21) ----------
  // Open the Directions screen, optionally preselecting a destination (from a
  // shelter card, a person's last-known location, or the map). target =
  // { lat, lon, name } | null. The screen owns origin/destination/mode state.
  const openDirections = useCallback((target = null) => {
    setState({ screen: 'directions', directionsTarget: target, reportOpen: false, routePolyline: null })
  }, [setState])

  // Stash the road-following polyline computed by the offline routing worker so
  // MapScreen can draw it. `latlngs` is [[lat,lon],...] or null to clear.
  const setRoutePolyline = useCallback((latlngs) => {
    setState({ routePolyline: Array.isArray(latlngs) && latlngs.length ? latlngs : null })
  }, [setState])

  const toggleOnline = useCallback(() => setState((s) => ({ online: !s.online })), [setState])
  const setReportType = useCallback((key) => setState({ reportType: key }), [setState])
  const setDraftType = useCallback((key) => setState({ draftType: key }), [setState])
  const openAdd = useCallback(() => setState({ addOpen: true }), [setState])
  const closeAdd = useCallback(() => setState({ addOpen: false }), [setState])
  const setDraftField = useCallback((field, value) => setState({ [field]: value }), [setState])

  // ---------- lifecycle ----------
  useEffect(() => {
    const onResize = () => setState({ vw: window.innerWidth })
    const onOnline = () => { setState({ online: true }); syncNow(); flushShelterQueue() }
    const onOffline = () => setState({ online: false })
    window.addEventListener('resize', onResize)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    // Native mesh bridge: only wires up when running inside the Android host.
    let unsubscribeMesh = null

    // Migrate the old localStorage cache into IndexedDB, then load + fetch.
    // All persistence reads are async, so run them in an inner async function.
    ;(async () => {
      await migrateFromLocalStorage()

      try {
        const s = await metaGet('session')
        if (s) setState({ authed: !!s.user, user: s.user || null, selectedDisasterId: s.disasterId || null })
      } catch (e) { /* ignore */ }

      try {
        const op = await metaGet('operator')
        if (op) setState({ operator: true })
      } catch (e) { /* ignore */ }

      try {
        const simple = await metaGet('simpleMode')
        if (simple) setState({ simpleMode: true })
      } catch (e) { /* ignore */ }

      // User preferences (plan-24): load the device copy first (offline-first),
      // then merge the server copy when a logged-in token is present.
      try {
        const storedPrefs = await metaGet('preferences')
        if (storedPrefs && storedPrefs.categories) {
          setState((s) => ({ preferences: mergeServerPreferences(defaultPreferences(), storedPrefs) }))
        }
      } catch (e) { /* ignore */ }
      loadPreferencesFromServer()
      fetchSubscriptions()

      await loadCachedData()
      fetchAll()
      fetchShelters()
      fetchHazards()
      fetchSharedRoutes()
      fetchCorridors()
      flushShelterQueue()
      try {
        const q = await metaGet('shelterQueue')
        if (Array.isArray(q)) setState({ pendingShelterCount: q.length })
      } catch (e) { /* ignore */ }

      setState({ meshConsent: getMeshConsent() })
      if (isMeshAvailable()) {
        setState({ meshAvailable: true, meshStatus: getMeshStatus() })
        unsubscribeMesh = onMeshEvent((evt) => {
          if (!evt) return
          if (evt.type === 'peer_synced' || evt.type === 'status') {
            setState({ meshStatus: getMeshStatus() })
            fetchAll()
          }
          // Accumulate recently-seen device ids. peer_synced is the primary
          // source (it carries the peer address); a status event may also
          // include a device list, which we fold in when present.
          if (evt.type === 'peer_synced') {
            const id = peerIdFromEvent(evt)
            if (id) setState({ recentPeers: mergeRecentPeer(get().recentPeers, id) })
          } else if (evt.type === 'status') {
            const ids = peerIdsFromStatus(evt)
            if (ids.length) {
              let next = get().recentPeers
              for (const id of ids) next = mergeRecentPeer(next, id)
              setState({ recentPeers: next })
            }
          }
        })
      }
    })()

    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
      if (unsubscribeMesh) unsubscribeMesh()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const actions = {
    signIn, signOut, chooseDisaster, changeDisaster, addDisaster,
    openReport, closeReport, nextStep, prevStep, updateDraft, submitReport, markSafe,
    checkInSelf, addPersonReport,
    setScreen, openPerson, setFilter, setSearch, toggleOnline, setReportType, setDraftType,
    loadMore, searchCedula, setCedulaQuery, clearCedula, searchNearby,
    fetchShelters, setShelterFilter, openShelter, closeShelter, setShelterTab,
    fetchShelterUpdates, shelterCheckin, postShelterUpdate, updateShelterCapacity,
    fetchShelterCheckins, claimShelter,
    fetchHazards, reportHazard,
    fetchSharedRoutes, shareRoute,
    fetchCorridors,
    openDirections, setRoutePolyline,
    openAdd, closeAdd, setDraftField, syncNow, meshSync,
    refreshMeshStatus, enableMesh, disableMesh, toggleMesh,
    acceptMeshWarning, declineMeshWarning,
    fetchDuplicates, mergeDuplicate, rejectDuplicate,
    fetchModerationPending, fetchModerationStats, fetchDashboard, approveRecord, rejectRecord,
    toggleOperator, toggleSimpleMode,
    setOperatorToken, clearOperatorToken, isOperatorTokenSet, subscribeOperatorToken,
    setCategoryPref, setSetting, loadPreferencesFromServer, sendNotifyTest,
    fetchSubscriptions, subscribeOperation, unsubscribeOperation, muteOperation,
  }

  return { state, actions }
}

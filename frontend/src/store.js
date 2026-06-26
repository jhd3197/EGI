// useEgi — central app state, offline cache/sync, and actions.
// This replaces the original `Component extends DCLogic` class. State lives in
// one object (mirroring the old this.state) with a setState-style merge helper.
import { useCallback, useEffect, useRef, useState } from 'react'
import { isMeshAvailable, onMeshEvent, syncMesh, getMeshStatus } from './lib/meshBridge'

// API base: same-origin by default (FastAPI serves the built app and the API
// together; the Vite dev server proxies these routes to the Python server).
// Override for a remote server with: localStorage.setItem('egi_api_url', 'https://…')
const API_URL =
  (typeof window !== 'undefined' && localStorage.getItem('egi_api_url')) || ''

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
  meshAvailable: false,
  meshStatus: null,
}

const nowIso = () => new Date().toISOString()
const cacheKey = (disasterId) => 'egi.data.' + (disasterId || 'global')

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

  const saveCachedData = useCallback((patch) => {
    try {
      const key = cacheKey(get().selectedDisasterId)
      const cur = JSON.parse(localStorage.getItem(key) || '{}')
      localStorage.setItem(key, JSON.stringify({ ...cur, ...patch, ts: nowIso() }))
    } catch (e) { console.error(e) }
  }, [])

  const loadCachedData = useCallback(() => {
    try {
      const key = cacheKey(get().selectedDisasterId)
      const raw = localStorage.getItem(key)
      if (raw) {
        const cached = JSON.parse(raw)
        setState({
          people: cached.people || [],
          institutions: cached.institutions || [],
          activity: cached.activity || [],
          disasters: cached.disasters || [],
        })
      }
      const mineRaw = localStorage.getItem('egi.myReports')
      if (mineRaw) setState({ myReports: JSON.parse(mineRaw) })
      const queueRaw = localStorage.getItem('egi.pendingRecords')
      if (queueRaw) setState({ queue: JSON.parse(queueRaw).length })
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
    const since = localStorage.getItem('egi.lastSync') || '1970-01-01T00:00:00Z'
    try {
      const sync = await api('/sync?since=' + encodeURIComponent(since))
      if (sync.records && sync.records.length) mergeRecords(sync.records)

      const qs = new URLSearchParams()
      qs.set('limit', '200')
      if (disasterId) qs.set('disaster_id', disasterId)
      const persons = await api('/persons?' + qs.toString())
      const records = persons.records || []
      console.log('[EGI] fetched', records.length, 'persons for disaster', disasterId)
      setState({ people: records })
      saveCachedData({ people: records })
      localStorage.setItem('egi.lastSync', nowIso())
    } catch (err) {
      console.error('[EGI] fetchAll failed', err) // offline or server error: keep cache
    } finally {
      setState({ loading: false })
    }
  }, [api, mergeRecords, saveCachedData, setState])

  const syncNow = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return
    try {
      const pending = JSON.parse(localStorage.getItem('egi.pendingRecords') || '[]')
      if (pending.length) {
        await api('/sync', { method: 'POST', body: JSON.stringify({ records: pending }) })
        localStorage.removeItem('egi.pendingRecords')
        setState({ queue: 0 })
      }
      // Flush any queued per-person notes/updates to their endpoints.
      const pendingReports = JSON.parse(localStorage.getItem('egi.pendingReports') || '[]')
      if (pendingReports.length) {
        const stillPending = []
        for (const item of pendingReports) {
          try {
            await api('/persons/' + encodeURIComponent(item.personId) + '/reports', {
              method: 'POST',
              body: JSON.stringify(item.report),
            })
          } catch (e) {
            stillPending.push(item) // keep on failure (e.g. 404 / offline)
          }
        }
        if (stillPending.length) {
          localStorage.setItem('egi.pendingReports', JSON.stringify(stillPending))
        } else {
          localStorage.removeItem('egi.pendingReports')
        }
        setState({ pendingReportCount: stillPending.length })
      }
      await fetchAll()
    } catch (err) {
      console.error('Sync failed', err)
    }
  }, [api, fetchAll, setState])

  const queueRecord = useCallback((record) => {
    try {
      const pending = JSON.parse(localStorage.getItem('egi.pendingRecords') || '[]')
      pending.push(record)
      localStorage.setItem('egi.pendingRecords', JSON.stringify(pending))
      setState({ queue: pending.length })
      if (navigator.onLine) syncNow()
    } catch (e) { console.error(e) }
  }, [setState, syncNow])

  // Trigger one native BLE-mesh exchange round (then cloud sync if online),
  // then refresh local state. No-op in a plain browser via the bridge guards.
  const meshSync = useCallback(() => {
    syncMesh()
    setTimeout(() => { setState({ meshStatus: getMeshStatus() }); fetchAll() }, 400)
  }, [fetchAll, setState])

  // ---------- session persistence ----------
  const persist = useCallback((patch) => {
    try {
      const cur = JSON.parse(localStorage.getItem('egi.session') || '{}')
      const next = { ...cur, ...patch }
      localStorage.setItem('egi.session', JSON.stringify(next))
      document.cookie =
        'egi_session=' + encodeURIComponent((next.user && next.user.mode) || '') + ';path=/;max-age=2592000'
    } catch (e) { /* ignore */ }
  }, [])

  const userFor = (mode) =>
    mode === 'google'
      ? { name: 'Carmen Rojas', email: 'carmen.r@gmail.com', initials: 'CR', mode: 'google' }
      : { name: 'Invitado', email: 'Sesión en este dispositivo', initials: 'IN', mode: 'guest' }

  // signIn handles any pending guarded action captured before auth.
  const signIn = useCallback((mode) => {
    const user = userFor(mode)
    persist({ user })
    const pending = get().pending
    setState({ authed: true, user, authPromptOpen: false, pending: null })
    if (pending && pending.kind === 'report') openReport(pending.type)
    else if (pending && pending.kind === 'markSafe') markSafe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persist, setState])

  const signOut = useCallback(() => {
    try {
      localStorage.removeItem('egi.session')
      document.cookie = 'egi_session=;path=/;max-age=0'
    } catch (e) { /* ignore */ }
    setState({ authed: false, user: null, selectedDisasterId: null, screen: 'home' })
  }, [setState])

  // ---------- disasters ----------
  const chooseDisaster = useCallback((id) => {
    persist({ disasterId: id })
    setState({ selectedDisasterId: id, screen: 'home', people: [], institutions: [], activity: [] })
    // load cache + refetch on the next tick once state has settled
    setTimeout(() => { loadCachedData(); fetchAll() }, 0)
  }, [persist, setState, loadCachedData, fetchAll])

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
  const nextStep = useCallback(() => setState((s) => ({ reportStep: Math.min(4, s.reportStep + 1) })), [setState])
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
    const newMine = [{ name: record.name, sub: 'Esperando conexión · ahora', state: 'queued' }, ...S.myReports]
    setState({ reportDone: true, savedCase: caseId, myReports: newMine, reportDraft: {} })
    localStorage.setItem('egi.myReports', JSON.stringify(newMine))
  }, [queueRecord, setState])

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
    localStorage.setItem('egi.myReports', JSON.stringify(newMine))
    setTimeout(() => setState({ checkedInSafe: false }), 4000)
  }, [queueRecord, setState])

  // Add a note/update (PFIF-style report) to a person. Optimistically appends
  // to the local timeline; queues for retry if the endpoint is unavailable.
  const addPersonReport = useCallback((personId, text) => {
    const note = (text || '').trim()
    if (!note) return
    const S = get()
    const report = {
      person_id: personId,
      note,
      author_name: (S.user && S.user.name) || 'Invitado',
      status: null,
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
    const queueLocally = () => {
      try {
        const q = JSON.parse(localStorage.getItem('egi.pendingReports') || '[]')
        q.push({ personId, report })
        localStorage.setItem('egi.pendingReports', JSON.stringify(q))
        setState({ pendingReportCount: q.length })
      } catch (e) { console.error(e) }
    }
    if (typeof navigator !== 'undefined' && !navigator.onLine) { queueLocally(); return }
    api('/persons/' + encodeURIComponent(personId) + '/reports', {
      method: 'POST',
      body: JSON.stringify(report),
    }).catch(() => { queueLocally() }) // 404 / offline: fall back to the queue
  }, [api, setState])

  // ---------- misc ui ----------
  const setScreen = useCallback((screen) => setState({ screen, reportOpen: false }), [setState])
  const openPerson = useCallback((id) => setState({ screen: 'detail', personId: id }), [setState])
  const setFilter = useCallback((f) => setState({ filter: f }), [setState])
  const setSearch = useCallback((value) => setState({ search: value }), [setState])
  const toggleOnline = useCallback(() => setState((s) => ({ online: !s.online })), [setState])
  const setReportType = useCallback((key) => setState({ reportType: key }), [setState])
  const setDraftType = useCallback((key) => setState({ draftType: key }), [setState])
  const openAdd = useCallback(() => setState({ addOpen: true }), [setState])
  const closeAdd = useCallback(() => setState({ addOpen: false }), [setState])
  const setDraftField = useCallback((field, value) => setState({ [field]: value }), [setState])

  // ---------- lifecycle ----------
  useEffect(() => {
    const onResize = () => setState({ vw: window.innerWidth })
    const onOnline = () => { setState({ online: true }); syncNow() }
    const onOffline = () => setState({ online: false })
    window.addEventListener('resize', onResize)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    try {
      const raw = localStorage.getItem('egi.session')
      if (raw) {
        const s = JSON.parse(raw)
        if (s) setState({ authed: !!s.user, user: s.user || null, selectedDisasterId: s.disasterId || null })
      }
    } catch (e) { /* ignore */ }

    loadCachedData()
    fetchAll()

    // Native mesh bridge: only wires up when running inside the Android host.
    let unsubscribeMesh = null
    if (isMeshAvailable()) {
      setState({ meshAvailable: true, meshStatus: getMeshStatus() })
      unsubscribeMesh = onMeshEvent((evt) => {
        if (evt && (evt.type === 'peer_synced' || evt.type === 'status')) {
          setState({ meshStatus: getMeshStatus() })
          fetchAll()
        }
      })
    }

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
    openAdd, closeAdd, setDraftField, syncNow, meshSync,
  }

  return { state, actions }
}

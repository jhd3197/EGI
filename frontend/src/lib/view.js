// buildView — derives all the display-ready values the screens need from raw
// state + actions. This is a direct port of the original renderVals(): keeping
// it in one place means the components stay purely presentational.
import { STATUS, DEMO_PEOPLE, DEMO_INSTI, DEMO_MINE, DEMO_ACT, DEMO_DISASTERS } from '../data/demo.js'
import { decoratePerson } from './person.js'
import { HAZARD_META, isHazardActive } from './hazards.js'
import { routeShareLatLngs } from './routeShare.js'

// `t` is the i18n translator (key, vars) => string. A safe identity default is
// provided so existing callers/tests that don't pass one keep working.
export function buildView(state, actions, t = (k) => k) {
  const S = state

  const dec = (p) => decoratePerson(p, S.overrides, actions.openPerson, t)

  const peopleSource = S.people && S.people.length ? S.people : DEMO_PEOPLE
  const all = peopleSource.filter((p) => (p.disaster || p.disaster_id) === S.selectedDisasterId).map(dec)
  const byStatus = S.filter === 'all' ? all : all.filter((p) => p.status === S.filter)
  const q = (S.search || '').trim().toLowerCase()
  const visible = !q
    ? byStatus
    : byStatus.filter((p) =>
        [p.name, p.cedula, p.place, p.location, p.id]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(q))
      )
  const sel = all.find((p) => p.id === S.personId) || all[0]

  // Map view (plan-10): decorated people for the active disaster that carry
  // coordinates. The map screen places a status-coloured marker for each.
  const mapPeople = all.filter((p) => typeof p.lat === 'number' && typeof p.lon === 'number')

  // ----- Hazard zones (plan-21 Phase 4) -----
  // Decorate each hazard with its display colour, translated type label, an
  // `active` flag (within its time window) and an `unverified` flag (reviewed=0,
  // i.e. crowd-reported and awaiting moderation). Rejected hazards (reviewed=-1)
  // are dropped. The map overlays + routing avoidance consume `view.hazards`.
  const decorateHazard = (h) => {
    const meta = HAZARD_META[h.type] || HAZARD_META.unsafe_zone
    return {
      ...h,
      color: meta.color,
      typeLabel: t(meta.key),
      active: isHazardActive(h),
      unverified: h.reviewed !== 1,
    }
  }
  const hazards = (S.hazards || [])
    .filter((h) => h && h.geometry && h.reviewed !== -1)
    .map(decorateHazard)

  // ----- Shared routes (plan-21 Phase 5) -----
  // Routes shared by nearby responders/users, decorated for the Directions
  // "Suggested routes" list + a map preview. Filtered to the active disaster
  // like the other lists. `latlngs` is the stored polyline or a 2-point
  // [origin, dest] fallback, ready for MapScreen's routePolyline mechanism.
  const sharedRoutes = (S.sharedRoutes || [])
    .filter((r) => r && (!r.disaster_id || r.disaster_id === S.selectedDisasterId))
    .map((r) => ({
      ...r,
      destName: r.dest_name || t('directions.destination'),
      author: r.author_alias || t('common.noName'),
      when: String(r.created_at || r.createdAt || '').replace('T', ' ').slice(0, 16),
      modeLabel: t('directions.mode.' + (r.mode === 'drive' ? 'drive' : 'walk')),
      sharedByLabel: t('directions.sharedBy', { alias: r.author_alias || t('common.noName') }),
      latlngs: routeShareLatLngs(r),
    }))

  // ----- Evacuation corridors (plan-21 Phase 6) -----
  // Named open/congested/closed paths (drive/walk/transit) for the active
  // disaster. Decorated with a status colour, translated mode/status labels, and
  // `latlngs` (the raw path) ready for MapScreen's polyline overlay.
  const CORRIDOR_STATUS = {
    open: { color: '#1B7A45', key: 'corridors.status.open' },
    congested: { color: '#9A6400', key: 'corridors.status.congested' },
    closed: { color: '#C2272D', key: 'corridors.status.closed' },
  }
  const corridors = (S.corridors || [])
    .filter((c) => c && Array.isArray(c.path) && c.path.length > 1 &&
      (!c.disaster_id || c.disaster_id === S.selectedDisasterId))
    .map((c) => {
      const st = CORRIDOR_STATUS[c.status] || CORRIDOR_STATUS.open
      const mode = ['drive', 'walk', 'transit'].includes(c.mode) ? c.mode : 'drive'
      return {
        ...c,
        statusColor: st.color,
        statusLabel: t(st.key),
        modeLabel: t('corridors.mode.' + mode),
        latlngs: c.path,
      }
    })

  const chips = [
    ['all', 'filter.all'], ['missing', 'filter.missing'], ['sighted', 'filter.sighted'],
    ['safe', 'filter.safe'], ['care', 'filter.care'],
  ].map(([k, lblKey]) => {
    const active = S.filter === k
    return {
      key: k, label: t(lblKey), active,
      chipBg: active ? '#1A1714' : '#fff',
      chipFg: active ? '#fff' : '#5A534C',
      chipBorder: active ? '#1A1714' : '#E2DED8',
      onClick: () => actions.setFilter(k),
    }
  })

  // ----- Shelters (plan-20) -----
  // Trust badge styling: official (verified staff) > volunteer > crowd.
  const TRUST_STYLE = {
    official: { bg: '#E3F2E7', fg: '#1B7A45', key: 'shelterDetail.trust.official' },
    volunteer: { bg: '#FBEEDA', fg: '#9A6400', key: 'shelterDetail.trust.volunteer' },
    crowd: { bg: '#F1EEE9', fg: '#8A837A', key: 'shelterDetail.trust.crowd' },
  }
  // Decorate one shelter record with display-ready capacity/services/trust values.
  const decorateShelter = (i) => {
    const total = typeof i.capacity_total === 'number' ? i.capacity_total : null
    const avail = typeof i.capacity_available === 'number' ? i.capacity_available : null
    const occ = typeof i.occupancy === 'number'
      ? i.occupancy
      : (total != null && avail != null ? Math.max(0, total - avail) : null)
    const occPct = total && occ != null ? Math.min(100, Math.round((occ / total) * 100)) : null
    const accepting = i.accepting_new === undefined ? true : !!i.accepting_new
    const trust = TRUST_STYLE[i.trust] || TRUST_STYLE.crowd
    // Bar color: red when full/over 90%, amber mid, green low.
    const barColor = occPct == null ? '#CFC9C0' : occPct >= 90 ? '#C2272D' : occPct >= 70 ? '#9A6400' : '#1B7A45'
    return {
      ...i,
      hasMinors: !!i.minors || (Array.isArray(i.target_populations) && i.target_populations.includes('minors')),
      tag: i.kind === 'hospital' ? t('shelters.tagHosp') : t('shelters.tagRef'),
      tintBg: i.kind === 'hospital' ? '#E4EEF6' : '#E3F2E7',
      tintFg: i.kind === 'hospital' ? '#1F5E96' : '#1B7A45',
      services: Array.isArray(i.services) ? i.services : [],
      supplyNeeds: Array.isArray(i.supply_needs) ? i.supply_needs : [],
      targetPopulations: Array.isArray(i.target_populations) ? i.target_populations : [],
      total, avail, occ, occPct, barColor, accepting,
      acceptingLabel: accepting ? t('shelterDetail.accepting') : t('shelterDetail.full'),
      acceptingBg: accepting ? '#E9F4ED' : '#FCEDEC',
      acceptingFg: accepting ? '#15683A' : '#B7242A',
      trustBg: trust.bg, trustFg: trust.fg, trustLabel: t(trust.key),
      capLabel: total != null && avail != null
        ? t('shelterDetail.capLabel', { avail, total })
        : (occ != null ? String(occ) : (i.count || '')),
      open: () => actions.openShelter(i.id),
    }
  }
  const instiSource = S.institutions && S.institutions.length ? S.institutions : DEMO_INSTI
  const institutions = instiSource
    .filter((i) => (i.disaster || i.disaster_id) === S.selectedDisasterId)
    .map(decorateShelter)

  // Filter chips for the shelter list (responder/victim quick filters).
  const sf = S.shelterFilters || {}
  const shelterFilterDefs = [
    ['hasSpace', 'shelters.filter.hasSpace'], ['pets', 'shelters.filter.pets'],
    ['medical', 'shelters.filter.medical'], ['supplies', 'shelters.filter.supplies'],
  ]
  const shelterFilters = shelterFilterDefs.map(([key, lblKey]) => {
    const on = !!sf[key]
    return {
      key, label: t(lblKey), active: on,
      chipBg: on ? '#1A1714' : '#fff', chipFg: on ? '#fff' : '#5A534C',
      chipBorder: on ? '#1A1714' : '#E2DED8',
      onClick: () => actions.setShelterFilter(key),
    }
  })

  // The open shelter detail (plan-20 §4) + its decoded update feed.
  const shelterRaw = instiSource.find((i) => i.id === S.shelterDetailId) || null
  const shelterDetail = shelterRaw ? decorateShelter(shelterRaw) : null
  const UPDATE_ROLE_STYLE = {
    official: { bg: '#E3F2E7', fg: '#1B7A45', key: 'shelterDetail.role.official' },
    volunteer: { bg: '#FBEEDA', fg: '#9A6400', key: 'shelterDetail.role.volunteer' },
    system: { bg: '#E4EEF6', fg: '#1F5E96', key: 'shelterDetail.role.system' },
  }
  const shelterUpdates = (S.shelterUpdates || []).map((u) => {
    const role = UPDATE_ROLE_STYLE[u.author_role] || UPDATE_ROLE_STYLE.volunteer
    return {
      ...u,
      when: String(u.created_at || u.createdAt || '').replace('T', ' ').slice(0, 16),
      roleBg: role.bg, roleFg: role.fg, roleLabel: t(role.key),
      author: u.author_name || t('shelterDetail.role.' + (u.author_role || 'volunteer')),
    }
  })

  const mineSource = S.myReports && S.myReports.length ? S.myReports : DEMO_MINE
  const myReports = mineSource.map((m) => ({
    ...m,
    status: m.state === 'queued' ? t('mine.queued') : t('mine.sent'),
    bg: m.state === 'queued' ? '#FCEDEC' : '#E9F4ED',
    fg: m.state === 'queued' ? '#B7242A' : '#15683A',
  }))

  const actSource = S.activity && S.activity.length ? S.activity : DEMO_ACT
  const activity = actSource
    .filter((a) => (a.disaster || a.disaster_id) === S.selectedDisasterId)
    .map((a) => ({ ...a, dot: STATUS[a.k].fg }))

  // Step metadata derived from the active report type. Missing keeps the full
  // 5-step flow; sighting/safe are short flows with their own titles.
  const stepKeySets = {
    missing: ['report.step.0', 'report.step.1', 'report.step.2', 'report.step.3', 'report.step.4'],
    sighting: ['report.sighting.step.0', 'report.sighting.step.1', 'report.sighting.step.2'],
    safe: ['report.safe.step.0', 'report.safe.step.1'],
  }
  const stepKeys = stepKeySets[S.reportType] || stepKeySets.missing
  const stepCount = stepKeys.length
  const curStep = Math.min(S.reportStep, stepCount - 1)
  const stepTitle = t(stepKeys[curStep])
  const stepBars = stepKeys.map((_, i) => ({ bg: i <= S.reportStep ? '#E5343B' : '#EAE6E0' }))

  const typeDefs = [
    { key: 'missing', es: t('report.type.missing'), en: t('report.type.missingEn') },
    { key: 'sighting', es: t('report.type.sighting'), en: t('report.type.sightingEn') },
    { key: 'safe', es: t('report.type.safe'), en: t('report.type.safeEn') },
  ]
  const typeOptions = typeDefs.map((def) => {
    const on = S.reportType === def.key
    return {
      ...def,
      bg: on ? '#FFF4F3' : '#fff',
      border: on ? '#E5343B' : '#E6E2DC',
      ring: on ? '#E5343B' : '#CFC9C0',
      dot: on ? '#E5343B' : 'transparent',
      onClick: () => actions.setReportType(def.key),
    }
  })
  const typeLabelMap = {
    missing: t('report.typeLabel.missing'),
    sighting: t('report.typeLabel.sighting'),
    safe: t('report.typeLabel.safe'),
  }

  const active = (s) => (S.screen === s ? '#E5343B' : '#9A938A')

  const isDesktop = S.vw >= 860
  const navStyle = (s) => (S.screen === s ? { color: '#E5343B', bg: '#FFF1F0' } : { color: '#5A534C', bg: 'transparent' })
  const conn = S.online
    ? { dot: '#1B7A45', fg: '#15683A', sub: '#6FA585', border: '#CCE6D6', bg: '#E9F4ED', title: t('conn.online.title'), hint: t('conn.online.hint'), pill: t('conn.online.pill') }
    : { dot: '#C2272D', fg: '#B7242A', sub: '#CC8E8A', border: '#F6DAD7', bg: '#FCEDEC', title: t('conn.offline.title'), hint: t('conn.offline.hint', { n: S.queue }), pill: t('conn.offline.pill') }

  // ----- Mesh (Red local) display values -----
  const ms = S.meshStatus || {}
  const meshRunning = !!ms.running
  const meshLastSync = ms.lastSync ? String(ms.lastSync).replace('T', ' ').slice(0, 16) : '—'
  // Recently-seen device ids, formatted for display: a shortened id plus a
  // relative "last seen" string.
  const meshShortId = (id) => {
    const s = String(id || '')
    return s.length > 12 ? `…${s.slice(-10)}` : s
  }
  const meshRelSeen = (iso) => {
    const then = Date.parse(iso)
    if (Number.isNaN(then)) return ''
    const sec = Math.max(0, Math.round((Date.now() - then) / 1000))
    if (sec < 45) return t('mesh.seenNow')
    const min = Math.round(sec / 60)
    if (min < 60) return t('mesh.seenMin', { n: min })
    const hr = Math.round(min / 60)
    if (hr < 24) return t('mesh.seenHr', { n: hr })
    return t('mesh.seenDay', { n: Math.round(hr / 24) })
  }
  const recentPeers = (Array.isArray(S.recentPeers) ? S.recentPeers : []).map((p) => ({
    id: p.id,
    shortId: meshShortId(p.id),
    seen: meshRelSeen(p.lastSeen),
  }))
  const mesh = {
    available: !!S.meshAvailable,
    consent: !!S.meshConsent,
    running: meshRunning,
    peers: ms.peers ?? 0,
    queued: ms.queued ?? 0,
    lastSync: meshLastSync,
    deviceId: ms.deviceId || '—',
    recentPeers,
    statusText: !S.meshAvailable
      ? t('mesh.unavailable')
      : meshRunning
        ? t('mesh.active')
        : t('mesh.stopped'),
    toggleLabel: meshRunning ? t('mesh.stop') : t('mesh.start'),
    statusPill: meshRunning ? t('mesh.pillActive') : t('mesh.pillInactive'),
    pillBg: meshRunning ? '#E9F4ED' : '#F1EEE9',
    pillFg: meshRunning ? '#15683A' : '#8A837A',
  }

  const disasterSource = S.disasters && S.disasters.length ? S.disasters : DEMO_DISASTERS
  const allDisasters = [...disasterSource, ...S.customDisasters]
  const disasters = allDisasters.map((d) => ({ ...d, open: () => actions.chooseDisaster(d.id) }))
  const selRaw = disasters.find((d) => d.id === S.selectedDisasterId) || null
  const selDisaster = selRaw || { tag: '', name: '', region: '', affected: '', shelters: '', date: '' }
  const TYPES = [['flood', 'add.type.flood'], ['quake', 'add.type.quake'], ['landslide', 'add.type.landslide']]
  const addTypeChips = TYPES.map(([k, lblKey]) => {
    const on = S.draftType === k
    return {
      key: k, label: t(lblKey), onClick: () => actions.setDraftType(k),
      chipBg: on ? '#1A1714' : '#fff', chipFg: on ? '#fff' : '#5A534C', chipBorder: on ? '#1A1714' : '#E2DED8',
    }
  })

  return {
    showAuth: !S.authed,
    showPicker: S.authed && !S.selectedDisasterId,
    showApp: S.authed && !!S.selectedDisasterId,
    // Low-literacy / panic "Modo simple" (plan-14, Phase 5). The simplified
    // home replaces the normal HomeScreen only while on the home screen, so the
    // report sheet and search still use the existing full-UI flows.
    simpleMode: !!S.simpleMode,
    showSimpleHome: !!S.simpleMode && S.screen === 'home' && !S.reportOpen,
    disasters, selDisaster,
    disasterName: selDisaster.name,
    disasterMeta: selRaw
      ? t('home.disasterMeta', { region: selDisaster.region, affected: selDisaster.affected, date: selDisaster.date })
      : '',
    user: S.user,
    userInitials: S.user ? S.user.initials : '',
    userName: S.user ? S.user.name : '',
    userEmail: S.user ? S.user.email : '',
    addOpen: S.addOpen, addTypeChips,
    draftName: S.draftName, draftRegion: S.draftRegion,
    isDesktop,
    rootDir: isDesktop ? 'row' : 'column',
    sidebarDisplay: isDesktop ? 'flex' : 'none',
    topbarDisplay: isDesktop ? 'none' : 'flex',
    tabBarDisplay: isDesktop ? 'none' : 'flex',
    contentMaxW: isDesktop ? '760px' : '100%',
    sheetJustify: isDesktop ? 'center' : 'flex-end',
    sheetPad: isDesktop ? '24px' : '0px',
    sheetRadius: isDesktop ? '20px' : '24px 24px 0 0',
    sheetMaxW: isDesktop ? '460px' : '560px',
    sheetMaxH: isDesktop ? '88%' : '94%',
    navHome: navStyle('home'), navSearch: navStyle('search'),
    navShelters: navStyle('shelters'), navMine: navStyle('mine'),
    navMesh: navStyle('mesh'),
    navMap: navStyle('map'),
    navDuplicates: navStyle('duplicates'),
    navModeration: navStyle('moderation'),
    navDashboard: navStyle('dashboard'),
    navDirections: navStyle('directions'),
    mesh, meshWarnOpen: S.meshWarnOpen,
    duplicates: { clusters: S.dupClusters || [], loading: !!S.dupLoading, count: (S.dupClusters || []).length },
    // Operator (moderator) mode + moderation queue (Phase 9)
    operator: !!S.operator,
    moderation: {
      pending: S.modPending || [],
      count: (S.modPending || []).length,
      loading: !!S.modLoading,
      stats: S.modStats || null,
    },
    // Operational-intelligence dashboard (plan-13).
    dashboard: { data: S.dashboard || null, loading: !!S.dashLoading },
    conn,
    isHome: S.screen === 'home', isSearch: S.screen === 'search',
    isDetail: S.screen === 'detail', isShelters: S.screen === 'shelters',
    isMine: S.screen === 'mine', isMesh: S.screen === 'mesh',
    isMap: S.screen === 'map',
    isDuplicates: S.screen === 'duplicates',
    isModeration: S.screen === 'moderation',
    isDashboard: S.screen === 'dashboard',
    // Offline routing (plan-21). Destination candidates are decorated shelters
    // and people that carry coordinates; the screen also accepts typed coords,
    // "my location", and a preselected `directionsTarget`.
    isDirections: S.screen === 'directions',
    directionsTarget: S.directionsTarget || null,
    // Road-following polyline computed by the offline routing worker (plan-21
    // Phase 2); MapScreen draws it when present.
    routePolyline: Array.isArray(S.routePolyline) && S.routePolyline.length ? S.routePolyline : null,
    directionsDestinations: {
      shelters: institutions
        .filter((i) => typeof i.lat === 'number' && typeof i.lon === 'number')
        .map((i) => ({ id: i.id, name: i.name, lat: i.lat, lon: i.lon, kind: 'shelter', sub: i.address || '' })),
      people: mapPeople.map((p) => ({
        id: p.id, name: p.name || t('common.noName'), lat: p.lat, lon: p.lon,
        kind: 'person', sub: p.location || p.statusLabel || '',
      })),
    },
    tabMesh: active('mesh'),
    offline: !S.online, online: S.online, queue: S.queue,
    search: S.search,
    checkedInSafe: S.checkedInSafe,
    visiblePeople: visible, visibleCount: visible.length,
    // Cédula search (Phase 6)
    cedulaQuery: S.cedulaQuery || '',
    cedulaActive: !!S.cedulaActive,
    cedulaSearching: !!S.cedulaSearching,
    cedulaResults: (S.cedulaResults || []).map(dec),
    cedulaCount: (S.cedulaResults || []).length,
    // Pagination (Phase 7)
    searchHasMore: !!S.searchHasMore,
    searchLoading: !!S.searchLoading,
    sel, chips, institutions, myReports, activity, mapPeople, hazards,
    // Shared routes (plan-21 Phase 5)
    sharedRoutes,
    // Evacuation corridors (plan-21 Phase 6)
    corridors,
    // Shelters (plan-20)
    shelterFilters, shelterDetail, shelterUpdates,
    shelterUpdatesLoading: !!S.shelterUpdatesLoading,
    shelterTab: S.shelterTab || 'info',
    isShelterDetail: S.screen === 'shelterDetail',
    shelterCheckedIn: S.shelterCheckedIn || null,
    shelterCheckins: S.shelterCheckins || [],
    shelterClaimMsg: S.shelterClaimMsg || null,
    pendingShelterCount: S.pendingShelterCount || 0,
    tabHome: active('home'), tabSearch: active('search'),
    tabShelters: active('shelters'), tabMine: active('mine'),
    reportOpen: S.reportOpen, reportDone: S.reportDone, reportForm: !S.reportDone,
    reportType: S.reportType,
    reportStep: S.reportStep, stepNum: S.reportStep + 1, stepCount,
    stepTitle, stepBars,
    isStep0: S.reportStep === 0, isStep1: S.reportStep === 1,
    isStep2: S.reportStep === 2, isStep3: S.reportStep === 3, isStep4: S.reportStep === 4,
    showBack: S.reportStep > 0, showNext: S.reportStep < stepCount - 1, showSubmit: S.reportStep === stepCount - 1,
    typeOptions, reportTypeLabel: typeLabelMap[S.reportType], savedCase: S.savedCase,
    reportDraft: S.reportDraft,
    reviewName: S.reportDraft.name || t('report.review.noName'),
    reviewAgeLocation:
      (S.reportDraft.age ? t('report.review.ageYears', { age: S.reportDraft.age }) : t('report.review.ageUnknown')) +
      ' · ' + (S.reportDraft.location || t('report.review.locationUnknown')),
    reviewLastSeen: S.reportDraft.lastSeenDate || t('common.dateUnknown'),
    reviewReporter: (S.reportDraft.relation || t('report.review.relationDefault')) +
      ' · ' + (S.reportDraft.country || t('report.review.locationUnknown')),
  }
}

// buildView — derives all the display-ready values the screens need from raw
// state + actions. This is a direct port of the original renderVals(): keeping
// it in one place means the components stay purely presentational.
import { STATUS, DEMO_PEOPLE, DEMO_INSTI, DEMO_MINE, DEMO_ACT, DEMO_DISASTERS } from '../data/demo.js'
import { decoratePerson } from './person.js'

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

  const instiSource = S.institutions && S.institutions.length ? S.institutions : DEMO_INSTI
  const institutions = instiSource
    .filter((i) => (i.disaster || i.disaster_id) === S.selectedDisasterId)
    .map((i) => ({
      ...i,
      hasMinors: !!i.minors,
      tag: i.kind === 'hospital' ? t('shelters.tagHosp') : t('shelters.tagRef'),
      tintBg: i.kind === 'hospital' ? '#E4EEF6' : '#E3F2E7',
      tintFg: i.kind === 'hospital' ? '#1F5E96' : '#1B7A45',
    }))

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
  const mesh = {
    available: !!S.meshAvailable,
    consent: !!S.meshConsent,
    running: meshRunning,
    peers: ms.peers ?? 0,
    queued: ms.queued ?? 0,
    lastSync: meshLastSync,
    deviceId: ms.deviceId || '—',
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
    navDuplicates: navStyle('duplicates'),
    navModeration: navStyle('moderation'),
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
    conn,
    isHome: S.screen === 'home', isSearch: S.screen === 'search',
    isDetail: S.screen === 'detail', isShelters: S.screen === 'shelters',
    isMine: S.screen === 'mine', isMesh: S.screen === 'mesh',
    isDuplicates: S.screen === 'duplicates',
    isModeration: S.screen === 'moderation',
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
    sel, chips, institutions, myReports, activity,
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

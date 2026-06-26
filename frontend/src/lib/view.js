// buildView — derives all the display-ready values the screens need from raw
// state + actions. This is a direct port of the original renderVals(): keeping
// it in one place means the components stay purely presentational.
import { STATUS, DEMO_PEOPLE, DEMO_INSTI, DEMO_MINE, DEMO_ACT, DEMO_DISASTERS } from '../data/demo.js'
import { decoratePerson } from './person.js'

export function buildView(state, actions) {
  const S = state

  const dec = (p) => decoratePerson(p, S.overrides, actions.openPerson)

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
    ['all', 'Todos'], ['missing', 'Desaparecidos'], ['sighted', 'Vistos'],
    ['safe', 'A salvo'], ['care', 'En cuidado'],
  ].map(([k, lbl]) => {
    const active = S.filter === k
    return {
      key: k, label: lbl, active,
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
      tag: i.kind === 'hospital' ? 'HOSP' : 'REF',
      tintBg: i.kind === 'hospital' ? '#E4EEF6' : '#E3F2E7',
      tintFg: i.kind === 'hospital' ? '#1F5E96' : '#1B7A45',
    }))

  const mineSource = S.myReports && S.myReports.length ? S.myReports : DEMO_MINE
  const myReports = mineSource.map((m) => ({
    ...m,
    status: m.state === 'queued' ? 'En cola' : 'Enviado',
    bg: m.state === 'queued' ? '#FCEDEC' : '#E9F4ED',
    fg: m.state === 'queued' ? '#B7242A' : '#15683A',
  }))

  const actSource = S.activity && S.activity.length ? S.activity : DEMO_ACT
  const activity = actSource
    .filter((a) => (a.disaster || a.disaster_id) === S.selectedDisasterId)
    .map((a) => ({ ...a, dot: STATUS[a.k].fg }))

  const stepTitles = ['Tipo y foto', 'Datos de la persona', 'Última ubicación', 'Tu contacto', 'Revisar y guardar']
  const stepBars = [0, 1, 2, 3, 4].map((i) => ({ bg: i <= S.reportStep ? '#E5343B' : '#EAE6E0' }))

  const typeDefs = [
    { key: 'missing', es: 'Reportar desaparecido', en: 'Report a missing person' },
    { key: 'sighting', es: 'Reporté un avistamiento', en: 'Report a sighting' },
    { key: 'safe', es: 'Registrar a alguien a salvo', en: 'Register someone safe' },
  ]
  const typeOptions = typeDefs.map((t) => {
    const on = S.reportType === t.key
    return {
      ...t,
      bg: on ? '#FFF4F3' : '#fff',
      border: on ? '#E5343B' : '#E6E2DC',
      ring: on ? '#E5343B' : '#CFC9C0',
      dot: on ? '#E5343B' : 'transparent',
      onClick: () => actions.setReportType(t.key),
    }
  })
  const typeLabelMap = { missing: 'Desaparecido', sighting: 'Avistamiento', safe: 'A salvo' }

  const active = (s) => (S.screen === s ? '#E5343B' : '#9A938A')

  const isDesktop = S.vw >= 860
  const navStyle = (s) => (S.screen === s ? { color: '#E5343B', bg: '#FFF1F0' } : { color: '#5A534C', bg: 'transparent' })
  const conn = S.online
    ? { dot: '#1B7A45', fg: '#15683A', sub: '#6FA585', border: '#CCE6D6', bg: '#E9F4ED', title: 'En línea', hint: 'Conectado · sincronizado', pill: 'EN LÍNEA' }
    : { dot: '#C2272D', fg: '#B7242A', sub: '#CC8E8A', border: '#F6DAD7', bg: '#FCEDEC', title: 'Sin conexión', hint: S.queue + ' en cola · se enviará', pill: 'SIN RED' }

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
      ? 'La malla local solo está disponible dentro de la app de Android.'
      : meshRunning
        ? 'Malla activa · buscando dispositivos cercanos'
        : 'Malla detenida',
    toggleLabel: meshRunning ? 'Detener malla' : 'Activar malla',
    statusPill: meshRunning ? 'ACTIVA' : 'INACTIVA',
    pillBg: meshRunning ? '#E9F4ED' : '#F1EEE9',
    pillFg: meshRunning ? '#15683A' : '#8A837A',
  }

  const disasterSource = S.disasters && S.disasters.length ? S.disasters : DEMO_DISASTERS
  const allDisasters = [...disasterSource, ...S.customDisasters]
  const disasters = allDisasters.map((d) => ({ ...d, open: () => actions.chooseDisaster(d.id) }))
  const selRaw = disasters.find((d) => d.id === S.selectedDisasterId) || null
  const selDisaster = selRaw || { tag: '', name: '', region: '', affected: '', shelters: '', date: '' }
  const TYPES = [['flood', 'Inundación'], ['quake', 'Sismo'], ['landslide', 'Deslave']]
  const addTypeChips = TYPES.map(([k, lbl]) => {
    const on = S.draftType === k
    return {
      key: k, label: lbl, onClick: () => actions.setDraftType(k),
      chipBg: on ? '#1A1714' : '#fff', chipFg: on ? '#fff' : '#5A534C', chipBorder: on ? '#1A1714' : '#E2DED8',
    }
  })

  return {
    showAuth: !S.authed,
    showPicker: S.authed && !S.selectedDisasterId,
    showApp: S.authed && !!S.selectedDisasterId,
    disasters, selDisaster,
    disasterName: selDisaster.name,
    disasterMeta: selRaw ? selDisaster.region + ' · ' + selDisaster.affected + ' registradas · desde ' + selDisaster.date : '',
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
    mesh, meshWarnOpen: S.meshWarnOpen,
    conn,
    isHome: S.screen === 'home', isSearch: S.screen === 'search',
    isDetail: S.screen === 'detail', isShelters: S.screen === 'shelters',
    isMine: S.screen === 'mine', isMesh: S.screen === 'mesh',
    tabMesh: active('mesh'),
    offline: !S.online, online: S.online, queue: S.queue,
    search: S.search,
    checkedInSafe: S.checkedInSafe,
    visiblePeople: visible, visibleCount: visible.length,
    sel, chips, institutions, myReports, activity,
    tabHome: active('home'), tabSearch: active('search'),
    tabShelters: active('shelters'), tabMine: active('mine'),
    reportOpen: S.reportOpen, reportDone: S.reportDone, reportForm: !S.reportDone,
    reportStep: S.reportStep, stepNum: S.reportStep + 1,
    stepTitle: stepTitles[S.reportStep], stepBars,
    isStep0: S.reportStep === 0, isStep1: S.reportStep === 1,
    isStep2: S.reportStep === 2, isStep3: S.reportStep === 3, isStep4: S.reportStep === 4,
    showBack: S.reportStep > 0, showNext: S.reportStep < 4, showSubmit: S.reportStep === 4,
    typeOptions, reportTypeLabel: typeLabelMap[S.reportType], savedCase: S.savedCase,
    reportDraft: S.reportDraft,
    reviewName: S.reportDraft.name || 'Sin nombre',
    reviewAgeLocation:
      (S.reportDraft.age ? S.reportDraft.age + ' años' : 'Edad desconocida') + ' · ' + (S.reportDraft.location || 'Ubicación desconocida'),
    reviewLastSeen: S.reportDraft.lastSeenDate || 'Fecha desconocida',
    reviewReporter: (S.reportDraft.relation || 'Familiar') + ' · ' + (S.reportDraft.country || 'Ubicación desconocida'),
  }
}

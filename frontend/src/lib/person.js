// Pure helpers for turning raw server / demo person records into the shape
// the UI renders. Ported 1:1 from the original prototype.
import { STATUS } from '../data/demo.js'

// Soft-normalize a cédula for matching, mirroring the server: uppercase, strip
// dots, spaces and dashes, then drop a leading V/E nationality prefix. So
// '26345789', 'V-26.345.789' and 'v26345789' all normalize to '26345789'.
export function normalizeCedula(value) {
  return String(value == null ? '' : value)
    .toUpperCase()
    .replace(/[.\s-]/g, '')
    .replace(/^[VE]/, '')
}

export function initials(n) {
  const clean = (n || '').replace(/\(.*?\)/g, '').trim()
  const parts = clean.split(/\s+/).filter(Boolean)
  return ((parts[0] || '')[0] || '') + ((parts[1] || '')[0] || '')
}

// `t` is the i18n translator; defaults to an identity that returns the Spanish
// key so callers without i18n still get a sensible (key) fallback.
export function label(p, t = (k) => k) {
  if (p.status === 'missing') return t(p.gender === 'F' ? 'status.missing.f' : 'status.missing.m')
  if (p.status === 'sighted') return t(p.gender === 'F' ? 'status.sighted.f' : 'status.sighted.m')
  if (p.status === 'safe') return t('status.safe')
  return t('status.care')
}

export function meta(p, t = (k) => k) {
  const g = p.gender === 'F' ? t('gender.f') : t('gender.m')
  if (p.age === 0) return p.place || p.location
  return (p.age || '?') + ' ' + t('common.years') + ' · ' + g
}

// Map server fields and demo fields onto one common shape.
export function normalizePerson(p) {
  return {
    id: p.id,
    disaster: p.disaster || p.disaster_id,
    name: p.name,
    cedula: p.cedula || '',
    gender: p.gender || 'M',
    age: p.age === null || p.age === undefined ? 0 : p.age,
    status: p.status,
    // Geospatial last-seen coordinates (plan-10). Preserved so the map view can
    // place a marker; null/undefined for records without coordinates.
    lat: typeof p.lat === 'number' ? p.lat : null,
    lon: typeof p.lon === 'number' ? p.lon : null,
    place: p.place || p.location,
    location: p.location || p.place,
    date: p.date || p.last_seen_date || 'Fecha desconocida',
    last_seen_date: p.last_seen_date || p.date,
    clothes: p.clothes || 'Sin información de vestimenta',
    desc: p.desc || p.notes || 'Sin descripción adicional.',
    notes: p.notes || p.desc,
    reportedBy: p.reportedBy || p.reported_by || 'Anónimo',
    reporterInitials: initials(p.reportedBy || p.reported_by || 'Anónimo'),
    updates: p.updates || [
      { t: 'Registro sincronizado', s: (p.updated_at || '').slice(0, 10), k: p.status || 'missing' },
    ],
  }
}

// Decorate a normalized person with display-ready styling and status overrides.
// Display priority: local override > server-derived status (highest-confidence
// latest report) > stored status. So a stale "missing" with a recent official
// "safe" report shows as safe.
export function decoratePerson(p, overrides, openPerson, t = (k) => k) {
  const np = normalizePerson(p)
  const status = overrides[np.id] || p.derived_status || np.status
  const pp = { ...np, status }
  // Fall back gracefully for statuses outside the 4-colour map (e.g. a server
  // record marked 'found' or 'deceased').
  const st = STATUS[status] || STATUS.missing
  return {
    ...pp,
    statusLabel: label(pp, t),
    badgeBg: st.bg,
    badgeFg: st.fg,
    initials: initials(np.name),
    meta: meta(np, t),
    reporterInitials: initials(np.reportedBy),
    updates: np.updates.map((u) => ({ ...u, dot: (STATUS[u.k] || STATUS.missing).fg })),
    open: () => openPerson(np.id),
  }
}

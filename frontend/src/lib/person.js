// Pure helpers for turning raw server / demo person records into the shape
// the UI renders. Ported 1:1 from the original prototype.
import { STATUS } from '../data/demo.js'

export function initials(n) {
  const clean = (n || '').replace(/\(.*?\)/g, '').trim()
  const parts = clean.split(/\s+/).filter(Boolean)
  return ((parts[0] || '')[0] || '') + ((parts[1] || '')[0] || '')
}

export function label(p) {
  if (p.status === 'missing') return p.gender === 'F' ? 'Desaparecida' : 'Desaparecido'
  if (p.status === 'sighted') return p.gender === 'F' ? 'Vista' : 'Visto'
  if (p.status === 'safe') return 'A salvo'
  return 'En cuidado'
}

export function meta(p) {
  const g = p.gender === 'F' ? 'Femenino' : 'Masculino'
  if (p.age === 0) return p.place || p.location
  return (p.age || '?') + ' años · ' + g
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
export function decoratePerson(p, overrides, openPerson) {
  const np = normalizePerson(p)
  const status = overrides[np.id] || np.status
  const pp = { ...np, status }
  // Fall back gracefully for statuses outside the 4-colour map (e.g. a server
  // record marked 'found' or 'deceased').
  const st = STATUS[status] || STATUS.missing
  return {
    ...pp,
    statusLabel: label(pp),
    badgeBg: st.bg,
    badgeFg: st.fg,
    initials: initials(np.name),
    meta: meta(np),
    reporterInitials: initials(np.reportedBy),
    updates: np.updates.map((u) => ({ ...u, dot: (STATUS[u.k] || STATUS.missing).fg })),
    open: () => openPerson(np.id),
  }
}

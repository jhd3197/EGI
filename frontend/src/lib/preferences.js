// User preferences: content categories + per-category display/notify/relay
// toggles, plus global settings (near-me radius, quiet hours). Local-first
// (cached in IndexedDB `meta` under `preferences`) and synced to the server for
// logged-in users; guests keep them on-device only (plan-24 Phase 1).
//
// Kept in sync with CONTENT_CATEGORIES / DEFAULT_NOTIFY_CATEGORIES in
// server/models.py and modules/preferences.py.

// The content-category catalogue. `notify` is the notify-on-by-default policy;
// `critical` categories can be turned down in the UI but life-safety alerts
// (own-record match, commander broadcast) bypass the toggle server-side.
// `i18n` is the translation key prefix for label + description.
export const CATEGORIES = [
  { key: 'people', notify: true, critical: true, i18n: 'settings.cat.people' },
  { key: 'animals', notify: false, critical: false, i18n: 'settings.cat.animals' },
  { key: 'shelters', notify: false, critical: false, i18n: 'settings.cat.shelters' },
  { key: 'hazards', notify: false, critical: false, i18n: 'settings.cat.hazards' },
  { key: 'supplies', notify: false, critical: false, i18n: 'settings.cat.supplies' },
  { key: 'operations', notify: false, critical: false, i18n: 'settings.cat.operations' },
  { key: 'broadcasts', notify: true, critical: true, i18n: 'settings.cat.broadcasts' },
]

export const CATEGORY_KEYS = CATEGORIES.map((c) => c.key)

export const CRITICAL_CATEGORIES = new Set(
  CATEGORIES.filter((c) => c.critical).map((c) => c.key),
)

// The three subscription dimensions, in display order. Mirrors the server.
export const DIMENSIONS = ['display', 'notify', 'relay']

function defaultCategory(key) {
  const meta = CATEGORIES.find((c) => c.key === key)
  return {
    display: true,
    notify: !!(meta && meta.notify),
    relay: true,
    radius: null, // per-category "near me" override (null = use global)
    updatedAt: null,
  }
}

export function defaultSettings() {
  return {
    radius: null, // global "near me" radius in metres (null/0 = off)
    homeLat: null,
    homeLon: null,
    quietStart: null, // hour 0-23 (null = no quiet hours)
    quietEnd: null,
    batch: false,
    updatedAt: null,
  }
}

// The full default preferences object the store starts from.
export function defaultPreferences() {
  const categories = {}
  for (const c of CATEGORIES) categories[c.key] = defaultCategory(c.key)
  return { categories, settings: defaultSettings() }
}

// ---- display / notify / relay helpers (used across UI, search, mesh) ----

export function isDisplayed(prefs, category) {
  const c = prefs && prefs.categories && prefs.categories[category]
  return c ? c.display !== false : true
}

export function isNotified(prefs, category) {
  const c = prefs && prefs.categories && prefs.categories[category]
  if (c) return !!c.notify
  const meta = CATEGORIES.find((m) => m.key === category)
  return !!(meta && meta.notify)
}

export function isRelayed(prefs, category) {
  const c = prefs && prefs.categories && prefs.categories[category]
  return c ? c.relay !== false : true
}

// The set of category keys currently hidden from the UI (for the "X ocultos"
// indicator and tab-bar pruning in Phase 3).
export function hiddenCategories(prefs) {
  return CATEGORY_KEYS.filter((k) => !isDisplayed(prefs, k))
}

// ---- server <-> client mapping ----

// Map the server's snake_case category row to the client shape.
function fromServerCategory(row) {
  return {
    display: row.display_enabled !== 0,
    notify: !!row.notify_enabled,
    relay: row.mesh_relay_enabled !== 0,
    radius: row.radius_meters != null ? row.radius_meters : null,
    updatedAt: row.updated_at || null,
  }
}

function fromServerSettings(s) {
  if (!s) return defaultSettings()
  return {
    radius: s.radius_meters != null ? s.radius_meters : null,
    homeLat: s.home_lat != null ? s.home_lat : null,
    homeLon: s.home_lon != null ? s.home_lon : null,
    quietStart: s.quiet_hours_start != null ? s.quiet_hours_start : null,
    quietEnd: s.quiet_hours_end != null ? s.quiet_hours_end : null,
    batch: !!s.batch_notifications,
    updatedAt: s.updated_at || null,
  }
}

// Merge a server preferences response into the local object with last-write-wins
// per row (an absent/older timestamp never clobbers a newer local change).
export function mergeServerPreferences(local, server) {
  const out = { categories: {}, settings: { ...local.settings } }
  for (const key of CATEGORY_KEYS) {
    const l = (local.categories && local.categories[key]) || defaultCategory(key)
    const srow = server && server.categories && server.categories[key]
    if (!srow) { out.categories[key] = l; continue }
    const s = fromServerCategory(srow)
    out.categories[key] = newer(s.updatedAt, l.updatedAt) ? s : l
  }
  const ss = fromServerSettings(server && server.settings)
  out.settings = newer(ss.updatedAt, local.settings && local.settings.updatedAt)
    ? ss
    : local.settings
  return out
}

function newer(a, b) {
  if (!a) return false
  if (!b) return true
  return String(a) >= String(b)
}

// Build the PUT /preferences body from the local object (full snapshot).
export function toServerPayload(prefs) {
  return {
    categories: CATEGORY_KEYS.map((key) => {
      const c = prefs.categories[key]
      return {
        category: key,
        display_enabled: c.display ? 1 : 0,
        notify_enabled: c.notify ? 1 : 0,
        mesh_relay_enabled: c.relay ? 1 : 0,
        radius_meters: c.radius,
        updated_at: c.updatedAt,
      }
    }),
    settings: {
      radius_meters: prefs.settings.radius,
      home_lat: prefs.settings.homeLat,
      home_lon: prefs.settings.homeLon,
      quiet_hours_start: prefs.settings.quietStart,
      quiet_hours_end: prefs.settings.quietEnd,
      batch_notifications: prefs.settings.batch ? 1 : 0,
      updated_at: prefs.settings.updatedAt,
    },
  }
}

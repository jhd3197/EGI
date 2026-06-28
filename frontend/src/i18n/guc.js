// Wayuunaiki (guc) — PARTIAL community translation.
//
// IMPORTANT: This dictionary is an incomplete, community-seeded starting point,
// NOT a finished or authoritative translation. Wayuunaiki is an oral-first
// language with regional variation and no single standard orthography, so these
// strings need review by fluent Wayuu speakers. Contributions and corrections
// are very welcome — please open a PR.
//
// Only keys we can render with reasonable confidence are included. Every key
// that is omitted here falls back automatically to Spanish (see translate() in
// ./index.js), which most Wayuunaiki speakers also read, so a partial dict is
// safe and useful. Prefer omitting a key over guessing a wrong translation.
export default {
  // Common / shared
  'common.continue': 'Aluwataa',
  'common.back': 'Ale\'eju',
  'common.done': 'Anasü',
  'common.cancel': 'Ayataa',
  'common.close': 'Asakataa',
  'common.language': 'Anüiki',

  // Auth / entry
  'auth.tagline': 'EGI, achajaa püpüshi.',
  'auth.enterGuest': 'Ekerolaa',

  // Navigation
  'nav.home': 'Miichi',
  'nav.search': 'Achajawaa',
  'nav.directions': 'Jalain antüin',
  'nav.report': 'Aküjaa',
  'nav.activeEmergency': 'KASA MOJUSÜ',

  // Home
  'home.searchTitle': 'Tachajüin wané wayuu',
  'home.imOk': 'Anasü taya',

  // Simple / panic mode (plan-14, Phase 5)
  'simple.search': 'Tachajüin wané wayuu',
  'simple.report': 'Aküjaa süchiki wané wayuu',
  'simple.safe': 'Anasü taya',
  'simple.listen': 'Aapajaa',

  // Status / filters
  'filter.all': 'Süpüshua',
  'status.safe': 'Anasü',

  // Report type labels
  'report.typeLabel.safe': 'Anasü',

  // Offline directions (plan-21) — partial; the rest falls back to Spanish.
  'directions.title': 'Jalain antüin',
  'directions.from': 'Süpülapünaa',
  'directions.to': 'Sümaiwa',
  'directions.myLocation': 'Tepialuu',
  'directions.openInMaps': 'Ojuttüin mapa',
  'directions.computingRoute': 'Aluwataain wopu…',
}

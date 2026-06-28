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

  // Merge candidates / dedup (plan-27) — es fallback pending Wayuu review.
  'duplicates.candidatesTitle': 'Candidatos a combinar',
  'duplicates.candidatesEmpty': 'No hay candidatos a combinar.',
  'duplicates.review': 'Revisar',
  'duplicates.scan': 'Buscar duplicados',
  'merge.canonical': 'Mantener este',
  'merge.confirmMerge': 'Combinar registros',
  'merge.notMatch': 'No coinciden',
  'merge.needsInfo': 'Falta información',
  'merge.confidence': 'Confianza',
  'merge.conflictsTitle': 'Campos en conflicto',
  'merge.matchingFields': 'Campos coincidentes',
  'merge.provenance': 'Procedencia',
  'merge.recordA': 'Registro A',
  'merge.recordB': 'Registro B',
  'merge.close': 'Cerrar',
  'dedup.reason.same_cedula': 'Misma cédula',
  'dedup.reason.similar_name': 'Nombre parecido',
  'dedup.reason.same_name': 'Mismo nombre',
  'dedup.reason.same_age': 'Misma edad',
  'dedup.reason.similar_age': 'Edad parecida',
  'dedup.reason.same_location': 'Misma ubicación',
  'dedup.reason.same_phone': 'Mismo teléfono',
  'dedup.reason.same_time_window': 'Mismo período',
  'dashboard.mergeCandidates': 'Candidatos a combinar',

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
  'home.intentLooking': 'Tachajüin wané wayuu',
  'home.intentHelp': 'Tacheküin tü akaaliinaakat',
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
  'directions.suggestedRoutes': 'Wopu eemüin',
  'directions.mode.walk': 'Waraittaa',
  // Multi-modal routing (plan-21 Phase 6) — partial; rest falls back to Spanish.
  'directions.modeLabel': 'Kasa süka pütüin',
  'corridors.legend': 'Wopu eemüin saaꞌin',

  // Hazard zones (plan-21 Phase 4) — partial; the rest falls back to Spanish.
  'hazards.fire': 'Siki',
  'hazards.unverified': 'Nnojotsü shiimain',
}

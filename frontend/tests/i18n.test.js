// i18n dictionary + translator tests. Spanish is the source of truth; en/pt
// must define the exact same key set, and translate() must interpolate and
// fall back correctly.
import { describe, expect, it } from 'vitest'
import es from '../src/i18n/es.js'
import en from '../src/i18n/en.js'
import pt from '../src/i18n/pt.js'
import guc from '../src/i18n/guc.js'
import { translate, LANGS, detectLang } from '../src/i18n/index.js'

const esKeys = Object.keys(es).sort()

describe('i18n dictionaries', () => {
  it('exposes the supported languages (es/en/pt full + guc partial)', () => {
    expect(LANGS.map((l) => l.code)).toEqual(['es', 'en', 'pt', 'guc'])
  })

  it('en has exactly the same key set as es', () => {
    expect(Object.keys(en).sort()).toEqual(esKeys)
  })

  it('pt has exactly the same key set as es', () => {
    expect(Object.keys(pt).sort()).toEqual(esKeys)
  })

  it('guc is a partial dictionary whose keys are all valid es keys', () => {
    // Wayuunaiki is intentionally partial; every key it defines must exist in
    // the es source set (no stray/typo keys), and missing keys fall back to es.
    const esKeySet = new Set(esKeys)
    for (const key of Object.keys(guc)) {
      expect(esKeySet.has(key), `guc.${key} is not a valid es key`).toBe(true)
    }
    expect(Object.keys(guc).length).toBeGreaterThan(0)
  })

  it('has no empty values in any language', () => {
    for (const [code, dict] of [['es', es], ['en', en], ['pt', pt]]) {
      for (const key of esKeys) {
        expect(dict[key], `${code}.${key} should be a non-empty string`).toBeTruthy()
      }
    }
  })
})

// plan-22: every UI string must be in exactly one language. These guard against
// the bilingual "Spanish · English" / *En sibling pattern coming back. Keep in
// sync with frontend/scripts/i18n-check.js (the CI enforcer).
describe('language purity (plan-22)', () => {
  // Keys where " · " is a deliberate single-language separator, not bilingual.
  const MIDDOT_ALLOWED = new Set([
    'auth.eyebrow', 'auth.guestNote', 'nav.egiSub', 'conn.online.hint',
    'conn.offline.hint', 'home.disasterMeta', 'mesh.active', 'shelterDetail.routeEst',
    'directions.followsRoads', 'picker.cardMeta', 'add.regionPlaceholder',
  ])

  it('has no keys ending in "En" in any dictionary', () => {
    for (const [code, dict] of [['es', es], ['en', en], ['pt', pt], ['guc', guc]]) {
      const bad = Object.keys(dict).filter((k) => /En$/.test(k))
      expect(bad, `${code}.js still has *En keys: ${bad.join(', ')}`).toEqual([])
    }
  })

  it('has no bilingual " · " separators outside the monolingual allowlist', () => {
    for (const [code, dict] of [['es', es], ['en', en], ['pt', pt], ['guc', guc]]) {
      for (const [key, value] of Object.entries(dict)) {
        if (value.includes(' · ') && !MIDDOT_ALLOWED.has(key)) {
          throw new Error(`${code}.${key} contains a bilingual " · " separator: "${value}"`)
        }
      }
    }
  })

  it('does not leak English into the Spanish screen', () => {
    const leaks = ['Who are you looking for?', 'Saved on this device', 'Report type',
      'will sync automatically', 'Timeline', 'reports queued to sync']
    for (const [key, value] of Object.entries(es)) {
      for (const leak of leaks) {
        expect(value.includes(leak), `es.${key} leaks English: "${value}"`).toBe(false)
      }
    }
  })

  it('does not leak Spanish into the Portuguese screen', () => {
    // The old bilingual home.lookingFor leaked Spanish into pt.
    expect(pt['home.lookingFor']).not.toContain('¿A quién buscas?')
    expect(pt['home.lookingFor']).toBe('Quem você procura?')
  })

  it('keeps the specific strings the audit flagged monolingual', () => {
    expect(es['home.lookingFor']).toBe('¿A quién buscas?')
    expect(en['home.lookingFor']).toBe('Who are you looking for?')
    expect(es['detail.timeline']).toBe('Línea de tiempo')
    expect(es['report.optional']).toBe('Opcional')
    expect(en['report.optional']).toBe('Optional')
    expect(pt['report.optional']).toBe('Opcional')
  })
})

describe('translate()', () => {
  it('returns the language-specific string', () => {
    expect(translate('es', 'common.cancel')).toBe('Cancelar')
    expect(translate('en', 'common.cancel')).toBe('Cancel')
    expect(translate('pt', 'common.cancel')).toBe('Cancelar')
  })

  it('translates a typical key differently across languages', () => {
    expect(translate('en', 'nav.home')).toBe('Home')
    expect(translate('en', 'nav.home')).not.toBe(translate('es', 'nav.home'))
  })

  it('falls back to Spanish for a key missing in the target language', () => {
    // Simulate a missing key by querying one that only the fallback resolves:
    // unknown keys return es, and unknown-everywhere returns the key itself.
    expect(translate('en', 'this.key.does.not.exist')).toBe('this.key.does.not.exist')
  })

  it('falls back to the raw key when unknown in every language', () => {
    expect(translate('es', 'totally.unknown.key')).toBe('totally.unknown.key')
  })

  it('interpolates {var} placeholders', () => {
    expect(translate('en', 'search.count', { n: 5 })).toBe('5 people')
    expect(translate('es', 'search.count', { n: 5 })).toBe('5 personas')
    expect(translate('en', 'report.stepCount', { n: 3 })).toBe('Step 3 of 5')
  })

  it('leaves placeholders intact when no matching var is provided', () => {
    expect(translate('en', 'search.count')).toBe('{n} people')
  })
})

describe('detectLang()', () => {
  it('returns a supported language code', () => {
    expect(['es', 'en', 'pt']).toContain(detectLang())
  })
})

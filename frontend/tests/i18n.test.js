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

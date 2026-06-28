#!/usr/bin/env node
// Guard: every UI string must render in exactly one language. A previous design
// hardcoded bilingual "Spanish · English" labels and *En sibling keys; this
// check fails CI if that pattern (or a cross-language leak) comes back.
//
// What it checks, over src/i18n/{es,en,pt,guc}.js:
//   1. es / en / pt have identical key sets (guc is intentionally partial — its
//      keys must all be valid es keys, but it may omit any).
//   2. No key ends in "En" (the dead bilingual-subtitle sibling pattern).
//   3. No value contains the " · " bilingual separator, EXCEPT a small allowlist
//      of keys where the middot is a legitimate monolingual separator
//      (e.g. "EMERGENCIA · GENTE · INFORMACIÓN", "{region} · {affected} …").
//   4. Heuristic: flag values whose language clearly does not match the file
//      (English marker words in es/pt; Spanish/Portuguese markers in en). This
//      is best-effort — it errs toward silence over false positives.
//
// Run with: npm run check:i18n  (also wired into the tests CI workflow).

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const i18nDir = join(fileURLToPath(new URL('.', import.meta.url)), '..', 'src', 'i18n')

async function load(code) {
  const mod = await import(pathToFileURL(join(i18nDir, `${code}.js`)).href)
  return mod.default
}

const [es, en, pt, guc] = await Promise.all(['es', 'en', 'pt', 'guc'].map(load))

// Keys where " · " is a deliberate single-language separator, not a bilingual
// label. Same key set across es/en/pt, so one allowlist covers all three.
const MIDDOT_ALLOWED = new Set([
  'auth.eyebrow',
  'auth.guestNote',
  'nav.egiSub',
  'conn.online.hint',
  'conn.offline.hint',
  'home.disasterMeta',
  'mesh.active',
  'shelterDetail.routeEst',
  'directions.followsRoads',
  'picker.cardMeta',
  'add.regionPlaceholder',
])

// High-signal, low-false-positive marker words for the language heuristic.
// Each entry must NOT appear in any value of its own file's correct language.
const ENGLISH_MARKERS = /\b(the|your|you|are|who|looking|missing|queued|sync|synced|saved|safe|device|account|hospitals)\b/i
const ROMANCE_MARKERS = /(¿|¡|você|buscas|teléfono|registrar a salvo|personas|relatar|abrigos)/i

const failures = []

// ---- 1. key-set parity (es is the source of truth) ----
const esKeys = Object.keys(es).sort()
const esKeySet = new Set(esKeys)
for (const [code, dict] of [['en', en], ['pt', pt]]) {
  const keys = Object.keys(dict).sort()
  const missing = esKeys.filter((k) => !(k in dict))
  const extra = keys.filter((k) => !esKeySet.has(k))
  if (missing.length) failures.push(`${code}.js: missing ${missing.length} key(s): ${missing.join(', ')}`)
  if (extra.length) failures.push(`${code}.js: ${extra.length} unknown key(s): ${extra.join(', ')}`)
}
for (const k of Object.keys(guc)) {
  if (!esKeySet.has(k)) failures.push(`guc.js: unknown key not in es: ${k}`)
}

// ---- 2/3/4. per-value checks across all dictionaries ----
const DICTS = [['es', es], ['en', en], ['pt', pt], ['guc', guc]]
for (const [code, dict] of DICTS) {
  for (const [key, value] of Object.entries(dict)) {
    if (/En$/.test(key)) failures.push(`${code}.js: dead bilingual sibling key "${key}" (keys must not end in "En")`)
    if (typeof value !== 'string' || value === '') {
      failures.push(`${code}.js: ${key} has an empty/non-string value`)
      continue
    }
    if (value.includes(' · ') && !MIDDOT_ALLOWED.has(key)) {
      failures.push(`${code}.js: ${key} contains the " · " bilingual separator → "${value}"`)
    }
    // Language heuristic (skip guc: it intentionally borrows es fallbacks).
    // Strip {placeholders} first — they are language-neutral interpolation slots.
    const text = value.replace(/\{\w+\}/g, ' ')
    if (code === 'es' || code === 'pt') {
      const m = text.match(ENGLISH_MARKERS)
      if (m) failures.push(`${code}.js: ${key} looks like English ("${m[0]}") → "${value}"`)
    } else if (code === 'en') {
      const m = text.match(ROMANCE_MARKERS)
      if (m) failures.push(`en.js: ${key} looks like Spanish/Portuguese ("${m[0]}") → "${value}"`)
    }
  }
}

if (failures.length) {
  console.error('[i18n-check] FAIL — language-purity problems found:')
  for (const f of failures) console.error('  - ' + f)
  console.error('\nEvery UI string must be in exactly one language. See docs/plans/plan-22-i18n-language-purity-audit.md.')
  process.exit(1)
}

console.log(`[i18n-check] OK — es/en/pt share ${esKeys.length} keys, no *En keys, no bilingual strings.`)

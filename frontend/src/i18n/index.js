// i18n core for the EGI PWA. Spanish is the source of truth; en/pt fall back to
// es, and finally to the raw key. A tiny observable store keeps the current
// language outside React so non-React helpers can read it too, and a thin React
// context exposes a `t()` to components.
//
// NOTE: the chosen language is a non-sensitive UI preference, so persisting it
// in localStorage ('egi_lang') is fine — the IndexedDB-only rule is about
// person/report data, not UI prefs.
import { createContext, createElement, useContext, useEffect, useState } from 'react'
import es from './es.js'
import en from './en.js'
import pt from './pt.js'

const DICTS = { es, en, pt }

export const LANGS = [
  { code: 'es', label: 'Español' },
  { code: 'en', label: 'English' },
  { code: 'pt', label: 'Português' },
]

const STORAGE_KEY = 'egi_lang'
const SUPPORTED = LANGS.map((l) => l.code)

// Detect the initial language: saved preference > browser language > Spanish.
export function detectLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && SUPPORTED.includes(saved)) return saved
  } catch { /* localStorage may be unavailable */ }
  const nav = (typeof navigator !== 'undefined' && (navigator.language || navigator.userLanguage)) || ''
  const base = String(nav).toLowerCase().split('-')[0] // e.g. 'pt-BR' -> 'pt'
  if (SUPPORTED.includes(base)) return base
  return 'es'
}

// ----- Observable store (module-level, framework-agnostic) -----
let current = detectLang()
const subscribers = new Set()

export function getLang() {
  return current
}

export function setLang(code) {
  if (!SUPPORTED.includes(code) || code === current) return
  current = code
  try { localStorage.setItem(STORAGE_KEY, code) } catch { /* ignore */ }
  subscribers.forEach((fn) => fn(code))
}

export function subscribe(fn) {
  subscribers.add(fn)
  return () => subscribers.delete(fn)
}

// Look up a key, interpolating {var} placeholders from `vars`.
export function translate(lang, key, vars) {
  const dict = DICTS[lang] || DICTS.es
  let str = dict[key]
  if (str === undefined) str = DICTS.es[key]
  if (str === undefined) str = key
  if (vars) {
    str = str.replace(/\{(\w+)\}/g, (m, name) =>
      (vars[name] === undefined || vars[name] === null) ? m : String(vars[name])
    )
  }
  return str
}

// ----- React context -----
const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(current)
  useEffect(() => subscribe(setLangState), [])
  const value = {
    lang,
    setLang,
    t: (key, vars) => translate(lang, key, vars),
  }
  return createElement(I18nContext.Provider, { value }, children)
}

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (ctx) return ctx
  // Fallback for components rendered outside a provider (e.g. in tests).
  return { lang: current, setLang, t: (key, vars) => translate(current, key, vars) }
}

// translate.js — on-device translation of dynamic (user-entered) strings.
//
// Static UI strings are handled by the bundled i18n dictionaries (src/i18n).
// This helper is for DYNAMIC text — e.g. a free-text note typed by one user that
// another user reads in a different language. It is local-first (plan §7): it
// only translates when the native Android bridge exposes an on-device ML Kit
// translator (window.EgiNative.translate). It never makes a cloud call, so in a
// plain browser it simply resolves to the original text unchanged.
//
// See mobile/android/PLAN14_TRANSLATION.md for the intended native integration.

const hasNativeTranslate = () =>
  typeof window !== 'undefined' &&
  !!window.EgiNative &&
  typeof window.EgiNative.translate === 'function'

// translateDynamic(text, targetLang) -> Promise<string>
// Resolves to the translated text when an on-device translator is available,
// otherwise resolves to the original text. Never rejects.
export async function translateDynamic(text, targetLang) {
  const str = text == null ? '' : String(text)
  if (!str.trim() || !targetLang) return str
  if (!hasNativeTranslate()) return str
  try {
    const out = await window.EgiNative.translate(str, targetLang)
    return (out === undefined || out === null || out === '') ? str : String(out)
  } catch (e) {
    return str // local-first: degrade silently to the original text
  }
}

// True when on-device dynamic translation is available on this device.
export function canTranslateDynamic() {
  return hasNativeTranslate()
}

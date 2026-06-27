// speech.js — text-to-speech for the low-literacy / panic "Modo simple".
// Prefers the native Android bridge (window.EgiNative.speak) when present, then
// falls back to the Web Speech API (window.speechSynthesis). In a browser that
// supports neither, every export is a safe no-op and nothing ever throws.
//
// Privacy: this only reads UI labels aloud on the device. No audio is recorded,
// uploaded, or stored — consistent with the no-analytics rule.

const hasNative = () =>
  typeof window !== 'undefined' &&
  !!window.EgiNative &&
  typeof window.EgiNative.speak === 'function'

const hasWebSpeech = () =>
  typeof window !== 'undefined' &&
  'speechSynthesis' in window &&
  typeof window.SpeechSynthesisUtterance !== 'undefined'

// True when at least one speech backend is usable on this device.
export function canSpeak() {
  return hasNative() || hasWebSpeech()
}

// Map an i18n language code to a BCP-47 tag the speech engine understands.
// Wayuunaiki (guc) has no TTS voice anywhere; fall back to Spanish phonetics,
// which is the closest widely-available approximation for its speakers.
const localeFor = (lang) => {
  switch (lang) {
    case 'es': return 'es-ES'
    case 'en': return 'en-US'
    case 'pt': return 'pt-BR'
    case 'guc': return 'es-ES'
    default: return 'es-ES'
  }
}

// Speak `text` in `lang`. Best-effort and side-effect-only; returns nothing.
export function speak(text, lang = 'es') {
  const str = (text || '').trim()
  if (!str) return
  if (hasNative()) {
    try { window.EgiNative.speak(str, lang); return }
    catch (e) { /* fall through to web speech */ }
  }
  if (hasWebSpeech()) {
    try {
      window.speechSynthesis.cancel() // stop any in-flight utterance first
      const u = new window.SpeechSynthesisUtterance(str)
      u.lang = localeFor(lang)
      window.speechSynthesis.speak(u)
    } catch (e) { /* no-op on failure */ }
  }
}

// voiceInput.js — speech-to-text (dictation) for free-text fields.
//
// Lets a user speak instead of type — important for low-literacy users and for
// languages with non-Latin orthographies. Prefers the native Android bridge
// (window.EgiNative.startVoiceInput) when present; otherwise uses the Web Speech
// API (SpeechRecognition / webkitSpeechRecognition). Degrades to a no-op that
// reports "unsupported" via onError so callers can hide or disable the UI.
//
// Privacy: dictation runs on the platform's recognizer. Nothing is stored or
// uploaded by EGI; only the recognized text is handed back to fill a field.

const hasNativeVoice = () =>
  typeof window !== 'undefined' &&
  !!window.EgiNative &&
  typeof window.EgiNative.startVoiceInput === 'function'

const getRecognition = () => {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

const localeFor = (lang) => {
  switch (lang) {
    case 'es': return 'es-ES'
    case 'en': return 'en-US'
    case 'pt': return 'pt-BR'
    case 'guc': return 'es-ES' // no recognizer for Wayuunaiki; closest fallback
    default: return 'es-ES'
  }
}

// True when some dictation backend is usable on this device.
export function canDictate() {
  return hasNativeVoice() || !!getRecognition()
}

// startDictation(lang, onResult, onError) -> stop()
// Begins one dictation session. Calls onResult(text) with the recognized text,
// onError(err) on failure/unsupported. Returns a stop() function that is always
// safe to call.
export function startDictation(lang = 'es', onResult = () => {}, onError = () => {}) {
  // Native bridge: it owns its own UI/lifecycle and calls back with the result.
  if (hasNativeVoice()) {
    try {
      // The native side may either return the text (sync/promise) or invoke a
      // global callback. Support the promise shape; install a callback hook too.
      window.EgiVoice = window.EgiVoice || {}
      window.EgiVoice.onResult = (text) => { try { onResult(String(text || '')) } catch (e) { /* ignore */ } }
      window.EgiVoice.onError = (err) => { try { onError(err) } catch (e) { /* ignore */ } }
      const ret = window.EgiNative.startVoiceInput(lang)
      if (ret && typeof ret.then === 'function') {
        ret.then((text) => onResult(String(text || ''))).catch((e) => onError(e))
      }
    } catch (e) { onError(e) }
    return () => {
      try { if (typeof window.EgiNative.stopVoiceInput === 'function') window.EgiNative.stopVoiceInput() }
      catch (e) { /* ignore */ }
    }
  }

  const Recognition = getRecognition()
  if (!Recognition) {
    onError(new Error('unsupported'))
    return () => {}
  }

  let rec
  try {
    rec = new Recognition()
    rec.lang = localeFor(lang)
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onresult = (e) => {
      try {
        const text = e.results && e.results[0] && e.results[0][0] ? e.results[0][0].transcript : ''
        onResult(String(text || ''))
      } catch (err) { onError(err) }
    }
    rec.onerror = (e) => onError(e && e.error ? e.error : e)
    rec.start()
  } catch (e) {
    onError(e)
    return () => {}
  }

  return () => { try { rec && rec.stop() } catch (e) { /* ignore */ } }
}

# Plan-14 — On-device translation & speech bridge (direction doc)

This is a direction document for the native half of plan-14 (inclusive crisis
access). The web app (the PWA in `frontend/`) already degrades gracefully: when
the native bridge methods below are absent it falls back to bundled i18n
dictionaries, the original (untranslated) text, and the browser Web Speech API.
The Android host should add **on-device, offline** translation and speech so the
app works for low-literacy users and minority-language speakers with no network.

## Target languages

Offline language packs to download (paired with Spanish/Portuguese/English):

- Spanish (`es`) ↔ Wayuunaiki (`guc`)
- Spanish (`es`) ↔ Warao
- Spanish (`es`) ↔ Pemón
- Spanish (`es`) ↔ Haitian Creole (`ht`)
- `es` ↔ `pt`, `es` ↔ `en`

Note: ML Kit on-device translation does not currently ship models for several
Venezuelan indigenous languages (Wayuunaiki/Warao/Pemón). Where no model exists,
the bridge should return the original text unchanged (the web layer already
treats that as a no-op) until a community/custom model is available.

## ML Kit on-device translation

Use the ML Kit Translation API (`com.google.mlkit:translate`):

1. On first run (or via a settings screen), download the offline model packs for
   the languages above, ideally only on unmetered networks, and cache them.
2. Translate fully on-device — never call a cloud endpoint (local-first,
   plan §7; no data leaves the device).

## JavaScript bridge surface (WebView)

Expose these `@JavascriptInterface` methods on `window.EgiNative` so the existing
web helpers (`frontend/src/lib/translate.js`, `frontend/src/lib/speech.js`,
`frontend/src/lib/voiceInput.js`) light up automatically:

```kotlin
// Dynamic text translation. Should resolve/return the translated string, or the
// original text when no offline model is available. Web side: translateDynamic().
fun translate(text: String, targetLang: String): String   // (or a Promise)

// Text-to-speech (Android TextToSpeech). Web side: speak() in speech.js.
fun speak(text: String, lang: String)

// Speech-to-text dictation. Web side: startVoiceInput() in voiceInput.js;
// deliver the result via window.EgiVoice.onResult(text) / onError(err).
fun startVoiceInput(lang: String)
fun stopVoiceInput()
```

Language codes match the web `LANGS` list (`es`, `en`, `pt`, `guc`, …). For TTS
and dictation of languages with no platform voice (e.g. `guc`), fall back to the
closest available locale (Spanish) rather than failing.

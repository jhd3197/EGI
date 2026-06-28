// EGI PWA smoke-test harness — injected into the WebView over the Chrome DevTools
// Protocol by pwa_cdp.py. Exposes window.__egiTest with capture buffers and async
// "journey" runners that drive the REAL DOM (no shortcuts into app internals) and
// return a JSON verdict { ok, detail, ... } the Python orchestrator asserts on.
//
// The PWA is state-routed (no URL routes / hashes), so journeys assert on rendered
// DOM + persisted data (IndexedDB session, and the native /persons backend) rather
// than on window.location.
(function () {
  if (window.__egiTest && window.__egiTest.__installed) return

  const logs = []
  const T = {
    __installed: true,
    logs,
    // ---- capture console.* so failures surface in the report + logcat ----
    _wrapConsole() {
      for (const level of ['log', 'warn', 'error']) {
        const orig = console[level].bind(console)
        console[level] = function () {
          try { logs.push({ level, msg: Array.from(arguments).map(String).join(' '), t: Date.now() }) } catch (e) {}
          return orig.apply(null, arguments)
        }
      }
    },
    // ---- tiny DOM helpers ----
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    text: (el) => (el && (el.textContent || '')).trim(),
    visible(el) {
      if (!el) return false
      const r = el.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    },
    findByText(needle, tag) {
      const sel = tag || 'button, a, [role=button]'
      const els = Array.from(document.querySelectorAll(sel))
      const low = needle.toLowerCase()
      return els.find((e) => T.visible(e) && T.text(e).toLowerCase().includes(low)) || null
    },
    async clickByText(needle, tag) {
      const el = T.findByText(needle, tag)
      if (!el) throw new Error('clickByText: not found: ' + needle)
      el.click()
      await T.sleep(120)
      return true
    },
    // React controlled inputs ignore a raw .value assignment; set through the
    // native setter and dispatch an input event so onChange fires.
    setInput(el, value) {
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
      setter.call(el, value)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    },
    async waitFor(predicate, timeoutMs = 6000, stepMs = 150) {
      const start = Date.now()
      while (Date.now() - start < timeoutMs) {
        try { if (await predicate()) return true } catch (e) {}
        await T.sleep(stepMs)
      }
      return false
    },
    // The native backend (Room) is the source of truth in the WebView; read it
    // back through the same /persons the PWA uses.
    async persons() {
      const res = await fetch('/persons')
      const data = await res.json()
      return data.records || []
    },
    onAuthScreen: () => !!document.getElementById('egi-alias'),
    // Home is shown once a disaster is chosen: the report CTA ("Reportar") and the
    // bottom tab bar render. Use a couple of resilient signals.
    onHome() {
      const hasReportCta = !!T.findByText('Desaparecido') || !!T.findByText('Reportar', '*')
      return !T.onAuthScreen() && hasReportCta
    },

    // ---- Journey A: enter as guest, then pick the first disaster ----
    async runGuest() {
      const out = { journey: 'guest', ok: false, steps: [] }
      try {
        if (!T.onAuthScreen()) return { ...out, detail: 'not on auth screen at start' }
        await T.clickByText('Invitado') // auth.enterGuest contains "Invitado"
        out.steps.push('clicked guest')
        const atPicker = await T.waitFor(() => !!T.findByText('Activa') || document.querySelectorAll('button').length > 1 && !T.onAuthScreen())
        out.steps.push('left auth: ' + atPicker)
        // Pick the first disaster card (cards carry the "Activa" status pill).
        const card = T.findByText('Activa') ? T.findByText('Activa').closest('button') : null
        if (!card) return { ...out, detail: 'no disaster card found' }
        card.click()
        out.steps.push('clicked first disaster')
        const atHome = await T.waitFor(() => T.onHome(), 8000)
        out.ok = atHome
        out.detail = atHome ? 'reached home as guest' : 'did not reach home'
        return out
      } catch (e) {
        return { ...out, detail: 'error: ' + (e && e.message) }
      }
    },

    // ---- Journey B: enter with a unique alias and prove it persists ----
    async runAlias(alias) {
      const out = { journey: 'alias', ok: false, alias, steps: [] }
      try {
        if (!T.onAuthScreen()) return { ...out, detail: 'not on auth screen at start' }
        const input = document.getElementById('egi-alias')
        T.setInput(input, alias)
        out.steps.push('filled alias')
        await T.sleep(150)
        await T.clickByText('alias') // auth.enterAlias "Entrar con mi alias" (guest btn lacks "alias")
        out.steps.push('clicked enter alias')
        const leftAuth = await T.waitFor(() => !T.onAuthScreen(), 6000)
        out.steps.push('left auth: ' + leftAuth)
        // Persistence proof: the session is stored in IndexedDB (written async by
        // signIn → persist), so poll a moment for it to land.
        await T.waitFor(async () => (await T.readSessionAlias()) === alias, 4000, 250)
        const persisted = await T.readSessionAlias()
        out.persistedAlias = persisted
        out.ok = leftAuth && persisted === alias
        out.detail = out.ok ? 'alias persisted in IndexedDB session' : 'alias not persisted (' + persisted + ')'
        return out
      } catch (e) {
        return { ...out, detail: 'error: ' + (e && e.message) }
      }
    },

    // Read the persisted alias from the PWA's IndexedDB 'meta' store (key 'session').
    readSessionAlias() {
      return new Promise((resolve) => {
        let done = false
        const finish = (v) => { if (!done) { done = true; resolve(v) } }
        try {
          const req = indexedDB.open('egi')
          req.onerror = () => finish(null)
          req.onsuccess = () => {
            const db = req.result
            if (!db.objectStoreNames.contains('meta')) return finish(null)
            const tx = db.transaction('meta', 'readonly')
            const get = tx.objectStore('meta').get('session')
            get.onsuccess = () => {
              const val = get.result
              const user = val && (val.user || (val.value && val.value.user))
              finish(user ? user.name : null)
            }
            get.onerror = () => finish(null)
          }
          setTimeout(() => finish(null), 3000)
        } catch (e) { finish(null) }
      })
    },

    // ---- Journey C: create a missing-person report through the sheet ----
    async runReport(name) {
      const out = { journey: 'report', ok: false, name, steps: [] }
      try {
        if (!T.onHome()) return { ...out, detail: 'not on home; run guest/alias + pick disaster first' }
        const before = (await T.persons()).length
        out.steps.push('persons before: ' + before)
        // Open the "Desaparecido" (missing) report flow.
        await T.clickByText('Desaparecido')
        const sheetOpen = await T.waitFor(() => !!T.findByText('Continuar') || !!T.findByText('Guardar'))
        out.steps.push('sheet open: ' + sheetOpen)
        // Walk the multi-step flow: on each step fill any visible text fields, then
        // Continue, until the Submit (Guardar) button appears.
        for (let i = 0; i < 8; i++) {
          const fields = Array.from(document.querySelectorAll('input, textarea')).filter(T.visible)
          for (const f of fields) { if (!f.value) T.setInput(f, i === 0 ? name : name + ' ' + i) }
          await T.sleep(120)
          const submit = T.findByText('Guardar')
          if (submit) { submit.click(); out.steps.push('submitted at step ' + i); break }
          const cont = T.findByText('Continuar')
          if (!cont) { out.steps.push('no continue/submit at step ' + i); break }
          cont.click()
          await T.sleep(180)
        }
        // After submit the PWA queues + POSTs /sync to the native bridge.
        const landed = await T.waitFor(async () => (await T.persons()).length > before, 8000, 400)
        const after = (await T.persons()).length
        const names = (await T.persons()).map((p) => p.name)
        out.steps.push('persons after: ' + after)
        out.ok = landed && names.some((n) => (n || '').indexOf(name) === 0)
        out.detail = out.ok ? 'report persisted to native DB' : 'report did not reach native DB'
        return out
      } catch (e) {
        return { ...out, detail: 'error: ' + (e && e.message) }
      }
    },
  }

  T._wrapConsole()
  window.__egiTest = T
  console.log('[EGI] test harness installed')
})()

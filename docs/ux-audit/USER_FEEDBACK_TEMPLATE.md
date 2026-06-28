# User feedback template (plan-29 §6)

Use this to capture a user-reported UX issue. It mirrors the in-app **"Reportar
un problema"** button (Settings → Report a problem), which opens a pre-filled
mail draft with the non-personal context fields below. Triage incoming reports
into a `findings-NNN.md` round.

> Privacy: collect the minimum. Do **not** paste names, cédulas, phone numbers,
> or locations of people into a report. The in-app draft only attaches screen,
> language, app version, and device user-agent.

---

## Report

- **Screen / flow:** (e.g. Shelter detail → Directions)
- **Device / OS / browser:** (e.g. Moto G Play 2023 / Android 12 / WebView)
- **Language:** es / en / pt
- **App version / build:**
- **What happened:** (one or two sentences)
- **What you expected:**
- **Screenshot or screen recording:** (attach if possible)
- **Severity:**
  - [ ] Blocker — cannot complete a critical task (register, search, find a shelter)
  - [ ] High — confusing or broken, but a workaround exists
  - [ ] Medium — visual / polish issue
  - [ ] Low — nice-to-have

## Triage (filled by the maintainer)

- **Finding ID:** F-NNN-NN
- **Reproducible:** yes / no / sometimes
- **Root cause:**
- **Fix / decision:**
- **Linked commit / PR:**

---

### Configuring the in-app report destination

The report button builds a `mailto:` to `soporte@egi.app` by default. A
deployment can override the address without a rebuild:

```js
localStorage.setItem('egi_feedback_email', 'ops@your-org.example')
```

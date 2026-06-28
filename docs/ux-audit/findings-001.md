# UX audit findings — round 001

**Date:** 2026-06-28
**Scope:** PWA frontend (`frontend/src/`) + Android WebView wrapper.
**Auditor:** plan-29 baseline pass.
**Tooling:** `npm run ux:audit` (i18n purity, WCAG contrast over design tokens,
offline self-containment) + manual review.

This is the first round of the EGI UX audit (plan-29). It records the three known
issues the plan was created to fix, their resolution, and the lower-severity items
the automated pass surfaced for future rounds.

---

## Resolved this round

### F-001-01 — Header wordmark rendered with an oversized "E" (High)

- **Where:** `frontend/src/components/Wordmark.jsx`.
- **Symptom:** the component drew "E" at 100% size and "GI" at ~60%, so the
  lockup looked like a broken or half-loaded logo on every screen.
- **Fix:** render "EGI" as one uniform run of text. The `size` prop now sets the
  cap-height of the whole wordmark.
- **Regression guard:** `frontend/tests/ux-audit.test.js` asserts the markup is a
  single text run and never emits two font sizes.

### F-001-02 — App background was a generic warm beige (Medium)

- **Where:** `AppShell.jsx` (and the auth/picker shells + small accent fills).
- **Symptom:** the `#F4EFE7` warm beige read like a generic AI-generated app and
  clashed with the white cards.
- **Fix:** introduced `frontend/src/styles/tokens.js` and moved the background to
  a clean cool neutral — `color.bg` = `#F8F9FA`, with `#F1F3F5` for sunken accent
  fills. No component hardcodes `#F4EFE7` anymore.
- **Regression guard:** `tokens.test.js` + `ux-audit.test.js` lock `color.bg`.

### F-001-03 — Shelter directions asked users to type raw lat/lon (High)

- **Where:** `ShelterDetailScreen.jsx`, "Desde otro lugar".
- **Symptom:** the only origin option was a free-text `lat, lon` field — unusable
  for a distraught user in a crisis.
- **Fix:** the primary **Directions** button now defaults to *use my location*.
  "Desde otro lugar" offers **Usar mi ubicación**, **Elegir en el mapa**, and
  **Escribir un lugar** (best-effort, offline-degrading geocode via
  `lib/directions.js` `geocodePlace`). Raw coordinates are demoted to a
  **Coordenadas (avanzado)** disclosure.
- **Regression guard:** `ux-audit.test.js` asserts the coordinates input is not
  the primary/default control (it sits after "use my location" and inside the
  advanced disclosure).

---

## Open items (lower severity — track for the next round)

From `npm run ux:audit` contrast (WCAG 2.1 AA over the tokens). Critical body-text
pairs all pass (≥9:1). The following are **below AA but not release-gated**; use
them only for large/secondary text, or darken them in a future pass:

| Pair | Ratio | Needed | Note |
| --- | --- | --- | --- |
| muted text (`#8A837A`) on surface | 3.74:1 | 4.5 | OK for large text; avoid for body copy. |
| muted text on app background | 3.55:1 | 4.5 | Same. |
| faint text (`#A9A299`) captions on surface | 2.53:1 | 3.0 | Below even large-text AA — used for monospace meta; consider darkening. |
| white on primary button (`#E5343B`) | 4.30:1 | 4.5 | Just under AA for normal text; buttons use semibold ≥13px so it is borderline. Consider a slightly darker red for small button text. |

- **A11y:** `tests/a11y.test.js` enforces accessible names on buttons/inputs for
  `ShelterDetailScreen`; extend the rendered-screen coverage in later rounds.
- **Baseline screenshots:** capture per `baseline/README.md` on the two test
  phones (Samsung SM-S134DL, Moto G Play 2023) once the WebView render path
  (pre-existing TDZ noted in plans 19/27) is cleared.

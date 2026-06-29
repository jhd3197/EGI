# UX audit findings — round 002

**Date:** 2026-06-29
**Scope:** PWA mobile chrome, search/directions input, home density (`frontend/src/`).
**Auditor:** plan-31 (mobile navigation, search UX & visual density).
**Tooling:** `npm run ux:audit` + `npm test` (incl. `tests/plan31.test.js`) + manual review.

This round addresses the four issues that surfaced during real-device review:
the wrong notification icon, the lopsided bottom tab bar, coordinates-first
search/directions, and overly heavy screens.

---

## Resolved this round

### F-002-01 — Notifications reached through a non-obvious icon (Medium)

- **Where:** `TopBar.jsx`, `SettingsScreen.jsx`, `PushToggle.jsx`.
- **Symptom:** notification preferences were only reachable through the generic
  gear (and, in older/cached builds, a sun-like glyph), so users did not
  associate the control with notifications.
- **Fix:** a **bell** (`BellIcon`) now marks notifications everywhere — a top-bar
  bell button that jumps to Settings, the Settings *Notificaciones* section
  header (icon + label lockup), and the push opt-in toggle row. The `SettingsIcon`
  was also redrawn from radial spokes (which read as a *sun* at 14–16 px — the
  glyph users mistook for notifications) to a clearly toothed cog, confirmed on
  both lab phones.
- **Regression guard:** `tests/a11y.test.js` keeps button names; the bell uses the
  new `notif.bellAria` label across es/en/pt.

### F-002-02 — Bottom tab bar was lopsided (High)

- **Where:** `TabBar.jsx`, `lib/view.js`.
- **Symptom:** the report `+` sat third with only two tabs before it and up to
  four after, with 9.5 px labels — visually left-heavy and easy to mis-tap.
- **Fix:** a symmetrical **3 + report + 3** layout — fixed left tabs (Inicio,
  Buscar, Mapa), the centred report button, and three right slots (Mis reportes,
  a contextual category, Ajustes). The sixth slot follows the user's enabled
  category (shelters → operations → animals) and falls back to Cómo llegar. Tab
  touch targets are ≥ 48 px and labels are 10 px.
- **Regression guard:** `tests/plan31.test.js` asserts exactly seven controls with
  the report button centred (4th of 7).

### F-002-03 — Search and directions asked for coordinates first (High)

- **Where:** `SearchScreen.jsx`, `DirectionsScreen.jsx`, `lib/directions.js`,
  `MapScreen.jsx`.
- **Symptom:** Search led with the cédula field, and Directions exposed raw
  `lat, lon` inputs as the primary way to set origin/destination.
- **Fix:** Search now leads with a prominent free-text name/place field plus a
  helper line, with cédula/document search demoted into an accordion. Directions
  defaults to **place-name** input for both origin and destination, with a
  **Lugar / Coordenadas** switch that hides raw coordinates behind an explicit
  advanced mode. `geocodePlace` gained a persistent cache (instant repeats,
  offline once seen) and the UI shows a helpful message when a place is not found
  or the device is offline. MapScreen notes that "search this area" is scoped to
  the visible map.
- **Regression guard:** `tests/plan31.test.js` asserts the destination place input
  renders by default and the raw-coordinates input is hidden until the user
  switches mode. `ShelterDetailScreen` already met this bar via the plan-29
  disclosure (`tests/ux-audit.test.js`).

### F-002-04 — Home and top bar were visually heavy (Medium)

- **Where:** `HomeScreen.jsx`, `TopBar.jsx`.
- **Symptom:** the home screen stacked a category note, emergency pulse,
  simple-mode toggle, title, divider, three-card intent picker, suggestions,
  search button, report group, check-in, and a full recent-activity list; the top
  bar carried a logo, language switcher, mesh pill, gear, connection pill, and a
  two-line emergency strip.
- **Fix:** Home drops the intent picker and the header simple-mode toggle, leads
  with a calm **Estoy bien** check-in, then **Busco a alguien** and the
  **Reportar** group, and collapses recent activity by default. The top bar moves
  the language switcher to Settings, collapses the mesh + connection pills into
  one status pill (local-network peers when mesh is active, else online/offline),
  slims the bell and gear to quiet icon buttons, and shows the disaster strip on
  one line.
- **Regression guard:** `tests/plan31.test.js` asserts the home screen no longer
  renders the intent picker or the simple-mode toggle while keeping the primary
  actions.

---

## Open items (carried from round 001)

- The sub-AA contrast pairs from round 001 are unchanged (white on the primary red
  button is 4.3:1; muted/faint text below AA for body copy). Not release-gated;
  track for a future darkening pass.
- Baseline screenshots on the two lab phones (Samsung SM-S134DL, Moto G Play 2023)
  still to be captured once a device is available to this session.

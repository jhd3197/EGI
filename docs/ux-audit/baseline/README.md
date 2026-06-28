# UX baseline screenshots (plan-29 §1)

This folder holds the visual baseline for the UX audit: a screenshot of every
major screen, across widths and languages, for before/after comparison.

## What to capture

For the PWA (browser DevTools device toolbar) at three widths — **360 px**,
**414 px**, **768 px** — and for the Android WebView on at least one real device
and one emulator, capture each major screen in **Spanish, English, and
Portuguese**:

- Auth / entry (`AuthScreen`)
- Disaster picker (`DisasterPicker`)
- Home (`HomeScreen` + `SimpleHomeScreen`)
- Search (`SearchScreen`) + person detail (`PersonDetail`)
- Report sheet (`ReportSheet`)
- Shelters list + detail (`SheltersScreen`, `ShelterDetailScreen`)
- Animals (`AnimalsScreen`, `AnimalDetailScreen`)
- Operations (`OperationsScreen`, `OperationDetailScreen`)
- Mesh (`MeshScreen`), Map (`MapScreen`), Directions (`DirectionsScreen`)
- Dashboard (`DashboardScreen`), Settings (`SettingsScreen`)

## Naming convention

```
<screen>-<locale>-<width>.png
```

Examples: `home-es-360.png`, `shelter-detail-pt-768.png`,
`directions-en-414.png`. For Android WebView captures, suffix the device serial:
`home-es-samsung-R9TT311P25N.png`.

## Where the images live

Baseline PNGs are **device-captured artifacts and are not committed** (same
rationale as the plan-19 visual baselines): they are large, binary, and
device-specific. Generate them locally / in the device lab and store them with
your release artifacts. This `README.md` is the committed contract for *how* the
set is produced.

The Android device-lab tooling already produces launch screenshots — see
`mobile/android/scripts/install-and-configure.sh` and
`mobile/android/screenshots/` — and the plan-19 `pwa_visual.py` perceptual diff
can compare a new build against a stored baseline.

## After capturing

Review the set against `../PREFLIGHT_CHECKLIST.md` and record anything new in a
`../findings-NNN.md` file.

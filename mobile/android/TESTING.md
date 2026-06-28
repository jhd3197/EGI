# EGI Android — Testing Guide

How to test the Android app, from JVM unit tests up to driving the embedded PWA on
real phones. The PWA-in-WebView end-to-end harness was added in **plan-19**.

## Layers

| Layer | What it covers | Command | Needs |
|-------|----------------|---------|-------|
| JVM unit | mesh codecs, record mappers, bloom filter, crypto, SMS parsing | `./gradlew test` | nothing |
| Instrumented | Room migrations, mesh merge, **PwaApiBridge** reads/writes, foreground service | `./gradlew connectedCheck` | 1 device/emulator |
| PWA smoke (A/B/C) | the embedded PWA's real user journeys in the WebView | `./scripts/pwa-smoke-test.sh` | ≥1 device |
| Visual regression | screenshot diff vs per-device baselines | `EGI_VISUAL=1 ./scripts/pwa-smoke-test.sh` | baselines + 1 device |
| Two-device mesh | a report created on phone A reaching phone B over BLE | `python ./scripts/mesh-pwa-e2e-test.py` | 2 phones, Bluetooth on |

## Environment

```bash
cd mobile/android
source ./scripts/detect-env.sh   # sets JAVA_HOME (Android Studio JBR) + ANDROID_SDK_ROOT
adb devices -l                   # both phones should show `device`
```

The two reference devices: **Samsung SM-S134DL** (`R9TT311P25N`, API 33) and
**Moto G Play 2023** (`ZY22J8F4FJ`, API 31).

## PWA WebView smoke tests (Journeys A/B/C)

`./scripts/pwa-smoke-test.sh` builds + installs the debug APK, then drives the PWA
on every connected device over the **Chrome DevTools Protocol** (no human taps):

- **Journey A — Guest entry:** tap "Enter as guest", pick the first disaster, reach home.
- **Journey B — Alias entry:** type a unique alias, enter, assert it persists in IndexedDB.
- **Journey C — Create report:** open the missing-person sheet, fill + submit, assert the
  record reached the native Room backend (`GET /persons` count grows).

Each journey runs in fresh app state (`pm clear`) and pins `egi_lang=es` for
determinism. Artifacts land in `test-results/<serial>/`:
`{guest,alias,report}.{png,json}`, `console.log`, `result.json`. The script exits
non-zero if any journey fails, so CI can gate on it.

Flags:
- `--no-build` — reuse the APK already on the device (skip build/install).
- `<serial> …` — restrict to specific devices.

How it works: the app enables WebView remote debugging for **debuggable builds
only** (`MainActivity` → `setWebContentsDebuggingEnabled`). `pwa_cdp.py` forwards
the WebView's devtools socket and runs JS; `pwa-test-harness.js` (injected as
`window.__egiTest`) drives the real DOM and returns JSON verdicts.

## Visual regression (Phase 5)

```bash
./scripts/update-baselines.sh                 # capture baselines from a known-good run
EGI_VISUAL=1 ./scripts/pwa-smoke-test.sh       # compare future runs to them
```

- Baselines are stored per-device under `screenshots/baseline/<serial>/<journey>.png`
  and are **not committed** (local artifact, resolution-specific).
- The diff is a perceptual per-pixel comparison (`pwa_visual.py`, Pillow + numpy).
  A journey fails if more than `EGI_VISUAL_THRESHOLD` (default **8%**) of pixels
  differ; a red-overlay `*.diff.png` is written for inspection. The default
  tolerates dynamic content (status-bar clock, relative timestamps, mount
  animations) — a real layout/font/colour regression differs far more.

## Two-device mesh end-to-end (Phase 4)

```bash
# Bluetooth must be ON on both phones:
adb -s R9TT311P25N shell svc bluetooth enable
adb -s ZY22J8F4FJ  shell svc bluetooth enable
python ./scripts/mesh-pwa-e2e-test.py
```

Creates a report on phone A through the PWA, enables the mesh on both, and polls
phone B's Room (`GET /persons`) for the record, measuring create→receive latency.
Artifacts: `test-results/mesh/{A-…-sender,B-…-receiver}.png`, `result.json`.

> **Known limitation:** end-to-end BLE propagation does not yet complete reliably
> within the timeout. Android throttles the sub-second `DutyCycler` scan windows
> ("scanning too frequently"), starving GATT discovery/exchange. The advertise
> side is fixed (a PWA-created record now refreshes the advertised bloom, verified
> on hardware), but retuning the mesh duty cycle is a mesh-layer concern tracked
> for plan-18. The harness reports PASS/FAIL + latency honestly.

## CI

- **`.github/workflows/android-pwa-smoke.yml`** — on every push/PR: build the PWA
  (with `npm run check:offline`), build the APK, run `lintDebug` + unit tests, boot
  an emulator, and run the single-device journeys. Artifacts uploaded.
- **`.github/workflows/android-mesh-e2e.yml`** — manual / nightly on a self-hosted
  runner labelled `egi-mesh` with two phones attached (cloud emulators can't do BLE).

## Troubleshooting

- **CDP handshake 403** — fixed by suppressing the `Origin` header (`pwa_cdp.py`).
- **`startMesh` Java exception** — BLE runtime permissions were wiped by `pm clear`;
  the mesh test re-grants them. For manual runs use `install-and-configure.sh`.
- **`POST_NOTIFICATIONS` grant fails on API 31** (Moto) — expected and harmless.
- **Wrong-language button not found** — the smoke test pins `egi_lang=es`; the
  harness matches Spanish UI text.

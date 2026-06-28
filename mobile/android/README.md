# EGI Android App

This is the native Android client. It wraps the offline-first web app in a `WebView` and adds Bluetooth Low Energy capabilities for device-to-device sync when there is no internet.

## Open in Android Studio

1. Open the `mobile/android` folder in Android Studio.
2. Sync Gradle.
3. Copy the contents of `frontend/` into `mobile/android/app/src/main/assets/www/`
   (create the folder if needed):

   ```bash
   mkdir -p mobile/android/app/src/main/assets/www
   cp -R frontend/* mobile/android/app/src/main/assets/www/
   ```

4. Run on a device or emulator.

## Bluetooth mesh

`BluetoothMeshManager.kt` orchestrates the store-and-forward mesh described in
`mobile/shared/protocol.md`:

- **`mesh/`** — wire contracts: `RecordEnvelope`/`IndexEntry` (+ `EnvelopeCodec`),
  `BleConstants` (service/characteristic UUIDs), and a compact `BloomFilter`.
- **`data/`** — a Room database (`persons`, `reports`, `sync_log`) mirroring the
  server schema, plus `MeshRepository` (last-write-wins dedup by `record_id`) and
  `RecordMappers` (entity ⇄ envelope ⇄ `/sync` JSON).
- **`ble/`** — `BleAdvertiser` (service UUID + bloom), `BleScanner`, `GattServer`
  and `GattClient` for index exchange and chunked record transfer.
- **`net/CloudSyncClient`** — uploads/downloads to the FastAPI `/sync` endpoint.
- **`bridge/EgiBridge`** — the `window.EgiNative` JavaScript interface so the
  WebView can trigger mesh sync and read the local DB
  (`frontend/src/lib/meshBridge.js` is the web side).
- **`wifi/WifiDirectManager`** — Wi-Fi Direct discovery for the bulk-transfer
  fallback (peer discovery wired; socket transfer scaffolded).

### Configuring the sync server

The native cloud client defaults to `http://10.0.2.2:3000` (the host loopback as
seen from the emulator). Override it by writing the `api_url` key into the
`egi_mesh` SharedPreferences (resolved in one place, `CloudSyncClient.resolveBaseUrl`).
Cleartext HTTP is allowed only for local/LAN hosts (see
`res/xml/network_security_config.xml`); use `https://` for real deployments.

### Push notifications (FCM) — optional

The app ships a native Firebase Cloud Messaging client
(`push/MeshFirebaseMessagingService`). It is **optional and off by default**: the
google-services Gradle plugin is applied only when a real `google-services.json`
is present, so a fresh checkout (and CI) still builds `assembleDebug` with FCM
dormant.

To enable it:

1. Create a Firebase project and register an Android app with package
   `com.egi.app`.
2. Copy `app/google-services.json.example` to `app/google-services.json` and fill
   in your project's values. The real file is gitignored — never commit it.
3. Rebuild. On launch the device registers its FCM token with the server
   (`POST /push/subscribe`, `kind="fcm"`); incoming alerts are forwarded to the
   PWA via the same `window.EgiMesh.onEvent(...)` bridge used for mesh events.

FCM tokens are treated as sensitive and never logged raw.

## Running the tests

- **JVM unit tests** (codecs, mappers, parsers — no device needed):

  ```bash
  ./gradlew test
  ```

- **Instrumented tests** (Room migration + report-merge, SMS check-in record
  creation, foreground-service notification) on a connected device/emulator:

  ```bash
  ./gradlew connectedCheck
  ```

  These live under `app/src/androidTest/` and cannot run in a headless/SDK-less
  environment.

- **PWA WebView end-to-end smoke tests** (drives the embedded PWA on real devices
  with no human interaction) — see [`TESTING.md`](TESTING.md):

  ```bash
  ./scripts/pwa-smoke-test.sh              # build, install, run Journeys A/B/C
  EGI_VISUAL=1 ./scripts/pwa-smoke-test.sh # also do visual-regression checks
  python ./scripts/mesh-pwa-e2e-test.py    # two-device mesh propagation (needs 2 phones)
  ```

## Status / next steps

- [x] BLE advertisement + scan (with bloom-filtered peer skipping).
- [x] GATT service for index exchange + chunked record transfer.
- [x] Room database mirroring the web app's data, with last-write-wins merge.
- [x] Bridge/cloud sync to `/sync` and a WebView JS bridge.
- [ ] Wi-Fi Direct **bulk** socket transfer (discovery done; streaming is a stub).
- [ ] Encrypt the GATT channel (currently cleartext, per the protocol draft).

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
`egi_mesh` SharedPreferences. Cleartext HTTP is allowed only for local/LAN hosts
(see `res/xml/network_security_config.xml`); use `https://` for real deployments.

## Status / next steps

- [x] BLE advertisement + scan (with bloom-filtered peer skipping).
- [x] GATT service for index exchange + chunked record transfer.
- [x] Room database mirroring the web app's data, with last-write-wins merge.
- [x] Bridge/cloud sync to `/sync` and a WebView JS bridge.
- [ ] Wi-Fi Direct **bulk** socket transfer (discovery done; streaming is a stub).
- [ ] Encrypt the GATT channel (currently cleartext, per the protocol draft).

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

`BluetoothMeshManager.kt` is a placeholder that logs when the mesh would start.
The hard part — discovering peers, connecting over BLE, and exchanging records —
is not implemented yet. See `mobile/shared/protocol.md` for the design.

## TODO

- Implement BLE advertisement and scan.
- Implement GATT service for record exchange.
- Add a local Room database to mirror the web app's IndexedDB data.
- Add a share-via-WiFi-direct fallback.

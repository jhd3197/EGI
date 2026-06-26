package com.egi.app.bridge

import android.webkit.JavascriptInterface
import com.egi.app.BluetoothMeshManager

/**
 * The `window.EgiNative` object exposed to the WebView (PWA). Lets the web UI
 * trigger mesh sync and read the on-device Room DB when running inside the app.
 * In a plain browser this object is simply absent, and the web bridge
 * (`frontend/src/lib/meshBridge.js`) degrades to no-ops.
 *
 * NOTE: every method here is invoked by the WebView on a binder thread, NOT the
 * UI thread. The manager's mutating calls are coroutine-backed and the status
 * reads are from cached volatile fields, so this is safe. Native→web events are
 * delivered separately via the manager's `eventSink` (posted to the UI thread by
 * MainActivity) calling `window.EgiMesh.onEvent(...)`.
 */
class EgiBridge(private val manager: BluetoothMeshManager) {

    @JavascriptInterface
    fun isAvailable(): Boolean = true

    @JavascriptInterface
    fun getDeviceId(): String = manager.deviceId

    @JavascriptInterface
    fun startMesh() = manager.start()

    @JavascriptInterface
    fun stopMesh() = manager.stop()

    @JavascriptInterface
    fun syncMesh() = manager.syncMeshRound()

    @JavascriptInterface
    fun getStatus(): String = manager.statusJson()

    @JavascriptInterface
    fun getLocalRecords(): String = manager.localRecordsJson()

    companion object {
        /** The global name the web bridge looks for: `window.EgiNative`. */
        const val INTERFACE_NAME = "EgiNative"
    }
}

package com.egi.app.bridge

import android.content.Context
import android.util.Log
import android.webkit.JavascriptInterface
import com.egi.app.BluetoothMeshManager
import com.egi.app.MeshConsent

/**
 * The `window.EgiNative` object exposed to the WebView (PWA). Lets the web UI
 * start/stop the mesh, trigger a sync round, read mesh status, and manage the
 * privacy consent when running inside the app. The web app owns its own data
 * (IndexedDB/localStorage), so there is no DB-read bridge method.
 * In a plain browser this object is simply absent, and the web bridge
 * (`frontend/src/lib/meshBridge.js`) degrades to no-ops.
 *
 * NOTE: every method here is invoked by the WebView on a binder thread, NOT the
 * UI thread. The manager's mutating calls are coroutine-backed and the status
 * reads are from cached volatile fields, so this is safe. Native→web events are
 * delivered separately via the manager's `eventSink` (posted to the UI thread by
 * MainActivity) calling `window.EgiMesh.onEvent(...)`.
 */
class EgiBridge(
    private val manager: BluetoothMeshManager,
    private val context: Context,
) {

    @JavascriptInterface
    fun isAvailable(): Boolean = true

    @JavascriptInterface
    fun getDeviceId(): String = manager.deviceId

    /** No-ops unless the user has consented to mesh sync (gated in [MeshConsent]). */
    @JavascriptInterface
    fun startMesh() {
        if (!MeshConsent.hasConsented(context)) {
            Log.i(TAG, "startMesh ignored: mesh consent not granted")
            return
        }
        manager.start()
    }

    @JavascriptInterface
    fun stopMesh() = manager.stop()

    /** Whether the user has accepted the mesh privacy warning. */
    @JavascriptInterface
    fun getMeshConsent(): Boolean = MeshConsent.hasConsented(context)

    /** Persist the user's mesh consent decision from the web UI. */
    @JavascriptInterface
    fun setMeshConsent(value: Boolean) = MeshConsent.setConsented(context, value)

    @JavascriptInterface
    fun syncMesh() = manager.syncMeshRound()

    @JavascriptInterface
    fun getStatus(): String = manager.statusJson()

    companion object {
        private const val TAG = "EGI-Bridge"

        /** The global name the web bridge looks for: `window.EgiNative`. */
        const val INTERFACE_NAME = "EgiNative"
    }
}

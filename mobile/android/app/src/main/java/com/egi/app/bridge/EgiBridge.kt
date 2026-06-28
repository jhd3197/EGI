package com.egi.app.bridge

import android.content.Context
import android.content.Intent
import android.net.Uri
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
    private val pwaApi: PwaApiBridge,
) {

    @JavascriptInterface
    fun isAvailable(): Boolean = true

    /**
     * Persist a `POST /sync` payload (`{"records":[…]}`) to the local Room DB. Called
     * by the injected fetch shim because `shouldInterceptRequest` cannot read a POST
     * body. Returns the JSON the PWA would have gotten from the server.
     */
    @JavascriptInterface
    fun postSync(body: String): String {
        val res = pwaApi.postSync(body)
        // The mesh advertises what this device holds; tell it the local set grew so
        // the new record gets relayed to nearby peers.
        manager.notifyLocalRecordsChanged()
        return res
    }

    /** Persist a `POST /persons/{id}/reports` note to Room. See [postSync]. */
    @JavascriptInterface
    fun postReport(personId: String, body: String): String {
        val res = pwaApi.postReport(personId, body)
        manager.notifyLocalRecordsChanged()
        return res
    }

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

    /** Toggle battery-saver mode (longer relay duty cycle). Persisted natively. */
    @JavascriptInterface
    fun setBatterySaver(value: Boolean) = manager.setBatterySaver(value)

    @JavascriptInterface
    fun getStatus(): String = manager.statusJson()

    /**
     * Hand off turn-by-turn navigation to an external maps app (plan-20 §5).
     * Tries, in order: Google Maps navigation intent, a generic `geo:` point
     * (Waze / OsmAnd / any maps app), then an OpenStreetMap web URL. The PWA's
     * directions helper falls back to the embedded map if this finds no handler.
     * Safe on a binder thread: starts the activity in a NEW_TASK.
     */
    @JavascriptInterface
    fun openTurnByTurn(lat: Double, lng: Double, label: String) {
        val dest = "$lat,$lng"
        val name = Uri.encode(if (label.isNotBlank()) label else "Destino")
        val candidates = listOf(
            "google.navigation:q=$dest",
            "geo:$dest?q=$dest($name)",
            "https://www.openstreetmap.org/directions?to=$dest",
        )
        for (uri in candidates) {
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri)).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
                return
            } catch (e: Exception) {
                Log.d(TAG, "openTurnByTurn: no handler for $uri", e)
            }
        }
        Log.i(TAG, "openTurnByTurn: no navigation app available")
    }

    companion object {
        private const val TAG = "EGI-Bridge"

        /** The global name the web bridge looks for: `window.EgiNative`. */
        const val INTERFACE_NAME = "EgiNative"
    }
}

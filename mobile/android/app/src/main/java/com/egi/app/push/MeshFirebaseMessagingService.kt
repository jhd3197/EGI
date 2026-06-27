package com.egi.app.push

import android.util.Log
import com.egi.app.net.CloudSyncClient
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Native Android FCM client (Phase 6).
 *
 * Two jobs:
 *  1. [onNewToken] — register this device's FCM token with the server
 *     (`POST /push/subscribe`, kind="fcm") so it can receive operation alerts.
 *  2. [onMessageReceived] — forward an incoming alert to the PWA via [PushEventBus]
 *     → `window.EgiMesh.onEvent(...)`, the same event path mesh status uses.
 *
 * Optional by design: FCM only activates when a real `google-services.json` is
 * dropped into `app/` (the google-services Gradle plugin is applied conditionally —
 * see `app/build.gradle`). Without it the firebase-messaging dependency is inert
 * and this service is simply never invoked, so the app still builds and runs.
 *
 * Privacy: the FCM registration token is treated as sensitive — we never log it
 * raw (only its length), matching the plan's "store only hashes if possible" intent
 * (the server stores it; we just transmit it over the same cleartext-restricted
 * channel as /sync).
 */
class MeshFirebaseMessagingService : FirebaseMessagingService() {

    // Short-lived work (one HTTP POST); a SupervisorJob keeps a failure isolated.
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onNewToken(token: String) {
        Log.i(TAG, "FCM registration token refreshed (len=${token.length})")
        val appContext = applicationContext
        scope.launch {
            try {
                val client = CloudSyncClient(CloudSyncClient.resolveBaseUrl(appContext))
                val ok = client.subscribePush(token, kind = "fcm")
                Log.i(TAG, "FCM token subscribe ${if (ok) "ok" else "rejected by server"}")
            } catch (e: Exception) {
                // Offline / server unreachable: the token will be re-offered by FCM on
                // the next refresh, so dropping this attempt is safe.
                Log.w(TAG, "FCM token subscribe failed: ${e.message}")
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = JSONObject()
        message.notification?.let { n ->
            data.put("title", n.title ?: JSONObject.NULL)
            data.put("body", n.body ?: JSONObject.NULL)
        }
        if (message.data.isNotEmpty()) {
            val payload = JSONObject()
            for ((k, v) in message.data) payload.put(k, v)
            data.put("data", payload)
        }
        val event = JSONObject().apply {
            put("type", "push")
            put("data", data)
        }
        // Route via the bus so it works whether or not an Activity/WebView is attached.
        PushEventBus.emit(event.toString())
        Log.i(TAG, "Push alert received; forwarded to PWA bridge")
    }

    companion object {
        private const val TAG = "EGI-FCM"
    }
}

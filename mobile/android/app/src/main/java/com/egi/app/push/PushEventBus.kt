package com.egi.app.push

/**
 * Tiny store-and-forward bridge for native→web push events.
 *
 * An incoming FCM message ([MeshFirebaseMessagingService.onMessageReceived]) may
 * arrive when no Activity (and therefore no WebView) is attached. We can't call
 * `evaluateJavascript` without a WebView, so events are funneled through this
 * process-wide object instead of straight to the bridge:
 *
 * - When `MainActivity` is alive it registers a [sink] (which posts to the UI
 *   thread and forwards to `window.EgiMesh.onEvent(...)`, the SAME path the mesh
 *   manager's eventSink uses), and any events that queued while it was gone are
 *   drained immediately.
 * - When no sink is attached, events are buffered (capped) so a freshly-opened
 *   app still sees the most recent alerts.
 *
 * Deliberately dependency-free and synchronized — no coroutines, no Android imports
 * — so it is safe to touch from a Service binder thread and from the UI thread.
 */
object PushEventBus {

    private const val MAX_PENDING = 20

    private val lock = Any()
    private val pending = ArrayDeque<String>()

    @Volatile
    private var sink: ((String) -> Unit)? = null

    /** Emit a JSON event string (shape: `{"type":"push","data":{...}}`). */
    fun emit(json: String) {
        synchronized(lock) {
            val current = sink
            if (current != null) {
                current.invoke(json)
            } else {
                pending.addLast(json)
                while (pending.size > MAX_PENDING) pending.removeFirst()
            }
        }
    }

    /**
     * Attach (or, with null, detach) the consumer. On attach, any buffered events
     * are flushed in order. The sink is responsible for thread-hopping to the UI
     * thread before touching the WebView.
     */
    fun setSink(sink: ((String) -> Unit)?) {
        synchronized(lock) {
            this.sink = sink
            if (sink != null) {
                while (pending.isNotEmpty()) {
                    sink.invoke(pending.removeFirst())
                }
            }
        }
    }
}
